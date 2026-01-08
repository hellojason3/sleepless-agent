"""
Sleepless Agent - 状态机守护进程模块

本模块实现核心守护进程，使用状态机模式循环执行 Claude Code。

状态机流转:
    ┌─────────┐    ┌───────────┐    ┌─────────────┐    ┌─────────┐
    │  INIT   │───▶│ CHECK_CTX │───▶│ RUN_CLAUDE  │───▶│ OBSERVE │
    └─────────┘    └───────────┘    └─────────────┘    └────┬────┘
                                                     │
                            ┌────────────────────────┴────────────────┐
                            │                                          │
                            ▼                                          ▼
                     STATUS: CONTINUE                           STATUS: DONE
                            │                                          │
                            └──────▶ RUN_CLAUDE                  ▼
                                                              IDLE

生命周期钩子（可选的 Reporter）:
    - EXEC_START: Claude 执行前触发
    - EXEC_OUTPUT: Claude 返回输出后触发
    - FILE_CHANGE: 检测到文件变化时触发
    - STALL/WARN: 长时间无进度时触发
    - DONE: 任务完成时触发
"""

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
    """
    守护进程状态机状态枚举

    状态说明:
        - INIT: 初始化状态，检查是否有待执行的提示
        - CHECK_CTX: 检查上下文，验证工作空间是否就绪
        - RUN_CLAUDE: 运行 Claude，执行当前提示
        - OBSERVE: 观察状态，解析输出并决定下一步
        - IDLE: 空闲状态，等待新提示
    """
    INIT = "init"
    CHECK_CTX = "check_ctx"
    RUN_CLAUDE = "run_claude"
    OBSERVE = "observe"
    IDLE = "idle"


