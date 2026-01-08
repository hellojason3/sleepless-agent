"""
Sleepless Agent - JSON 状态文件管理模块

本模块负责管理工作空间中的状态文件。
状态文件位置: {workspace}/.claude/state.json

状态文件结构:
    {
        "status": "running|idle|pending|error",
        "current_prompt": "待执行的提示文本",
        "workspace": "/path/to/workspace",
        "started_at": "2025-01-08T10:30:00Z",
        "last_output": "Claude 的最后输出（最多 5KB）",
        "iteration_count": 3,
        "error": "错误信息（如有）"
    }

状态值说明:
    - idle: 空闲，无任务在执行
    - pending: 有待执行的任务，尚未开始
    - running: Claude 正在执行任务
    - error: 执行过程中出现错误
"""

import json
import time
from pathlib import Path
from typing import Optional


class StateManager:
    """
    JSON 状态文件管理器

    负责状态的持久化存储和检索，提供线程安全的状态操作。
    所有状态变更都会立即写入磁盘。

    Attributes:
        workspace: 工作空间目录路径
        state_file: 状态文件的完整路径
    """

    def __init__(self, workspace: Path):
        """
        初始化状态管理器

        Args:
            workspace: 工作空间目录路径
        """
        self.workspace = Path(workspace)
        # 状态文件放在 .claude 隐藏目录下
        self.state_file = self.workspace / ".claude" / "state.json"

    def load(self) -> dict:
        """
        从 JSON 文件加载状态

        如果文件不存在或解析失败，返回默认状态。

        Returns:
            dict: 状态字典
        """
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except (json.JSONDecodeError, IOError):
                # 文件损坏时返回默认状态
                return self._default_state()
        return self._default_state()

    def save(self, data: dict) -> None:
        """
        保存状态到 JSON 文件

        会自动创建父目录（如果不存在）。

        Args:
            data: 要保存的状态字典
        """
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        # 使用缩进格式化输出，便于人类阅读
        self.state_file.write_text(json.dumps(data, indent=2))

    def _default_state(self) -> dict:
        """
        返回默认状态结构

        Returns:
            dict: 默认状态字典
        """
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
        """
        设置新的执行提示

        同时重置迭代计数和错误状态。

        Args:
            prompt: 要执行的提示文本
        """
        state = self.load()
        state["current_prompt"] = prompt
        state["status"] = "pending"
        state["iteration_count"] = 0
        state["error"] = None
        self.save(state)

    def mark_running(self) -> None:
        """
        标记状态为运行中

        同时记录开始时间（UTC 格式）。
        """
        state = self.load()
        state["status"] = "running"
        # 使用 ISO 8601 格式的 UTC 时间
        state["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.save(state)

    def mark_idle(self) -> None:
        """
        标记状态为空闲并清除提示

        用于停止当前任务。
        """
        state = self.load()
        state["status"] = "idle"
        state["current_prompt"] = None
        self.save(state)

    def mark_error(self, error: str) -> None:
        """
        标记状态为错误并记录错误信息

        Args:
            error: 错误描述信息
        """
        state = self.load()
        state["status"] = "error"
        state["error"] = error
        self.save(state)

    def update_output(self, output: str) -> None:
        """
        更新最后输出并递增迭代计数

        输出会被截断为最多 5KB，避免状态文件过大。

        Args:
            output: Claude 的输出文本
        """
        state = self.load()
        # 只保留最后 5KB
        state["last_output"] = output[-5000:] if len(output) > 5000 else output
        # 递增迭代计数
        state["iteration_count"] = state.get("iteration_count", 0) + 1
        self.save(state)

    def get_prompt(self) -> Optional[str]:
        """
        获取当前待执行的提示

        Returns:
            str | None: 当前提示，如果没有则返回 None
        """
        return self.load().get("current_prompt")

    def get_status(self) -> str:
        """
        获取当前状态

        Returns:
            str: 状态值，默认为 "idle"
        """
        return self.load().get("status", "idle")

    def check_done_flag(self) -> bool:
        """
        检查并消费完成标志文件

        这是另一种指示任务完成的方式。
        如果 .claude/done.flag 文件存在，删除它并返回 True。

        Returns:
            bool: 如果标志文件存在返回 True，否则返回 False
        """
        done_flag = self.workspace / ".claude" / "done.flag"
        if done_flag.exists():
            done_flag.unlink()  # 删除标志文件
            return True
        return False
