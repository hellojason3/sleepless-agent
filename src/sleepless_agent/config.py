"""Minimal configuration for Claude Code Supervisor Runtime."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ZulipConfig:
    """Zulip reporter configuration."""
    enabled: bool
    site: Optional[str]
    email: Optional[str]
    api_key: Optional[str]
    stream: Optional[str]

    @classmethod
    def from_env(cls) -> "ZulipConfig":
        """Load Zulip config from environment variables."""
        enabled = os.getenv("ZULIP_ENABLED", "").lower() == "true"
        return cls(
            enabled=enabled,
            site=os.getenv("ZULIP_SITE"),
            email=os.getenv("ZULIP_EMAIL"),
            api_key=os.getenv("ZULIP_API_KEY"),
            stream=os.getenv("ZULIP_STREAM"),
        )

    def is_valid(self) -> bool:
        """Check if all required Zulip settings are present."""
        return bool(
            self.enabled
            and self.site
            and self.email
            and self.api_key
            and self.stream
        )


@dataclass
class Config:
    """Runtime configuration."""
    workspace: Path
    docker_container: str
    timeout_seconds: int
    zulip: ZulipConfig

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """Load configuration from YAML file and environment.

        Priority (highest to lowest):
        1. Environment variables (SLEEPLESS_*, ZULIP_*)
        2. Config file
        3. Defaults

        Args:
            config_path: Optional path to config YAML file
        """
        # Defaults
        workspace = Path("./workspace")
        docker_container = "claude-cc"
        timeout_seconds = 3600

        # Load from config file if exists
        if config_path and config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
                workspace = Path(data.get("workspace", workspace))
                docker_container = data.get("docker_container", docker_container)
                timeout_seconds = data.get("timeout_seconds", timeout_seconds)

        # Environment overrides
        if env_workspace := os.getenv("SLEEPLESS_WORKSPACE"):
            workspace = Path(env_workspace)
        if env_container := os.getenv("SLEEPLESS_CONTAINER"):
            docker_container = env_container
        if env_timeout := os.getenv("SLEEPLESS_TIMEOUT"):
            timeout_seconds = int(env_timeout)

        # Load Zulip config from environment
        zulip = ZulipConfig.from_env()

        return cls(
            workspace=workspace.resolve(),
            docker_container=docker_container,
            timeout_seconds=timeout_seconds,
            zulip=zulip,
        )


def get_config(config_path: Optional[Path] = None) -> Config:
    """Get configuration singleton."""
    return Config.load(config_path)
