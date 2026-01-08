"""
Sleepless Agent - 报告器模块

本模块包含所有报告器实现，用于任务可观测性。

报告器类型:
    - BaseReporter: 抽象基类，定义报告器接口
    - NoopReporter: 空操作报告器，禁用报告时使用
    - ZulipReporter: Zulip 集成报告器

设计原则:
    1. 单向通信: 仅向外发送消息，绝不读取
    2. 异常安全: 报告器故障不影响主流程
    3. 可扩展: 可轻松添加新的报告目标

使用示例:
    from sleepless_agent.reporters import ZulipReporter, NoopReporter

    # 启用 Zulip 报告
    reporter = ZulipReporter(site="...", email="...", api_key="...", stream="...")

    # 禁用报告
    reporter = NoopReporter()
"""

from sleepless_agent.reporters.base import BaseReporter, NoopReporter
from sleepless_agent.reporters.zulip_reporter import ZulipReporter

__all__ = [
    "BaseReporter",
    "NoopReporter",
    "ZulipReporter",
]
