"""JSON state file management for the minimal supervisor runtime."""

import json
import time
from pathlib import Path
from typing import Optional


class StateManager:
    """Manages the JSON state file in the workspace."""

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self.state_file = self.workspace / ".claude" / "state.json"

    def load(self) -> dict:
        """Load state from JSON file, returning defaults if not exists."""
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except (json.JSONDecodeError, IOError):
                return self._default_state()
        return self._default_state()

    def save(self, data: dict) -> None:
        """Save state to JSON file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(data, indent=2))

    def _default_state(self) -> dict:
        """Return default state structure."""
        return {
            "status": "idle",
            "current_prompt": None,
            "workspace": str(self.workspace),
            "started_at": None,
            "last_output": None,
            "iteration_count": 0,
            "error": None,
        }

    def set_prompt(self, prompt: str) -> None:
        """Set a new prompt to execute."""
        state = self.load()
        state["current_prompt"] = prompt
        state["status"] = "pending"
        state["iteration_count"] = 0
        state["error"] = None
        self.save(state)

    def mark_running(self) -> None:
        """Mark state as running."""
        state = self.load()
        state["status"] = "running"
        state["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.save(state)

    def mark_idle(self) -> None:
        """Mark state as idle and clear prompt."""
        state = self.load()
        state["status"] = "idle"
        state["current_prompt"] = None
        self.save(state)

    def mark_error(self, error: str) -> None:
        """Mark state as error with message."""
        state = self.load()
        state["status"] = "error"
        state["error"] = error
        self.save(state)

    def update_output(self, output: str) -> None:
        """Update last output (truncated to 5KB)."""
        state = self.load()
        state["last_output"] = output[-5000:] if len(output) > 5000 else output
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        self.save(state)

    def get_prompt(self) -> Optional[str]:
        """Get current prompt if any."""
        return self.load().get("current_prompt")

    def get_status(self) -> str:
        """Get current status."""
        return self.load().get("status", "idle")

    def check_done_flag(self) -> bool:
        """Check and consume .claude/done.flag file."""
        done_flag = self.workspace / ".claude" / "done.flag"
        if done_flag.exists():
            done_flag.unlink()
            return True
        return False
