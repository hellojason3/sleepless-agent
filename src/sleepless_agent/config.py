"""
Sleepless Agent - 配置管理模块

本模块负责加载和管理应用程序配置。
配置优先级（从高到低）:
    1. 环境变量 (SLEEPLESS_*, ZULIP_*)
    2. YAML 配置文件
    3. 默认值

配置项说明:
    工作空间配置:
        - workspace: 工作空间目录路径
        - docker_container: Docker 容器名称
        - timeout_seconds: 执行超时秒数

    Zulip 报告配置:
        - enabled: 是否启用 Zulip 报告
        - site: Zulip 服务器 URL
        - email: 机器人邮箱地址
        - api_key: API 密钥
        - stream: 目标流名称
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class ZulipConfig:
    """
    Zulip 报告器配置数据类

    Attributes:
        enabled: 是否启用 Zulip 报告功能
        site: Zulip 服务器 URL（如: https://org.zulipchat.com）
        email: 机器人的邮箱地址
        api_key: Zulip API 密钥
        stream: 目标流名称
    """
    enabled: bool
    site: Optional[str]
    email: Optional[str]
    api_key: Optional[str]
    stream: Optional[str]

    @classmethod
    def from_env(cls) -> "ZulipConfig":
        """
        从环境变量加载 Zulip 配置

        读取的环境变量:
            - ZULIP_ENABLED: "true" 时启用（不区分大小写）
            - ZULIP_SITE: Zulip 服务器 URL
            - ZULIP_EMAIL: 机器人邮箱
            - ZULIP_API_KEY: API 密钥
            - ZULIP_STREAM: 流名称

        Returns:
            ZulipConfig: 加载的配置对象
        """
        enabled = os.getenv("ZULIP_ENABLED", "").lower() == "true"
        return cls(
            enabled=enabled,
            site=os.getenv("ZULIP_SITE"),
            email=os.getenv("ZULIP_EMAIL"),
            api_key=os.getenv("ZULIP_API_KEY"),
            stream=os.getenv("ZULIP_STREAM"),
        )

    def is_valid(self) -> bool:
        """
        检查 Zulip 配置是否完整有效

        Returns:
            bool: 当且仅当 enabled=True 且所有必需字段都非空时返回 True
        """
        return bool(
            self.enabled
            and self.site
            and self.email
            and self.api_key
            and self.stream
        )


@dataclass
class Config:
    """
    运行时配置数据类

    Attributes:
        workspace: 工作空间目录路径（Path 对象）
        docker_container: Docker 容器名称
        timeout_seconds: Claude 执行超时时间（秒）
        zulip: Zulip 报告器配置
    """
    workspace: Path
    docker_container: str
    timeout_seconds: int
    zulip: ZulipConfig

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """
        加载配置（支持多来源合并）

        加载优先级（后加载的覆盖先加载的）:
            1. 默认值
            2. YAML 配置文件（如果提供且存在）
            3. 环境变量

        Args:
            config_path: YAML 配置文件路径（可选）

        Returns:
            Config: 加载的配置对象

        示例 YAML 文件格式:
            workspace: ./workspace
            docker_container: claude-cc
            timeout_seconds: 3600
        """
        # 1. 设置默认值
        workspace = Path("./workspace")
        docker_container = "claude-cc"
        timeout_seconds = 3600

        # 2. 从配置文件加载（如果存在）
        if config_path and config_path.exists():
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
                workspace = Path(data.get("workspace", workspace))
                docker_container = data.get("docker_container", docker_container)
                timeout_seconds = data.get("timeout_seconds", timeout_seconds)

        # 3. 环境变量覆盖
        if env_workspace := os.getenv("SLEEPLESS_WORKSPACE"):
            workspace = Path(env_workspace)
        if env_container := os.getenv("SLEEPLESS_CONTAINER"):
            docker_container = env_container
        if env_timeout := os.getenv("SLEEPLESS_TIMEOUT"):
            timeout_seconds = int(env_timeout)

        # 4. 加载 Zulip 配置（仅从环境变量）
        zulip = ZulipConfig.from_env()

        return cls(
            workspace=workspace.resolve(),
            docker_container=docker_container,
            timeout_seconds=timeout_seconds,
            zulip=zulip,
        )


def get_config(config_path: Optional[Path] = None) -> Config:
    """
    获取配置单例（便捷函数）

    Args:
        config_path: YAML 配置文件路径（可选）

    Returns:
        Config: 加载的配置对象
    """
    return Config.load(config_path)
