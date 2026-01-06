"""Zulip reporter - sends events to Zulip stream/topic.

This is a ONE-WAY reporter:
- Sends messages TO Zulip
- NEVER reads from Zulip
- NEVER influences execution decisions
- All exceptions are caught and logged locally
"""

import json
import urllib.request
import urllib.error
import base64
from typing import Optional


class ZulipReporter:
    """Reporter that sends events to a Zulip stream.

    Uses Zulip REST API /messages endpoint.
    All errors are caught and logged - never raises exceptions.
    """

    def __init__(
        self,
        site: str,
        email: str,
        api_key: str,
        stream: str,
    ):
        """Initialize Zulip reporter.

        Args:
            site: Zulip server URL (e.g., https://zulip.example.com)
            email: Bot email address
            api_key: Bot API key
            stream: Stream name to post messages to
        """
        self.site = site.rstrip("/")
        self.email = email
        self.api_key = api_key
        self.stream = stream
        self._auth_header = self._make_auth_header()

    def _make_auth_header(self) -> str:
        """Create Basic auth header from email and API key."""
        credentials = f"{self.email}:{self.api_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def send(self, topic: str, content: str) -> None:
        """Send a message to the Zulip stream.

        Args:
            topic: The topic within the stream
            content: The message content (Markdown supported)

        Note:
            This method NEVER raises exceptions.
            All errors are caught and logged to stderr.
        """
        try:
            self._send_message(topic, content)
        except Exception as e:
            # Log locally but never raise - Zulip failure must not affect execution
            print(f"[ZulipReporter] Failed to send message: {e}")

    def _send_message(self, topic: str, content: str) -> None:
        """Internal method to send message via Zulip API."""
        url = f"{self.site}/api/v1/messages"

        data = {
            "type": "stream",
            "to": self.stream,
            "topic": topic,
            "content": content,
        }

        # URL encode the data
        encoded_data = urllib.parse.urlencode(data).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=encoded_data,
            method="POST",
            headers={
                "Authorization": self._auth_header,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode())
                if result.get("result") != "success":
                    print(f"[ZulipReporter] API error: {result.get('msg', 'Unknown error')}")
        except urllib.error.HTTPError as e:
            print(f"[ZulipReporter] HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            print(f"[ZulipReporter] Network error: {e.reason}")
        except json.JSONDecodeError:
            print("[ZulipReporter] Invalid JSON response from Zulip")

    # Convenience methods inherited behavior from base, but we implement send()
    # The base class methods (exec_start, exec_output, etc.) call send()

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

    def file_change(self, topic: str, files: list) -> None:
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


# Import for URL encoding
import urllib.parse
