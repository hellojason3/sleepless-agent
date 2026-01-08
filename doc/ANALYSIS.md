# Sleepless Agent 工程详细分析文档

> 版本: 1.0.0
> 日期: 2026-01-08
> 作者: Sleepless Agent 维护团队

---

## 目录

1. [项目概述](#1-项目概述)
2. [核心设计理念](#2-核心设计理念)
3. [架构设计](#3-架构设计)
4. [状态机详解](#4-状态机详解)
5. [模块详解](#5-模块详解)
6. [数据流](#6-数据流)
7. [配置管理](#7-配置管理)
8. [部署方案](#8-部署方案)
9. [扩展性分析](#9-扩展性分析)
10. [故障排查](#10-故障排查)

---

## 1. 项目概述

### 1.1 项目定位

**Sleepless Agent** 是一个极简的 Claude Code 持续执行监控运行时。它是一个轻量级守护进程，用于保持 Claude Code 持续运行直到任务完成。

### 1.2 核心功能

| 功能 | 描述 |
|------|------|
| 持续执行 | 循环调用 Claude Code 直到任务完成 |
| 状态管理 | 基于单文件 JSON 的状态持久化 |
| 信号检测 | 解析 Claude 输出中的完成/继续信号 |
| 可观测性 | 可选的 Zulip 事件报告（单向） |
| 停滞检测 | 检测长时间无进度的情况并报警 |

### 1.3 技术栈

```
Python 3.11+
├── 标准库 (subprocess, json, pathlib, signal, urllib)
└── PyYAML (配置文件解析)
```

### 1.4 目录结构

```
sleepless-agent/
├── src/sleepless_agent/
│   ├── __init__.py              # 版本定义
│   ├── __main__.py              # 程序入口点
│   ├── cli.py                   # CLI 命令行接口
│   ├── config.py                # 配置加载
│   ├── core/
│   │   ├── __init__.py
│   │   ├── daemon.py            # 状态机守护进程
│   │   ├── executor.py          # Docker 执行器
│   │   └── state.py             # JSON 状态管理
│   ├── reporters/
│   │   ├── __init__.py
│   │   ├── base.py              # 基础报告器接口
│   │   └── zulip_reporter.py    # Zulip 集成
│   └── deployment/
│       ├── sleepless-agent.service  # systemd 服务文件
│       └── com.sleepless-agent.plist # launchd 服务文件
├── docs/                        # 文档目录
├── doc/                         # 详细分析文档（新增）
├── Dockerfile                   # Claude Code 容器镜像
├── Makefile                     # 构建和部署命令
├── pyproject.toml               # Python 包配置
└── README.md                    # 项目说明
```

---

## 2. 核心设计理念

### 2.1 设计原则

1. **删除 > 添加 (Deletion > Addition)**
   - 极简代码，极简功能
   - 避免过度抽象
   - 只做一件事并做好

2. **无智能判断 (No Intelligent Judgment)**
   - 所有决策来自 Claude 的输出
   - 守护进程只负责循环和信号检测
   - 不内置任何任务规划逻辑

3. **状态在工作空间 (All State in Workspace)**
   - 单个 JSON 文件存储状态
   - 无外部数据库依赖
   - 状态文件路径: `{workspace}/.claude/state.json`

4. **单向报告 (One-way Reporting)**
   - 可观测性不控制执行
   - Zulip 仅作为输出目标
   - 报告器故障不影响主流程

### 2.2 反模式（明确不做的事）

| 反模式 | 说明 |
|--------|------|
| 任务队列 | 单活动任务，不支持队列 |
| Slack 机器人 | 无聊天界面 |
| 多智能体系统 | Claude 完成所有工作 |
| Git 自动化 | 无自动提交 |
| 数据库 | 仅 JSON 文件 |

---

## 3. 架构设计

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         用户层 (User Layer)                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐     │
│  │ sle start│    │ sle stop │    │ sle status│   │ sle prompt│     │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘     │
└───────┼─────────────┼─────────────┼───────────────┼──────────────┘
        │             │             │               │
┌───────┴─────────────┴─────────────┴───────────────┴──────────────┐
│                        CLI 层 (cli.py)                            │
│                   argparse + 命令处理函数                          │
└─────────────────────────────┬─────────────────────────────────────┘
                              │
┌─────────────────────────────┴─────────────────────────────────────┐
│                      守护进程层 (daemon.py)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ State Machine│─▶│ State Manager│─▶│   Executor   │            │
│  │  (5 states)  │  │   (JSON)     │  │   (Docker)   │            │
│  └──────────────┘  └──────────────┘  └──────┬───────┘            │
└────────────────────────────────────────────┼─────────────────────┘
                                               │
┌──────────────────────────────────────────────┴────────────────────┐
│                      外部集成层                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │   Reporter   │  │  Docker API  │  │  File System │            │
│  │  (Zulip/Noop)│  │  (Container) │  │  (Workspace) │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 组件交互序列图

```
用户           CLI           Daemon         Executor        Claude
 │              │              │               │              │
 ├─ prompt ─────▶              │               │              │
 │              │              │               │              │
 ├─ start ──────▶              │               │              │
 │              │              │               │              │
 │              │           ┌──┘───┐          │              │
 │              │           │ INIT │          │              │
 │              │           └──┬───┘          │              │
 │              │              │               │              │
 │              │           ┌──┴───┐          │              │
 │              │           │CHECK │          │              │
 │              │           │ _CTX │          │              │
 │              │           └──┬───┘          │              │
 │              │              │               │              │
 │              │           ┌──┴────┐         │              │
 │              │           │RUN    ├─────────▶              │
 │              │           │CLAUDE │         │              │
 │              │           └──┬────┘         │              │
 │              │              │               │              │
 │              │           ┌──┴──────┐       │              │
 │              │           │OBSERVE  │       │              │
 │              │           │         │       │              │
 │              │           │ 解析输出 │◀──────┘              │
 │              │           │         │                      │
 │              │           │CONTINUE?│                      │
 │              │           └──┬──┬───┘                      │
 │              │              │  │                          │
 │              │           ┌──┘  └──┐                       │
 │              │           ▼         ▼                       │
 │              │        ┌────┐  ┌────┐                      │
 │              │        │YES │  │ NO │                      │
 │              │        └──┬─┘  └─┬──┘                      │
 │              │           │       │                         │
 │              │      ┌────┘       └────┐                   │
 │              │      ▼                  ▼                   │
 │              │   ┌────────┐        ┌──────┐               │
 │              │   │继续循环 │        │ IDLE │               │
 │              │   └────────┘        └──────┘               │
 │              │                                            │
 ├─ status ─────▶              │               │              │
 │◀─ JSON state ───────────────┤               │              │
```

---

## 4. 状态机详解

### 4.1 状态定义

守护进程实现了一个 5 状态有限状态机 (FSM)：

```python
class State(Enum):
    INIT = "init"           # 初始化：检查待执行提示
    CHECK_CTX = "check_ctx" # 检查上下文：验证工作空间
    RUN_CLAUDE = "run_claude" # 运行 Claude：执行任务
    OBSERVE = "observe"     # 观察：分析输出决定下一步
    IDLE = "idle"           # 空闲：等待新任务
```

### 4.2 状态转换图

```
                    ┌─────────────────────────────────────────────┐
                    │                                             │
                    ▼                                             │
┌─────────┐    ┌──────────┐    ┌────────────┐    ┌─────────┐    │
│  IDLE   │◀───│ OBSERVE  │◀───│ RUN_CLAUDE │◀───│CHECK_CTX│    │
└────┬────┘    └────┬─────┘    └─────┬──────┘    └────┬────┘    │
     │              │                  │                │         │
     │              │                  │                │         │
     │    STATUS:   │                  │                │         │
     │    DONE      │                  │                │         │
     │              │     STATUS:      │                │         │
     │              │     CONTINUE     │                │         │
     │              │                  │                │         │
     ▼              │                  │                │         │
┌─────────┐         │                  │                │         │
│  INIT   │─────────┘                  │                │         │
└────┬────┘                            │                │         │
     │                                 │                │         │
     │ 有 prompt                        │                │         │
     │                                 │                │         │
     │ 无 prompt                        │                │         │
     └─────────────────────────────────┴────────────────┘         │
                                                                       │
                                                                       │
         新 prompt ───────────────────────────────────────────────────┘
```

### 4.3 状态处理方法

| 状态 | 方法 | 主要逻辑 |
|------|------|----------|
| INIT | `_handle_init()` | 检查是否有待执行的 prompt |
| CHECK_CTX | `_handle_check_ctx()` | 验证工作空间存在，初始化任务跟踪 |
| RUN_CLAUDE | `_handle_run_claude()` | 通过 Docker 执行 Claude |
| OBSERVE | `_handle_observe()` | 解析输出，检测文件变化，决定继续或停止 |
| IDLE | `_handle_idle()` | 休眠等待新 prompt |

### 4.4 信号解析逻辑

守护进程通过 `parse_status()` 方法解析 Claude 输出：

```python
def parse_status(self, output: str) -> str:
    # 1. 检查最后 20 行是否有状态标记
    # 2. 检查 .claude/done.flag 文件
    # 3. 默认继续执行
```

**检测顺序：**

1. `STATUS: DONE` → 返回 `"done"`
2. `STATUS: CONTINUE` → 返回 `"continue"`
3. `.claude/done.flag` 存在 → 返回 `"done"`
4. 默认 → 返回 `"continue"`

---

## 5. 模块详解

### 5.1 CLI 模块 (`cli.py`)

**文件位置**: `src/sleepless_agent/cli.py`

**功能**: 提供命令行接口

**命令列表**:

| 命令 | 函数 | 描述 |
|------|------|------|
| `start` | `cmd_start()` | 启动守护进程 |
| `stop` | `cmd_stop()` | 停止守护进程/清除 prompt |
| `status` | `cmd_status()` | 显示当前状态 |
| `prompt` | `cmd_prompt()` | 设置新的执行提示 |

**全局参数**:

```bash
-w, --workspace  # 工作空间目录 (默认: ./workspace)
-c, --container  # Docker 容器名 (默认: claude-cc)
-t, --timeout    # 执行超时秒数 (默认: 3600)
```

**使用示例**:

```bash
# 启动守护进程
sle start -w ./my-project -c claude-container

# 设置任务
sle prompt "实现用户认证功能"

# 查看状态
sle status -w ./my-project

# 停止
sle stop -w ./my-project
```

---

### 5.2 状态管理模块 (`state.py`)

**文件位置**: `src/sleepless_agent/core/state.py`

**功能**: 管理工作空间中的 JSON 状态文件

**状态文件结构**:

```json
{
  "status": "running",           // 当前状态
  "current_prompt": "...",       // 待执行的提示
  "workspace": "/path/to/ws",    // 工作空间路径
  "started_at": "2025-01-08T...", // 开始时间
  "last_output": "...",          // 最后 5KB 输出
  "iteration_count": 3,          // 迭代次数
  "error": null                  // 错误信息
}
```

**状态值枚举**:

| 状态 | 描述 |
|------|------|
| `idle` | 空闲，无任务 |
| `pending` | 有待执行的任务 |
| `running` | 正在执行 |
| `error` | 执行出错 |

**主要方法**:

| 方法 | 描述 |
|------|------|
| `load()` | 加载状态 |
| `save(data)` | 保存状态 |
| `set_prompt(prompt)` | 设置新提示 |
| `mark_running()` | 标记为运行中 |
| `mark_idle()` | 标记为空闲 |
| `mark_error(error)` | 标记错误 |
| `update_output(output)` | 更新输出 |
| `get_prompt()` | 获取当前提示 |
| `get_status()` | 获取当前状态 |
| `check_done_flag()` | 检查完成标志文件 |

---

### 5.3 执行器模块 (`executor.py`)

**文件位置**: `src/sleepless_agent/core/executor.py`

**功能**: 通过 Docker 子进程执行 Claude Code

**核心方法**:

```python
def run(prompt: str, cwd: str = "/workspace") -> Tuple[str, int]:
    """执行 Claude

    实际执行的命令:
    docker exec -w /workspace claude-cc claude -p "prompt"

    返回: (stdout, return_code)
    """
```

**检查方法**:

| 方法 | 描述 |
|------|------|
| `check_docker()` | 检查 Docker 容器是否运行 |
| `check_claude()` | 检查 Claude CLI 是否可用 |

**错误处理**:

- 超时 → 返回 `"ERROR: Timeout expired"`, `-1`
- 异常 → 返回 `"ERROR: {exception}"`, `-1`

---

### 5.4 守护进程模块 (`daemon.py`)

**文件位置**: `src/sleepless_agent/core/daemon.py`

**功能**: 核心状态机实现

**类结构**:

```python
class Daemon:
    def __init__(
        self,
        workspace: Path,           # 工作空间路径
        docker_container: str,     # Docker 容器名
        timeout: int,              # 超时秒数
        idle_interval: int,        # 空闲休眠秒数
        reporter: BaseReporter,    # 报告器
        stall_threshold_minutes: int,  # 停滞检测阈值
    )
```

**任务跟踪属性**:

| 属性 | 类型 | 描述 |
|------|------|------|
| `current_topic` | str | 当前任务的唯一标识符 |
| `task_start_time` | float | 任务开始时间戳 |
| `last_file_snapshot` | Set[str] | 上次文件快照 |
| `last_progress_time` | float | 上次进度时间 |
| `stall_warned` | bool | 是否已警告停滞 |

**生命周期钩子**:

| 钩子 | 触发时机 | 报告方法 |
|------|----------|----------|
| EXEC_START | Claude 执行前 | `reporter.exec_start()` |
| EXEC_OUTPUT | Claude 返回后 | `reporter.exec_output()` |
| FILE_CHANGE | 检测到文件变化 | `reporter.file_change()` |
| STALL/WARN | 长时间无进度 | `reporter.stall_warning()` |
| DONE | 任务完成 | `reporter.task_done()` |

**文件变化检测**:

```python
def _get_workspace_files(self) -> Set[str]:
    """获取工作空间文件集合（包含 mtime）

    返回格式: {"path/to/file:1234567890.123", ...}
    """

def _detect_file_changes(self) -> list:
    """检测自上次检查以来的变化文件"""
```

---

### 5.5 报告器模块 (`reporters/`)

#### 5.5.1 基础报告器 (`base.py`)

**抽象接口**:

```python
class BaseReporter(ABC):
    @abstractmethod
    def send(self, topic: str, content: str) -> None:
        """发送消息（永不抛出异常）"""
```

**报告方法**:

| 方法 | 描述 |
|------|------|
| `exec_start(topic, iteration, prompt)` | 执行开始 |
| `exec_output(topic, status, output_preview)` | 输出事件 |
| `file_change(topic, files)` | 文件变化 |
| `stall_warning(topic, minutes)` | 停滞警告 |
| `task_done(topic, iterations)` | 任务完成 |

#### 5.5.2 空报告器 (`NoopReporter`)

用于禁用报告功能，所有方法为空操作。

#### 5.5.3 Zulip 报告器 (`zulip_reporter.py`)

**初始化参数**:

| 参数 | 描述 |
|------|------|
| `site` | Zulip 服务器 URL |
| `email` | 机器人邮箱 |
| `api_key` | API 密钥 |
| `stream` | 流名称 |

**认证方式**: Basic Auth (base64)

**API 端点**: `POST /api/v1/messages`

**错误处理**: 所有异常被捕获并打印到 stderr，永不抛出

---

## 6. 数据流

### 6.1 执行流程

```
1. 用户设置 prompt
   └─> sle prompt "任务描述"
       └─> state.json: current_prompt = "任务描述"
           └─> state.json: status = "pending"

2. 守护进程启动
   └─> sle start
       └─> Daemon.run()
           └─> 状态机循环

3. INIT 状态
   └─> 读取 current_prompt
       └─> 如果有 prompt → CHECK_CTX
           └─> 如果无 prompt → IDLE

4. CHECK_CTX 状态
   └─> 验证工作空间存在
       └─> 创建 .claude 目录
           └─> 初始化文件快照
               └─> 生成唯一 topic
                   └─> RUN_CLAUDE

5. RUN_CLAUDE 状态
   └─> 标记状态为 running
       └─> 执行: docker exec claude-cc claude -p "prompt"
           └─> 捕获输出
               └─> 更新 state.json: last_output
                   └─> OBSERVE

6. OBSERVE 状态
   └─> 解析输出中的 STATUS 信号
       └─> 检测文件变化
           └─> 检查停滞
               └─> 如果 STATUS: DONE → IDLE
                   └─> 如果 STATUS: CONTINUE → RUN_CLAUDE

7. IDLE 状态
   └─> 休眠 idle_interval 秒
       └─> 检查新 prompt
           └─> 如果有 → CHECK_CTX
```

### 6.2 状态数据流

```
┌─────────────────────────────────────────────────────────────┐
│                     state.json                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │ {                                                   │     │
│  │   "status": "running",           │───┐             │     │
│  │   "current_prompt": "...",       │   │             │     │
│  │   "workspace": "...",            │   │ 读取         │     │
│  │   "started_at": "...",           │   │             │     │
│  │   "last_output": "...",          │◀──┘             │     │
│  │   "iteration_count": 3,          │                 │     │
│  │   "error": null                  │                 │     │
│  │ }                                │                 │     │
│  └──────────────────────────────────│─────────────────┘     │
│                                       ▲                       │
│                                       │ 写入                   │
│                                   ┌───┴───┐                   │
│                                   │ State │                   │
│                                   │Manager│                   │
│                                   └───────┘                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. 配置管理

### 7.1 配置优先级

```
环境变量 > 配置文件 > 默认值
```

### 7.2 环境变量

| 变量名 | 描述 | 默认值 |
|--------|------|--------|
| `SLEEPLESS_WORKSPACE` | 工作空间目录 | `./workspace` |
| `SLEEPLESS_CONTAINER` | Docker 容器名 | `claude-cc` |
| `SLEEPLESS_TIMEOUT` | 超时秒数 | `3600` |
| `ZULIP_ENABLED` | 启用 Zulip | `false` |
| `ZULIP_SITE` | Zulip 服务器 URL | - |
| `ZULIP_EMAIL` | Zulip 机器人邮箱 | - |
| `ZULIP_API_KEY` | Zulip API 密钥 | - |
| `ZULIP_STREAM` | Zulip 流名称 | - |

### 7.3 配置加载代码

```python
# config.py
@classmethod
def load(cls, config_path: Optional[Path] = None) -> "Config":
    # 1. 设置默认值
    # 2. 加载 YAML 配置文件（如果存在）
    # 3. 应用环境变量覆盖
    # 4. 加载 Zulip 配置
    return Config(...)
```

---

## 8. 部署方案

### 8.1 Docker 容器配置

**镜像**: 基于 Alpine Linux

**包含组件**:

| 组件 | 版本/来源 |
|------|-----------|
| Alpine Linux | latest |
| Rust | via rustup (rsproxy.cn 镜像) |
| Node.js | apk |
| Claude Code CLI | npm: @anthropic-ai/claude-code |
| 构建工具 | build-base |

**卷挂载**:

```bash
-v $(pwd)/workspace:/workspace       # 工作空间
-v $(HOME)/.claude-sleepless-agent:/home/claude/.claude  # Claude 认证
```

### 8.2 systemd 服务

**文件位置**: `/etc/systemd/system/sleepless-agent.service`

**配置要点**:

```ini
[Service]
Type=simple
User=sleepless
WorkingDirectory=/opt/sleepless-agent
ExecStart=/opt/sleepless-agent/venv/bin/sle start
Restart=on-failure
EnvironmentFile=/opt/sleepless-agent/.env

# 安全配置
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/sleepless-agent/workspace
```

### 8.3 launchd 服务 (macOS)

**文件位置**: `~/Library/LaunchAgents/com.sleepless-agent.plist`

**配置要点**:

```xml
<key>Label</key>
<string>com.sleepless-agent</string>
<key>ProgramArguments</key>
<array>
    <string>/usr/local/bin/sle</string>
    <string>start</string>
</array>
<key>RunAtLoad</key>
<true/>
<key>KeepAlive</key>
<dict>
    <key>SuccessfulExit</key>
    <false/>
</dict>
```

---

## 9. 扩展性分析

### 9.1 添加新的报告器

继承 `BaseReporter` 并实现 `send()` 方法：

```python
# reporters/slack_reporter.py
from sleepless_agent.reporters.base import BaseReporter

class SlackReporter(BaseReporter):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, topic: str, content: str) -> None:
        try:
            # 发送到 Slack
            requests.post(self.webhook_url, json={
                "text": f"[{topic}] {content}"
            })
        except Exception as e:
            print(f"[SlackReporter] Failed: {e}")
```

### 9.2 添加新的状态信号

修改 `daemon.py` 中的 `parse_status()` 方法：

```python
def parse_status(self, output: str) -> str:
    lines = output.strip().split("\n")
    for line in reversed(lines[-20:]):
        if "STATUS: DONE" in line:
            return "done"
        if "STATUS: CONTINUE" in line:
            return "continue"
        # 添加新信号
        if "STATUS: PAUSE" in line:
            return "pause"  # 需要添加对应的状态处理
    ...
```

### 9.3 自定义执行器

可以继承 `ClaudeExecutor` 实现不同的执行方式：

```python
# executors/k8s_executor.py
from sleepless_agent.core.executor import ClaudeExecutor

class K8sExecutor(ClaudeExecutor):
    def run(self, prompt: str, cwd: str = "/workspace") -> Tuple[str, int]:
        # 使用 Kubernetes API 执行
        ...
```

---

## 10. 故障排查

### 10.1 常见问题

#### 问题: 守护进程无法启动

**检查步骤**:

```bash
# 1. 检查 Docker 容器是否运行
docker ps | grep claude-cc

# 2. 检查 Claude CLI 是否可用
docker exec claude-cc claude --version

# 3. 检查工作空间权限
ls -la ./workspace
```

#### 问题: 任务卡在循环中

**原因**: Claude 输出中没有 `STATUS: DONE` 或 `STATUS: CONTINUE`

**解决方案**:

1. 检查 prompt 是否要求输出状态信号
2. 查看 state.json 中的 last_output
3. 手动创建 `.claude/done.flag` 文件

```bash
touch workspace/.claude/done.flag
```

#### 问题: 状态文件损坏

**症状**: `sle status` 报错

**解决方案**:

```bash
# 删除损坏的状态文件
rm workspace/.claude/state.json

# 重新设置 prompt
sle prompt "任务描述"
```

### 10.2 日志查看

```bash
# systemd 日志
journalctl -u sleepless-agent -f

# launchd 日志 (macOS)
tail -f ~/projects/sleepless-agent/workspace/daemon.log
```

### 10.3 调试模式

```bash
# 直接运行 Python 模块
python -m sleepless_agent start -w ./workspace

# 查看详细状态
cat workspace/.claude/state.json | jq .
```

---

## 附录

### A. 文件清单

| 文件 | 行数 | 描述 |
|------|------|------|
| `cli.py` | 150 | CLI 命令行接口 |
| `config.py` | 98 | 配置管理 |
| `daemon.py` | 356 | 状态机守护进程 |
| `executor.py` | 89 | Docker 执行器 |
| `state.py` | 94 | JSON 状态管理 |
| `base.py` | 67 | 报告器基类 |
| `zulip_reporter.py` | 139 | Zulip 集成 |

### B. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2025-01-06 | 初始版本 |

### C. 参考链接

- [GitHub 仓库](https://github.com/context-machine-lab/sleepless-agent)
- [Claude Code 文档](https://docs.anthropic.com/claude-code)
- [Docker 文档](https://docs.docker.com/)

---

*本文档由 Sleepless Agent 维护团队编写，最后更新于 2026-01-08*
