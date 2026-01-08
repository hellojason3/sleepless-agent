"""
Sleepless Agent - CLI 命令行接口模块

本模块提供命令行界面，允许用户与守护进程交互。
主要命令:
    - start: 启动守护进程
    - stop: 停止守护进程/清除提示
    - status: 显示当前状态
    - prompt: 设置新的执行提示

使用示例:
    sle start -w ./workspace -c claude-cc
    sle prompt "实现用户认证功能"
    sle status -w ./workspace
    sle stop -w ./workspace
"""

import argparse
import json
import sys
from pathlib import Path

from sleepless_agent.core.state import StateManager
from sleepless_agent.core.daemon import run_daemon


def cmd_start(args) -> int:
    """
    启动守护进程命令处理函数

    执行步骤:
        1. 解析工作空间路径
        2. 如果工作空间不存在则创建
        3. 打印启动信息
        4. 调用 run_daemon() 进入主循环

    Args:
        args: argparse 解析后的参数对象
            - workspace: 工作空间目录路径
            - container: Docker 容器名称
            - timeout: 执行超时时间（秒）

    Returns:
        int: 退出码，0 表示成功
    """
    # 将路径转换为绝对路径，避免相对路径的歧义
    workspace = Path(args.workspace).resolve()

    # 如果工作空间不存在，递归创建目录
    if not workspace.exists():
        workspace.mkdir(parents=True)
        print(f"Created workspace: {workspace}")

    # 打印启动配置信息，方便用户确认
    print(f"Starting daemon...")
    print(f"  Workspace: {workspace}")
    print(f"  Container: {args.container}")
    print(f"  Timeout: {args.timeout}s")

    # 启动守护进程（阻塞调用，直到进程退出）
    run_daemon(
        workspace=str(workspace),
        docker_container=args.container,
        timeout=args.timeout,
    )
    return 0


def cmd_stop(args) -> int:
    """
    停止守护进程命令处理函数

    注意: 此函数不会立即终止进程，而是清除当前提示，
    守护进程会在完成当前迭代后检测到状态变化并进入空闲状态。

    Args:
        args: argparse 解析后的参数对象
            - workspace: 工作空间目录路径

    Returns:
        int: 退出码，0 表示成功
    """
    workspace = Path(args.workspace).resolve()
    state_manager = StateManager(workspace)

    # 加载当前状态
    state = state_manager.load()

    # 如果守护进程正在运行，发送停止信号
    if state.get("status") == "running":
        state_manager.mark_idle()
        print("Stop signal sent - daemon will stop after current iteration")
    else:
        # 即使不在运行状态，也清除提示以确保停止
        state_manager.mark_idle()
        print("Prompt cleared")

    return 0


def cmd_status(args) -> int:
    """
    显示守护进程当前状态命令处理函数

    以 JSON 格式输出状态文件内容，便于脚本解析和调试。

    Args:
        args: argparse 解析后的参数对象
            - workspace: 工作空间目录路径

    Returns:
        int: 退出码，0 表示成功，1 表示状态文件不存在
    """
    workspace = Path(args.workspace).resolve()
    # 状态文件位于工作空间的 .claude 隐藏目录下
    state_file = workspace / ".claude" / "state.json"

    # 如果状态文件不存在，说明守护进程从未启动过
    if not state_file.exists():
        print("No state file found - daemon not initialized")
        print(f"Expected at: {state_file}")
        return 1

    # 读取并格式化输出 JSON 状态
    state = json.loads(state_file.read_text())
    print(json.dumps(state, indent=2))
    return 0


def cmd_prompt(args) -> int:
    """
    设置新的执行提示命令处理函数

    此命令可以随时调用，即使守护进程正在运行。
    守护进程会在下次迭代时检测到新提示并开始执行。

    Args:
        args: argparse 解析后的参数对象
            - workspace: 工作空间目录路径
            - prompt: 要执行的任务提示文本

    Returns:
        int: 退出码，0 表示成功
    """
    workspace = Path(args.workspace).resolve()

    # 确保工作空间存在
    if not workspace.exists():
        workspace.mkdir(parents=True)
        print(f"Created workspace: {workspace}")

    # 保存提示到状态文件
    state_manager = StateManager(workspace)
    state_manager.set_prompt(args.prompt)

    # 打印确认信息，显示提示预览
    print(f"Prompt set ({len(args.prompt)} chars)")
    preview = args.prompt[:100] + "..." if len(args.prompt) > 100 else args.prompt
    print(f"Preview: {preview}")
    return 0


def main() -> int:
    """
    CLI 主入口函数

    使用 argparse 解析命令行参数，并路由到相应的处理函数。

    全局选项:
        -w, --workspace: 工作空间目录（默认: ./workspace）
        -c, --container: Docker 容器名（默认: claude-cc）
        -t, --timeout: 执行超时秒数（默认: 3600）

    子命令:
        start: 启动守护进程
        stop: 停止守护进程
        status: 显示状态
        prompt: 设置提示

    Returns:
        int: 程序退出码
    """
    # 创建主解析器
    parser = argparse.ArgumentParser(
        prog="sle",
        description="Claude Code Supervisor Runtime",
    )

    # 全局参数定义
    parser.add_argument(
        "--workspace", "-w",
        default="./workspace",
        help="Workspace directory path (default: ./workspace)",
    )
    parser.add_argument(
        "--container", "-c",
        default="claude-cc",
        help="Docker container name (default: claude-cc)",
    )
    parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=3600,
        help="Execution timeout in seconds (default: 3600)",
    )

    # 创建子命令解析器
    subparsers = parser.add_subparsers(dest="command", required=True)

    # start 子命令
    subparsers.add_parser(
        "start",
        help="Start the supervisor daemon",
    )

    # stop 子命令
    subparsers.add_parser(
        "stop",
        help="Stop the daemon / clear prompt",
    )

    # status 子命令
    subparsers.add_parser(
        "status",
        help="Show current daemon status",
    )

    # prompt 子命令（需要一个额外的参数）
    prompt_parser = subparsers.add_parser(
        "prompt",
        help="Set a new prompt to execute",
    )
    prompt_parser.add_argument(
        "prompt",
        help="The prompt text to execute",
    )

    # 解析命令行参数
    args = parser.parse_args()

    # 根据子命令路由到相应的处理函数
    if args.command == "start":
        return cmd_start(args)
    elif args.command == "stop":
        return cmd_stop(args)
    elif args.command == "status":
        return cmd_status(args)
    elif args.command == "prompt":
        return cmd_prompt(args)
    else:
        # 未识别的命令（理论上不会到达这里，因为设置了 required=True）
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
