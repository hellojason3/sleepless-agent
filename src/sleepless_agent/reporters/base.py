"""Base reporter interface and NoopReporter implementation."""

from abc import ABC, abstractmethod
from typing import List, Optional


class BaseReporter(ABC):
    """Base class for all reporters.

    Reporters are one-way: Sleepless -> External System.
    They must NEVER:
    - Read messages from external systems
    - Influence execution decisions
    - Raise exceptions that interrupt task execution
    """

    @abstractmethod
    def send(self, topic: str, content: str) -> None:
        """Send a message to the reporting system.

        Args:
            topic: The topic/thread identifier for the message
            content: The message content

        Note:
            This method must NEVER raise exceptions.
            All errors must be caught and logged locally.
        """
        pass

    def exec_start(self, topic: str, iteration: int, prompt: str) -> None:
        """Report execution start event."""
        preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
        self.send(topic, f"▶️ EXEC #{iteration} started\nPrompt: {preview}")

    def exec_output(self, topic: str, status: str, output_preview: str = "") -> None:
        """Report Claude output event."""
        content = f"🧠 Claude output:\n{status}"
        if output_preview:
            content += f"\n```\n{output_preview[:500]}\n```"
        self.send(topic, content)

    def file_change(self, topic: str, files: List[str]) -> None:
        """Report file change event."""
        if not files:
            return
        file_list = "\n".join(f"- {f}" for f in files[:20])
        if len(files) > 20:
            file_list += f"\n... and {len(files) - 20} more"
        self.send(topic, f"📁 Files modified:\n{file_list}")

    def stall_warning(self, topic: str, minutes: int) -> None:
        """Report stall/warning event."""
        self.send(topic, f"⚠️ No progress detected for {minutes} minutes")

    def task_done(self, topic: str, iterations: int) -> None:
        """Report task completion event."""
        self.send(topic, f"✅ Task completed after {iterations} iterations")


class NoopReporter(BaseReporter):
    """No-operation reporter - used when reporting is disabled."""

    def send(self, topic: str, content: str) -> None:
        """Do nothing - reporting is disabled."""
        pass
