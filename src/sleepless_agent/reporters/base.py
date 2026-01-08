"""
Sleepless Agent - 基础报告器接口模块

本模块定义了报告器的抽象接口和空操作实现。

设计原则:
    1. 单向通信: Sleepless Agent → 外部系统（仅输出）
    2. 不影响执行: 报告器故障绝不能中断任务执行
    3. 异常安全: 所有方法必须捕获异常，永不抛出

报告器接口:
    - send(): 核心发送方法，由子类实现
    - exec_start(): 报告执行开始事件
    - exec_output(): 报告输出事件
    - file_change(): 报告文件变化事件
    - stall_warning(): 报告停滞警告
    - task_done(): 报告任务完成事件
"""

from abc import ABC, abstractmethod
from typing import List, Optional


class BaseReporter(ABC):
    """
    报告器基类（抽象接口）

    所有报告器必须继承此类并实现 send() 方法。

    重要约束:
        - 绝不从外部系统读取消息
        - 绝不影响执行决策
        - 绝不抛出异常（必须内部捕获）

    使用示例:
        class MyReporter(BaseReporter):
            def send(self, topic: str, content: str) -> None:
                try:
                    my_api.send(topic, content)
                except Exception as e:
                    print(f"Report failed: {e}")
    """

    @abstractmethod
    def send(self, topic: str, content: str) -> None:
        """
        发送消息到报告系统（抽象方法）

        子类必须实现此方法。

        重要:
            - 此方法必须永不抛出异常
            - 所有错误必须被捕获并本地记录
            - 失败不应影响主流程执行

        Args:
            topic: 消息主题/线程标识符
            content: 消息内容
        """
        pass

    def exec_start(self, topic: str, iteration: int, prompt: str) -> None:
        """
        报告执行开始事件

        在 Claude 执行前触发。

        Args:
            topic: 任务主题标识符
            iteration: 迭代次数
            prompt: 执行的提示文本
        """
        # 截断过长的提示以避免消息过大
        preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
        self.send(topic, f"▶️ EXEC #{iteration} started\nPrompt: {preview}")

    def exec_output(self, topic: str, status: str, output_preview: str = "") -> None:
        """
        报告 Claude 输出事件

        在 Claude 返回输出后触发。

        Args:
            topic: 任务主题标识符
            status: 状态信号（如 "STATUS: DONE"）
            output_preview: 输出预览（可选）
        """
        content = f"🧠 Claude output:\n{status}"
        if output_preview:
            content += f"\n```\n{output_preview[:500]}\n```"
        self.send(topic, content)

    def file_change(self, topic: str, files: List[str]) -> None:
        """
        报告文件变化事件

        检测到工作空间文件变化时触发。

        Args:
            topic: 任务主题标识符
            files: 变化文件列表
        """
        if not files:
            return
        # 限制显示的文件数量
        file_list = "\n".join(f"- {f}" for f in files[:20])
        if len(files) > 20:
            file_list += f"\n... and {len(files) - 20} more"
        self.send(topic, f"📁 Files modified:\n{file_list}")

    def stall_warning(self, topic: str, minutes: int) -> None:
        """
        报告停滞警告事件

        长时间无进度时触发。

        Args:
            topic: 任务主题标识符
            minutes: 无进度的分钟数
        """
        self.send(topic, f"⚠️ No progress detected for {minutes} minutes")

    def task_done(self, topic: str, iterations: int) -> None:
        """
        报告任务完成事件

        检测到 STATUS: DONE 时触发。

        Args:
            topic: 任务主题标识符
            iterations: 总迭代次数
        """
        self.send(topic, f"✅ Task completed after {iterations} iterations")


class NoopReporter(BaseReporter):
    """
    空操作报告器

    当报告功能禁用时使用。
    所有方法为空操作，不产生任何输出。

    使用场景:
        - 未配置 Zulip
        - 本地测试不需要可观测性
        - 作为默认报告器实现
    """

    def send(self, topic: str, content: str) -> None:
        """
        空操作发送方法

        什么都不做，直接返回。

        Args:
            topic: 任务主题标识符（忽略）
            content: 消息内容（忽略）
        """
        pass
