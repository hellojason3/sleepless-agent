"""Minimal CLI for Claude Code Supervisor Runtime."""

import argparse
import json
import sys
from pathlib import Path

from sleepless_agent.core.state import StateManager
from sleepless_agent.core.daemon import run_daemon


def cmd_start(args) -> int:
    """Start the supervisor daemon."""
    workspace = Path(args.workspace).resolve()

    if not workspace.exists():
        workspace.mkdir(parents=True)
        print(f"Created workspace: {workspace}")

    print(f"Starting daemon...")
    print(f"  Workspace: {workspace}")
    print(f"  Container: {args.container}")
    print(f"  Timeout: {args.timeout}s")

    run_daemon(
        workspace=str(workspace),
        docker_container=args.container,
        timeout=args.timeout,
    )
    return 0


def cmd_stop(args) -> int:
    """Stop the daemon by clearing the prompt."""
    workspace = Path(args.workspace).resolve()
    state_manager = StateManager(workspace)

    state = state_manager.load()
    if state.get("status") == "running":
        state_manager.mark_idle()
        print("Stop signal sent - daemon will stop after current iteration")
    else:
        state_manager.mark_idle()
        print("Prompt cleared")

    return 0


def cmd_status(args) -> int:
    """Show current daemon status."""
    workspace = Path(args.workspace).resolve()
    state_file = workspace / ".claude" / "state.json"

    if not state_file.exists():
        print("No state file found - daemon not initialized")
        print(f"Expected at: {state_file}")
        return 1

    state = json.loads(state_file.read_text())
    print(json.dumps(state, indent=2))
    return 0


def cmd_prompt(args) -> int:
    """Set a new prompt to execute."""
    workspace = Path(args.workspace).resolve()

    if not workspace.exists():
        workspace.mkdir(parents=True)
        print(f"Created workspace: {workspace}")

    state_manager = StateManager(workspace)
    state_manager.set_prompt(args.prompt)

    print(f"Prompt set ({len(args.prompt)} chars)")
    print(f"Preview: {args.prompt[:100]}{'...' if len(args.prompt) > 100 else ''}")
    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="sle",
        description="Claude Code Supervisor Runtime",
    )
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

    subparsers = parser.add_subparsers(dest="command", required=True)

    # start command
    subparsers.add_parser(
        "start",
        help="Start the supervisor daemon",
    )

    # stop command
    subparsers.add_parser(
        "stop",
        help="Stop the daemon / clear prompt",
    )

    # status command
    subparsers.add_parser(
        "status",
        help="Show current daemon status",
    )

    # prompt command
    prompt_parser = subparsers.add_parser(
        "prompt",
        help="Set a new prompt to execute",
    )
    prompt_parser.add_argument(
        "prompt",
        help="The prompt text to execute",
    )

    args = parser.parse_args()

    if args.command == "start":
        return cmd_start(args)
    elif args.command == "stop":
        return cmd_stop(args)
    elif args.command == "status":
        return cmd_status(args)
    elif args.command == "prompt":
        return cmd_prompt(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
