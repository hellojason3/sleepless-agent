"""
Sleepless Agent - Claude Code 持续执行监控运行时

一个极简的守护进程，用于保持 Claude Code 持续运行直到任务完成。

主要特性:
    - 状态机驱动的执行循环
    - 基于 JSON 文件的状态持久化
    - Docker 容器集成
    - 可选的 Zulip 可观测性报告

版本: 1.0.0
许可: MIT
仓库: https://github.com/context-machine-lab/sleepless-agent
"""

__version__ = "1.0.0"
