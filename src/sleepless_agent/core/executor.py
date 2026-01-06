"""Minimal Claude Code executor via Docker subprocess."""

import subprocess
from typing import Tuple


class ClaudeExecutor:
    """Execute Claude Code via Docker subprocess."""

    def __init__(
        self,
        docker_container: str = "claude-cc",
        timeout: int = 3600,
    ):
        """Initialize executor.

        Args:
            docker_container: Name of Docker container running Claude Code
            timeout: Execution timeout in seconds
        """
        self.docker_container = docker_container
        self.timeout = timeout

    def run(self, prompt: str, cwd: str = "/workspace") -> Tuple[str, int]:
        """Execute Claude with prompt via docker exec.

        Args:
            prompt: The prompt to send to Claude
            cwd: Working directory inside container

        Returns:
            Tuple of (stdout, return_code)
        """
        cmd = [
            "docker", "exec",
            "-w", cwd,
            self.docker_container,
            "claude", "-p", prompt,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            return result.stdout + result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "ERROR: Timeout expired", -1
        except Exception as e:
            return f"ERROR: {str(e)}", -1

    def check_docker(self) -> bool:
        """Check if Docker container is running."""
        cmd = [
            "docker", "inspect",
            "-f", "{{.State.Running}}",
            self.docker_container,
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip() == "true"
        except Exception:
            return False

    def check_claude(self) -> bool:
        """Check if Claude CLI is available in container."""
        cmd = [
            "docker", "exec",
            self.docker_container,
            "claude", "--version",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False
