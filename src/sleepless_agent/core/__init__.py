"""
Sleepless Agent - 核心模块

本模块包含守护进程的核心组件：
    - Daemon: 状态机守护进程主类
    - run_daemon: 便捷的守护进程启动函数
    - ClaudeExecutor: Docker 执行器
    - StateManager: JSON 状态文件管理器

使用示例:
    from sleepless_agent.core import Daemon, StateManager, ClaudeExecutor

    # 创建状态管理器
    state_manager = StateManager("./workspace")

    # 创建执行器
    executor = ClaudeExecutor(docker_container="claude-cc")

    # 运行守护进程
    from sleepless_agent.core import run_daemon
    run_daemon(workspace="./workspace")
"""

from sleepless_agent.core.daemon import Daemon, run_daemon
from sleepless_agent.core.executor import ClaudeExecutor
from sleepless_agent.core.state import StateManager

__all__ = [
    "Daemon",
    "run_daemon",
    "ClaudeExecutor",
    "StateManager",
]
