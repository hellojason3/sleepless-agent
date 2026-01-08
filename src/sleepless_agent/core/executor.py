"""
Sleepless Agent - Docker 执行器模块

本模块负责通过 Docker 子进程执行 Claude Code CLI。
不直接运行 Claude，而是调用 docker exec 命令在容器中执行。

执行流程:
    1. 构建 docker exec 命令
    2. 启动子进程执行
    3. 捕获 stdout 和 stderr
    4. 返回组合输出和退出码

实际执行的命令格式:
    docker exec -w /workspace claude-cc claude -p "prompt"
"""

import subprocess
from typing import Tuple


class ClaudeExecutor:
    """
    Claude Code Docker 执行器

    通过 Docker 子进程调用 Claude Code CLI。
    支持超时控制和环境验证。

    Attributes:
        docker_container: Docker 容器名称
        timeout: 执行超时时间（秒）
    """

    def __init__(
        self,
        docker_container: str = "claude-cc",
        timeout: int = 3600,
    ):
        """
        初始化执行器

        Args:
            docker_container: 运行 Claude Code 的 Docker 容器名称
            timeout: 执行超时时间（秒），默认 1 小时
        """
        self.docker_container = docker_container
        self.timeout = timeout

    def run(self, prompt: str, cwd: str = "/workspace") -> Tuple[str, int]:
        """
        通过 Docker 执行 Claude

        构建并执行命令:
            docker exec -w {cwd} {container} claude -p "{prompt}"

        Args:
            prompt: 发送给 Claude 的提示文本
            cwd: 容器内的工作目录

        Returns:
            Tuple[str, int]: (输出文本, 退出码)
                - 输出文本包含 stdout + stderr
                - 退出码: 0=成功, -1=超时或异常, 其他=Claude 退出码

        错误处理:
            - 超时: 返回 "ERROR: Timeout expired", -1
            - 异常: 返回 "ERROR: {异常信息}", -1
        """
        # 构建 docker exec 命令
        cmd = [
            "docker", "exec",
            "-w", cwd,
            self.docker_container,
            "claude", "-p", prompt,
        ]

        try:
            # 执行命令并捕获输出
            result = subprocess.run(
                cmd,
                capture_output=True,  # 捕获 stdout 和 stderr
                text=True,            # 返回字符串而非字节
                timeout=self.timeout,  # 设置超时
            )
            # 合并 stdout 和 stderr
            return result.stdout + result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            # 超时处理
            return "ERROR: Timeout expired", -1
        except Exception as e:
            # 其他异常处理
            return f"ERROR: {str(e)}", -1

    def check_docker(self) -> bool:
        """
        检查 Docker 容器是否正在运行

        使用 docker inspect 命令检查容器状态。

        Returns:
            bool: 容器运行中返回 True，否则返回 False
        """
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
            # 检查输出是否为 "true"
            return result.stdout.strip() == "true"
        except Exception:
            # 任何异常都认为容器不可用
            return False

    def check_claude(self) -> bool:
        """
        检查容器内 Claude CLI 是否可用

        通过执行 claude --version 命令验证。

        Returns:
            bool: Claude 可用返回 True，否则返回 False
        """
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
            # 退出码为 0 表示命令成功执行
            return result.returncode == 0
        except Exception:
            return False
