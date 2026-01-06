"""Minimal supervisor daemon with state machine loop."""

import hashlib
import signal
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Set

from sleepless_agent.core.executor import ClaudeExecutor
from sleepless_agent.core.state import StateManager
from sleepless_agent.config import get_config, ZulipConfig
from sleepless_agent.reporters.base import BaseReporter, NoopReporter
from sleepless_agent.reporters.zulip_reporter import ZulipReporter


class State(Enum):
    """Daemon state machine states."""
    INIT = "init"
    CHECK_CTX = "check_ctx"
    RUN_CLAUDE = "run_claude"
    OBSERVE = "observe"
    IDLE = "idle"


def create_reporter(zulip_config: ZulipConfig) -> BaseReporter:
    """Create appropriate reporter based on configuration.

    Returns ZulipReporter if configured, otherwise NoopReporter.
    """
    if zulip_config.is_valid():
        print(f"Zulip reporter enabled: {zulip_config.stream}")
        return ZulipReporter(
            site=zulip_config.site,
            email=zulip_config.email,
            api_key=zulip_config.api_key,
            stream=zulip_config.stream,
        )
    else:
        if zulip_config.enabled:
            print("Warning: ZULIP_ENABLED=true but missing required settings")
        return NoopReporter()


class Daemon:
    """Minimal Claude Code supervisor daemon.

    State Machine:
        INIT -> CHECK_CTX -> RUN_CLAUDE -> OBSERVE -> (loop or IDLE)
    """

    def __init__(
        self,
        workspace: Path,
        docker_container: str = "claude-cc",
        timeout: int = 3600,
        idle_interval: int = 5,
        reporter: Optional[BaseReporter] = None,
        stall_threshold_minutes: int = 10,
    ):
        """Initialize daemon.

        Args:
            workspace: Path to workspace directory
            docker_container: Name of Docker container
            timeout: Claude execution timeout in seconds
            idle_interval: Seconds to sleep when idle
            reporter: Reporter for observability events
            stall_threshold_minutes: Minutes without progress before warning
        """
        self.workspace = Path(workspace).resolve()
        self.docker_container = docker_container
        self.timeout = timeout
        self.idle_interval = idle_interval
        self.stall_threshold_minutes = stall_threshold_minutes

        self.state = State.INIT
        self.running = False

        self.state_manager = StateManager(self.workspace)
        self.executor = ClaudeExecutor(docker_container, timeout)
        self.reporter = reporter or NoopReporter()

        # Task tracking
        self.current_topic: Optional[str] = None
        self.task_start_time: Optional[float] = None
        self.last_file_snapshot: Set[str] = set()
        self.last_progress_time: Optional[float] = None
        self.stall_warned: bool = False

    def _generate_topic(self) -> str:
        """Generate a unique topic name for the current task."""
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        # Use first 6 chars of hash of prompt for uniqueness
        prompt = self.state_manager.get_prompt() or ""
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:6]
        return f"task-{timestamp}-{prompt_hash}"

    def _get_workspace_files(self) -> Set[str]:
        """Get set of files in workspace with their mtimes."""
        files = set()
        try:
            for path in self.workspace.rglob("*"):
                if path.is_file() and ".git" not in path.parts:
                    # Include mtime in the identifier to detect changes
                    mtime = path.stat().st_mtime
                    files.add(f"{path.relative_to(self.workspace)}:{mtime}")
        except Exception:
            pass
        return files

    def _detect_file_changes(self) -> list:
        """Detect changed files since last check."""
        current_files = self._get_workspace_files()

        # Extract just filenames (without mtime) for comparison
        current_names = {f.rsplit(":", 1)[0] for f in current_files}
        last_names = {f.rsplit(":", 1)[0] for f in self.last_file_snapshot}

        # Find changed or new files
        changed = []
        for f in current_files:
            name = f.rsplit(":", 1)[0]
            if f not in self.last_file_snapshot:
                changed.append(name)

        self.last_file_snapshot = current_files
        return changed

    def parse_status(self, output: str) -> str:
        """Parse Claude output for continuation signals.

        Checks (in order):
        1. "STATUS: DONE" in output -> done
        2. "STATUS: CONTINUE" in output -> continue
        3. .claude/done.flag file exists -> done
        4. Default -> continue

        Args:
            output: Claude's stdout

        Returns:
            "done" or "continue"
        """
        # Check last 20 lines for status markers
        lines = output.strip().split("\n")
        for line in reversed(lines[-20:]):
            if "STATUS: DONE" in line:
                return "done"
            if "STATUS: CONTINUE" in line:
                return "continue"

        # Check done flag file
        if self.state_manager.check_done_flag():
            return "done"

        # Default to continue
        return "continue"

    def run(self) -> None:
        """Run the daemon main loop."""
        self.running = True
        print(f"Daemon started with workspace: {self.workspace}")
        print(f"Docker container: {self.docker_container}")

        # Verify Docker container
        if not self.executor.check_docker():
            print(f"ERROR: Docker container '{self.docker_container}' is not running")
            return

        while self.running:
            try:
                self._step()
            except KeyboardInterrupt:
                print("\nShutting down...")
                break
            except Exception as e:
                print(f"ERROR in main loop: {e}")
                self.state_manager.mark_error(str(e))
                self.state = State.IDLE
                time.sleep(self.idle_interval)

        print("Daemon stopped")

    def _step(self) -> None:
        """Execute one step of the state machine."""
        if self.state == State.INIT:
            self._handle_init()

        elif self.state == State.CHECK_CTX:
            self._handle_check_ctx()

        elif self.state == State.RUN_CLAUDE:
            self._handle_run_claude()

        elif self.state == State.OBSERVE:
            self._handle_observe()

        elif self.state == State.IDLE:
            self._handle_idle()

    def _handle_init(self) -> None:
        """Initialize: check for existing prompt."""
        prompt = self.state_manager.get_prompt()
        if prompt:
            print(f"Found pending prompt: {prompt[:50]}...")
            self.state = State.CHECK_CTX
        else:
            self.state = State.IDLE

    def _handle_check_ctx(self) -> None:
        """Check context: verify workspace exists."""
        if not self.workspace.exists():
            print(f"ERROR: Workspace {self.workspace} does not exist")
            self.state_manager.mark_error("Workspace does not exist")
            self.state = State.IDLE
            return

        # Ensure .claude directory exists
        claude_dir = self.workspace / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)

        # Start new task tracking
        self.current_topic = self._generate_topic()
        self.task_start_time = time.time()
        self.last_file_snapshot = self._get_workspace_files()
        self.last_progress_time = time.time()
        self.stall_warned = False

        self.state = State.RUN_CLAUDE

    def _handle_run_claude(self) -> None:
        """Run Claude: execute prompt via Docker."""
        prompt = self.state_manager.get_prompt()
        if not prompt:
            self.state = State.IDLE
            return

        self.state_manager.mark_running()
        state = self.state_manager.load()
        iteration = state.get("iteration_count", 0) + 1
        print(f"[Iteration {iteration}] Running Claude...")

        # HOOK: EXEC_START
        if self.current_topic:
            self.reporter.exec_start(self.current_topic, iteration, prompt)

        # Execute Claude
        output, return_code = self.executor.run(prompt, str(self.workspace))

        # Update state with output
        self.state_manager.update_output(output)

        if return_code != 0 and "ERROR:" in output:
            print(f"ERROR: Claude execution failed: {output[:200]}")
            self.state_manager.mark_error(output[:500])
            self.state = State.IDLE
            return

        print(f"[Iteration {iteration}] Claude finished (exit code: {return_code})")
        self.state = State.OBSERVE

    def _handle_observe(self) -> None:
        """Observe: check if should continue or stop."""
        state = self.state_manager.load()
        output = state.get("last_output", "")
        iteration = state.get("iteration_count", 0)
        status = self.parse_status(output)

        # HOOK: EXEC_OUTPUT
        if self.current_topic:
            status_text = "STATUS: DONE" if status == "done" else "STATUS: CONTINUE"
            self.reporter.exec_output(self.current_topic, status_text)

        # HOOK: FILE_CHANGE
        changed_files = self._detect_file_changes()
        if changed_files and self.current_topic:
            self.reporter.file_change(self.current_topic, changed_files)
            self.last_progress_time = time.time()
            self.stall_warned = False

        # HOOK: STALL/WARN - check for stagnation
        if self.last_progress_time and not self.stall_warned:
            minutes_since_progress = (time.time() - self.last_progress_time) / 60
            if minutes_since_progress >= self.stall_threshold_minutes:
                if self.current_topic:
                    self.reporter.stall_warning(
                        self.current_topic,
                        int(minutes_since_progress)
                    )
                self.stall_warned = True

        if status == "done":
            print("STATUS: DONE detected - task complete")

            # HOOK: DONE
            if self.current_topic:
                self.reporter.task_done(self.current_topic, iteration)

            self.state_manager.mark_idle()
            self.current_topic = None
            self.state = State.IDLE
        else:
            print("STATUS: CONTINUE detected - looping back")
            self.state = State.RUN_CLAUDE

    def _handle_idle(self) -> None:
        """Idle: wait for new prompt."""
        time.sleep(self.idle_interval)

        # Check for new prompt
        prompt = self.state_manager.get_prompt()
        status = self.state_manager.get_status()

        if prompt and status in ("pending", "idle"):
            print(f"New prompt detected: {prompt[:50]}...")
            self.state = State.CHECK_CTX

    def stop(self) -> None:
        """Stop the daemon."""
        self.running = False


def run_daemon(
    workspace: str,
    docker_container: str = "claude-cc",
    timeout: int = 3600,
) -> None:
    """Run daemon with signal handling.

    Args:
        workspace: Path to workspace directory
        docker_container: Name of Docker container
        timeout: Claude execution timeout in seconds
    """
    # Load config and create reporter
    config = get_config()
    reporter = create_reporter(config.zulip)

    daemon = Daemon(
        workspace=Path(workspace),
        docker_container=docker_container,
        timeout=timeout,
        reporter=reporter,
    )

    def signal_handler(sig, frame):
        print("\nReceived shutdown signal...")
        daemon.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    daemon.run()
