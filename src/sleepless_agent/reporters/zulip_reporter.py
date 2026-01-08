"""
Sleepless Agent - Zulip 报告器模块

本模块实现向 Zulip 发送事件消息的报告器。

重要特性:
    1. 单向通信: 仅向 Zulip 发送消息，从不读取
    2. 异常安全: 所有错误被捕获，不影响主流程
    3. 使用 Basic Auth: 通过 email:api_key 进行认证

Zulip API 端点:
    POST /api/v1/messages

请求格式:
    type: "stream"
    to: "stream_name"
    topic: "topic_name"
    content: "message_content"

环境变量配置:
    ZULIP_ENABLED=true
    ZULIP_SITE=https://your-org.zulipchat.com
    ZULIP_EMAIL=sleepless-bot@your-org.zulipchat.com
    ZULIP_API_KEY=your_api_key
    ZULIP_STREAM=sleepless
"""

import json
import urllib.request
import urllib.error
import base64
from typing import Optional


class ZulipReporter:
    """
    Zulip 报告器

    将事件消息发送到 Zulip 流，用于任务可观测性。

    使用 Zulip REST API 的 /messages 端点。
    所有错误被捕获并打印到 stderr，永不抛出异常。

    Attributes:
        site: Zulip 服务器 URL（如 https://org.zulipchat.com）
        email: 机器人邮箱地址
        api_key: Zulip API 密钥
        stream: 目标流名称
        _auth_header: HTTP Basic Auth 认证头

    使用示例:
        reporter = ZulipReporter(
            site="https://example.zulipchat.com",
            email="bot@example.com",
            api_key="xxx",
            stream="tasks"
        )
        reporter.task_done("task-123", 5)
    """

    def __init__(
        self,
        site: str,
        email: str,
        api_key: str,
        stream: str,
    ):
        """
        初始化 Zulip 报告器

        Args:
            site: Zulip 服务器 URL
            email: 机器人邮箱地址
            api_key: Zulip API 密钥
            stream: 目标流名称
        """
        self.site = site.rstrip("/")
        self.email = email
        self.api_key = api_key
        self.stream = stream
        # 预先生成认证头
        self._auth_header = self._make_auth_header()

    def _make_auth_header(self) -> str:
        """
        创建 HTTP Basic 认证头

        格式: Basic base64(email:api_key)

        Returns:
            str: HTTP Authorization 头值
        """
        credentials = f"{self.email}:{self.api_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def send(self, topic: str, content: str) -> None:
        """
        发送消息到 Zulip 流

        公共方法，被其他报告方法调用。
        所有异常被捕获，永不抛出。

        Args:
            topic: Zulip 消息主题
            content: 消息内容（支持 Markdown）
        """
        try:
            self._send_message(topic, content)
        except Exception as e:
            # 记录错误但不抛出，确保不影响主流程
            print(f"[ZulipReporter] Failed to send message: {e}")

    def _send_message(self, topic: str, content: str) -> None:
        """
        内部方法：通过 Zulip API 发送消息

        发送 POST 请求到 /api/v1/messages 端点。

        Args:
            topic: Zulip 消息主题
            content: 消息内容

        Raises:
            urllib.error.HTTPError: HTTP 错误（会被 send() 捕获）
            urllib.error.URLError: 网络错误（会被 send() 捕获）
        """
        url = f"{self.site}/api/v1/messages"

        # 构建请求数据
        data = {
            "type": "stream",
            "to": self.stream,
            "topic": topic,
            "content": content,
        }

        # URL 编码数据
        encoded_data = urllib.parse.urlencode(data).encode("utf-8")

        # 构建请求对象
        request = urllib.request.Request(
            url,
            data=encoded_data,
            method="POST",
            headers={
                "Authorization": self._auth_header,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        # 发送请求并处理响应
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

    # ==================== 报告方法 ====================

    def exec_start(self, topic: str, iteration: int, prompt: str) -> None:
        """
        报告执行开始事件

        Args:
            topic: 任务主题
            iteration: 迭代次数
            prompt: 执行提示
        """
        preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
        self.send(topic, f"▶️ EXEC #{iteration} started\nPrompt: {preview}")

    def exec_output(self, topic: str, status: str, output_preview: str = "") -> None:
        """
        报告输出事件

        Args:
            topic: 任务主题
            status: 状态信号
            output_preview: 输出预览（可选）
        """
        content = f"🧠 Claude output:\n{status}"
        if output_preview:
            content += f"\n```\n{output_preview[:500]}\n```"
        self.send(topic, content)

    def file_change(self, topic: str, files: list) -> None:
        """
        报告文件变化事件

        Args:
            topic: 任务主题
            files: 变化文件列表
        """
        if not files:
            return
        file_list = "\n".join(f"- {f}" for f in files[:20])
        if len(files) > 20:
            file_list += f"\n... and {len(files) - 20} more"
        self.send(topic, f"📁 Files modified:\n{file_list}")

    def stall_warning(self, topic: str, minutes: int) -> None:
        """
        报告停滞警告事件

        Args:
            topic: 任务主题
            minutes: 无进度的分钟数
        """
        self.send(topic, f"⚠️ No progress detected for {minutes} minutes")

    def task_done(self, topic: str, iterations: int) -> None:
        """
        报告任务完成事件

        Args:
            topic: 任务主题
            iterations: 总迭代次数
        """
        self.send(topic, f"✅ Task completed after {iterations} iterations")


# URL 编码模块导入（用于 _send_message）
import urllib.parse