def create_reporter(zulip_config: ZulipConfig) -> BaseReporter:
    """
    根据配置创建适当的报告器

    优先级:
        1. 如果 Zulip 配置完整有效，返回 ZulipReporter
        2. 否则返回 NoopReporter（空操作）

    Args:
        zulip_config: Zulip 配置对象

    Returns:
        BaseReporter: 报告器实例
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
    """
    极简 Claude Code 监督守护进程

    使用状态机模式持续执行 Claude Code，直到任务完成。

    状态转换:
        INIT -> CHECK_CTX -> RUN_CLAUDE -> OBSERVE -> (loop or IDLE)

    Attributes:
        workspace: 工作空间目录路径
        docker_container: Docker 容器名称
        timeout: Claude 执行超时时间（秒）
        idle_interval: 空闲时休眠间隔（秒）
        reporter: 可观测性报告器
        stall_threshold_minutes: 停滞检测阈值（分钟）
        state: 当前状态机状态
        running: 是否正在运行
        state_manager: 状态文件管理器
        executor: Claude 执行器
        current_topic: 当前任务的唯一标识符
        task_start_time: 任务开始时间戳
        last_file_snapshot: 上次文件快照
        last_progress_time: 上次检测到进度的时间
        stall_warned: 是否已发出停滞警告
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
        """
        初始化守护进程

        Args:
            workspace: 工作空间目录路径
            docker_container: Docker 容器名称
            timeout: Claude 执行超时时间（秒）
            idle_interval: 空闲时休眠秒数
            reporter: 可观测性报告器（可选）
            stall_threshold_minutes: 无进度警告阈值（分钟）
        """
        self.workspace = Path(workspace).resolve()
        self.docker_container = docker_container
        self.timeout = timeout
        self.idle_interval = idle_interval
        self.stall_threshold_minutes = stall_threshold_minutes

        # 状态机初始化
        self.state = State.INIT
        self.running = False

        # 核心组件
        self.state_manager = StateManager(self.workspace)
        self.executor = ClaudeExecutor(docker_container, timeout)
        # 如果没有提供报告器，使用空操作报告器
        self.reporter = reporter or NoopReporter()

        # 任务跟踪（用于可观测性和停滞检测）
        self.current_topic: Optional[str] = None
        self.task_start_time: Optional[float] = None
        self.last_file_snapshot: Set[str] = set()
        self.last_progress_time: Optional[float] = None
        self.stall_warned: bool = False

    def _generate_topic(self) -> str:
        """
        生成当前任务的唯一主题标识符

        格式: task-{timestamp}-{prompt_hash}
        例如: task-20250108-143052-a1b2c3

        Returns:
            str: 唯一的主题字符串
        """
        # 当前 UTC 时间戳
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        # 使用提示 MD5 哈希的前 6 位作为唯一后缀
        prompt = self.state_manager.get_prompt() or ""
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:6]
        return f"task-{timestamp}-{prompt_hash}"

    def _get_workspace_files(self) -> Set[str]:
        """
        获取工作空间中的所有文件（包含修改时间）

        返回格式: {"path/to/file:timestamp", ...}
        包含 mtime 是为了检测文件内容变化。

        Returns:
            Set[str]: 文件标识符集合
        """
        files = set()
        try:
            for path in self.workspace.rglob("*"):
                # 跳过 .git 目录和非文件项
                if path.is_file() and ".git" not in path.parts:
                    # 包含修改时间以检测内容变化
                    mtime = path.stat().st_mtime
                    files.add(f"{path.relative_to(self.workspace)}:{mtime}")
        except Exception:
            pass
        return files

    def _detect_file_changes(self) -> list:
        """
        检测自上次检查以来的变化文件

        通过比较文件名和 mtime 来检测变化。

        Returns:
            list: 变化文件列表（相对于工作空间的路径）
        """
        current_files = self._get_workspace_files()

        # 提取文件名（不含 mtime）用于比较
        current_names = {f.rsplit(":", 1)[0] for f in current_files}
        last_names = {f.rsplit(":", 1)[0] for f in self.last_file_snapshot}

        # 找出变化或新增的文件
        changed = []
        for f in current_files:
            name = f.rsplit(":", 1)[0]
            if f not in self.last_file_snapshot:
                changed.append(name)

        # 更新快照
        self.last_file_snapshot = current_files
        return changed

    def parse_status(self, output: str) -> str:
        """
        解析 Claude 输出中的续传信号

        检测顺序（优先级从高到低）:
            1. "STATUS: DONE" → 返回 "done"
            2. "STATUS: CONTINUE" → 返回 "continue"
            3. .claude/done.flag 文件存在 → 返回 "done"
            4. 默认 → 返回 "continue"

        只检查最后 20 行输出，避免误报。

        Args:
            output: Claude 的 stdout 输出

        Returns:
            str: "done" 或 "continue"
        """
        # 检查最后 20 行中的状态标记
        lines = output.strip().split("\n")
        for line in reversed(lines[-20:]):
            if "STATUS: DONE" in line:
                return "done"
            if "STATUS: CONTINUE" in line:
                return "continue"

        # 检查完成标志文件
        if self.state_manager.check_done_flag():
            return "done"

        # 默认继续执行
        return "continue"

    def run(self) -> None:
        """
        运行守护进程主循环

        启动前验证 Docker 容器状态，然后进入状态机循环。
        支持 Ctrl+C 优雅退出。
        """
        self.running = True
        print(f"Daemon started with workspace: {self.workspace}")
        print(f"Docker container: {self.docker_container}")

        # 启动前验证 Docker 容器
        if not self.executor.check_docker():
            print(f"ERROR: Docker container '{self.docker_container}' is not running")
            return

        # 主循环
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
        """
        执行状态机的一个步骤

        根据当前状态调用相应的处理方法。
        """
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
        """
        处理 INIT 状态

        检查是否有待执行的提示：
            - 有提示 → 进入 CHECK_CTX 状态
            - 无提示 → 进入 IDLE 状态
        """
        prompt = self.state_manager.get_prompt()
        if prompt:
            print(f"Found pending prompt: {prompt[:50]}...")
            self.state = State.CHECK_CTX
        else:
            self.state = State.IDLE

    def _handle_check_ctx(self) -> None:
        """
        处理 CHECK_CTX 状态

        验证工作空间存在，初始化任务跟踪。
        """
        # 验证工作空间
        if not self.workspace.exists():
            print(f"ERROR: Workspace {self.workspace} does not exist")
            self.state_manager.mark_error("Workspace does not exist")
            self.state = State.IDLE
            return

        # 确保 .claude 目录存在
        claude_dir = self.workspace / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)

        # 初始化任务跟踪
        self.current_topic = self._generate_topic()
        self.task_start_time = time.time()
        self.last_file_snapshot = self._get_workspace_files()
        self.last_progress_time = time.time()
        self.stall_warned = False

        self.state = State.RUN_CLAUDE

    def _handle_run_claude(self) -> None:
        """
        处理 RUN_CLAUDE 状态

        执行当前提示，更新状态文件，触发 EXEC_START 钩子。
        """
        prompt = self.state_manager.get_prompt()
        if not prompt:
            self.state = State.IDLE
            return

        # 标记为运行状态
        self.state_manager.mark_running()
        state = self.state_manager.load()
        iteration = state.get("iteration_count", 0) + 1
        print(f"[Iteration {iteration}] Running Claude...")

        # 钩子: EXEC_START
        if self.current_topic:
            self.reporter.exec_start(self.current_topic, iteration, prompt)

        # 执行 Claude
        output, return_code = self.executor.run(prompt, str(self.workspace))

        # 更新输出到状态文件
        self.state_manager.update_output(output)

        # 检查执行结果
        if return_code != 0 and "ERROR:" in output:
            print(f"ERROR: Claude execution failed: {output[:200]}")
            self.state_manager.mark_error(output[:500])
            self.state = State.IDLE
            return

        print(f"[Iteration {iteration}] Claude finished (exit code: {return_code})")
        self.state = State.OBSERVE

    def _handle_observe(self) -> None:
        """
        处理 OBSERVE 状态

        解析输出，检测文件变化，检查停滞，决定继续或停止。
        触发多个钩子: EXEC_OUTPUT, FILE_CHANGE, STALL/WARN, DONE
        """
        state = self.state_manager.load()
        output = state.get("last_output", "")
        iteration = state.get("iteration_count", 0)

        # 解析状态信号
        status = self.parse_status(output)

        # 钩子: EXEC_OUTPUT
        if self.current_topic:
            status_text = "STATUS: DONE" if status == "done" else "STATUS: CONTINUE"
            self.reporter.exec_output(self.current_topic, status_text)

        # 钩子: FILE_CHANGE
        changed_files = self._detect_file_changes()
        if changed_files and self.current_topic:
            self.reporter.file_change(self.current_topic, changed_files)
            self.last_progress_time = time.time()
            self.stall_warned = False

        # 钩子: STALL/WARN - 检查停滞
        if self.last_progress_time and not self.stall_warned:
            minutes_since_progress = (time.time() - self.last_progress_time) / 60
            if minutes_since_progress >= self.stall_threshold_minutes:
                if self.current_topic:
                    self.reporter.stall_warning(
                        self.current_topic,
                        int(minutes_since_progress)
                    )
                self.stall_warned = True

        # 根据状态决定下一步
        if status == "done":
            print("STATUS: DONE detected - task complete")

            # 钩子: DONE
            if self.current_topic:
                self.reporter.task_done(self.current_topic, iteration)

            self.state_manager.mark_idle()
            self.current_topic = None
            self.state = State.IDLE
        else:
            print("STATUS: CONTINUE detected - looping back")
            self.state = State.RUN_CLAUDE

    def _handle_idle(self) -> None:
        """
        处理 IDLE 状态

        休眠等待，定期检查是否有新提示。
        """
        time.sleep(self.idle_interval)

        # 检查新提示
        prompt = self.state_manager.get_prompt()
        status = self.state_manager.get_status()

        if prompt and status in ("pending", "idle"):
            print(f"New prompt detected: {prompt[:50]}...")
            self.state = State.CHECK_CTX

    def stop(self) -> None:
        """
        停止守护进程

        设置 running 标志为 False，主循环将退出。
        """
        self.running = False


def run_daemon(
    workspace: str,
    docker_container: str = "claude-cc",
    timeout: int = 3600,
) -> None:
    """
    运行守护进程（带信号处理）

    创建守护进程实例，注册信号处理器，启动主循环。

    支持的信号:
        - SIGINT: Ctrl+C
        - SIGTERM: 终止信号

    Args:
        workspace: 工作空间目录路径
        docker_container: Docker 容器名称
        timeout: Claude 执行超时时间（秒）
    """
    # 加载配置并创建报告器
    config = get_config()
    reporter = create_reporter(config.zulip)

    # 创建守护进程
    daemon = Daemon(
        workspace=Path(workspace),
        docker_container=docker_container,
        timeout=timeout,
        reporter=reporter,
    )

    # 注册信号处理器
    def signal_handler(sig, frame):
        """信号处理函数"""
        print("\nReceived shutdown signal...")
        daemon.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 启动主循环
    daemon.run()
