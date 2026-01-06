# Sleepless Agent

**Minimal Claude Code Continuous Execution Supervisor Runtime**

A lightweight daemon that keeps Claude Code running continuously until your task is complete. No Slack, no database, no multi-agent workflows—just a simple state machine that calls Claude Code via Docker and watches for completion signals.

## What It Does

Sleepless Agent does exactly one thing:

> Before Claude Code stops, know "what to do next" and continue calling it.

```
┌──────────┐     ┌───────────┐     ┌─────────────┐     ┌─────────┐
│   INIT   │ ──▶ │ CHECK_CTX │ ──▶ │ RUN_CLAUDE  │ ──▶ │ OBSERVE │
└──────────┘     └───────────┘     └─────────────┘     └────┬────┘
                                                            │
                                   ┌────────────────────────┴────────────────────────┐
                                   │                                                 │
                                   ▼                                                 ▼
                            STATUS: CONTINUE                                  STATUS: DONE
                                   │                                                 │
                                   └──────▶ RUN_CLAUDE                         ▼
                                                                              IDLE
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker with Claude Code container running
- Claude Code CLI installed in the container

### Installation

```bash
# Clone and install
git clone https://github.com/context-machine-lab/sleepless-agent.git
cd sleepless-agent
pip install -e .
```

### Basic Usage

```bash
# 1. Set a prompt for Claude to execute
sle prompt "Implement the authentication feature described in .claude/plan.md. Output STATUS: DONE when complete, STATUS: CONTINUE if more work needed."

# 2. Start the daemon
sle start -w ./workspace -c claude-cc

# 3. Check status (in another terminal)
sle status -w ./workspace

# 4. Stop the daemon
sle stop -w ./workspace
```

### How Continuation Works

Claude must output one of these signals:
- `STATUS: DONE` — Task complete, daemon goes idle
- `STATUS: CONTINUE` — More work needed, daemon loops back
- Or create a `.claude/done.flag` file in the workspace

**Example prompt:**
```
Continue implementing the feature in .claude/plan.md.

When you complete a step, evaluate if more work is needed:
- If more work needed: end with "STATUS: CONTINUE"
- If all work complete: end with "STATUS: DONE"
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `sle start` | Start the supervisor daemon |
| `sle stop` | Stop the daemon / clear prompt |
| `sle status` | Show current state (JSON) |
| `sle prompt "..."` | Set a new prompt to execute |

### Options

```bash
sle --workspace ./my-project    # Set workspace directory (default: ./workspace)
sle --container my-claude       # Set Docker container name (default: claude-cc)
sle --timeout 7200              # Set timeout in seconds (default: 3600)
```

## Configuration

### Environment Variables

```bash
# Core settings
SLEEPLESS_WORKSPACE=./workspace    # Workspace directory
SLEEPLESS_CONTAINER=claude-cc      # Docker container name
SLEEPLESS_TIMEOUT=3600             # Execution timeout (seconds)
```

Copy `.env.example` to `.env` and customize as needed.

## State File

The daemon maintains state in `{workspace}/.claude/state.json`:

```json
{
  "status": "running",
  "current_prompt": "Implement auth feature...",
  "workspace": "/path/to/workspace",
  "started_at": "2025-01-06T10:30:00Z",
  "last_output": "Last 5KB of Claude output...",
  "iteration_count": 3,
  "error": null
}
```

**Status values:**
- `idle` — No task, waiting for prompt
- `pending` — Prompt set, ready to execute
- `running` — Claude is executing
- `error` — Execution failed

## Zulip Observability (Optional)

Enable read-only event reporting to Zulip for monitoring task execution. Zulip acts as a dashboard—it never controls execution.

### Setup

```bash
export ZULIP_ENABLED=true
export ZULIP_SITE=https://your-org.zulipchat.com
export ZULIP_EMAIL=sleepless-bot@your-org.zulipchat.com
export ZULIP_API_KEY=your-api-key
export ZULIP_STREAM=sleepless
```

### Events Reported

| Event | When | Example |
|-------|------|---------|
| `EXEC_START` | Before Claude runs | ▶️ EXEC #3 started |
| `EXEC_OUTPUT` | After Claude returns | 🧠 Claude output: STATUS: CONTINUE |
| `FILE_CHANGE` | Files modified | 📁 Files modified: src/auth.rs |
| `STALL/WARN` | No progress for 10min | ⚠️ No progress detected |
| `DONE` | Task complete | ✅ Task completed |

Each task gets a unique Zulip topic: `task-20250106-143052-a1b2c3`

### Design Principles

- **One-way only**: Sleepless → Zulip (never reads from Zulip)
- **No control impact**: Zulip failures are logged, never thrown
- **No intelligent judgment**: Reporter just relays events

## Project Structure

```
sleepless-agent/
├── src/sleepless_agent/
│   ├── __init__.py           # Version
│   ├── __main__.py           # Entry point
│   ├── cli.py                # CLI commands
│   ├── config.py             # Configuration loading
│   ├── core/
│   │   ├── daemon.py         # State machine loop
│   │   ├── executor.py       # Docker subprocess execution
│   │   └── state.py          # JSON state management
│   └── reporters/
│       ├── base.py           # BaseReporter + NoopReporter
│       └── zulip_reporter.py # Zulip integration
├── .env.example              # Environment template
├── pyproject.toml            # Package config
└── README.md                 # This file
```

## Architecture

### What This Is

A **minimal supervisor runtime** that:
- Runs Claude Code via `docker exec`
- Parses stdout for continuation signals
- Loops until `STATUS: DONE` or timeout
- Optionally reports events to Zulip

### What This Is NOT

- ❌ Not a task queue (single active task)
- ❌ Not a Slack bot (no chat interface)
- ❌ Not a multi-agent system (Claude does everything)
- ❌ Not a Git automation tool (no auto-commits)
- ❌ No database (JSON state file only)

### Design Principles

1. **Deletion > Addition** — Minimal code, minimal features
2. **No intelligent judgment** — All decisions come from Claude's output
3. **All state in workspace** — Single JSON file, no external dependencies

## Docker Setup

Sleepless expects Claude Code to be running in a Docker container:

```bash
# Example: Run Claude Code in Docker
docker run -d --name claude-cc \
  -v $(pwd)/workspace:/workspace \
  your-claude-code-image

# Verify Claude is accessible
docker exec claude-cc claude --version
```

The daemon calls:
```bash
docker exec -w /workspace claude-cc claude -p "your prompt"
```

## Troubleshooting

### Daemon won't start

```bash
# Check if Docker container is running
docker ps | grep claude-cc

# Check if Claude CLI is accessible
docker exec claude-cc claude --version
```

### Task stuck in loop

Check the prompt—Claude must output `STATUS: DONE` or `STATUS: CONTINUE`. If neither appears in the last 20 lines, the daemon defaults to continue.

### Check state file

```bash
cat workspace/.claude/state.json | jq .
```

### Force stop

```bash
# Clear the prompt to stop after current iteration
sle stop -w ./workspace

# Or manually:
echo '{"status":"idle","current_prompt":null}' > workspace/.claude/state.json
```

## License

MIT License - See [LICENSE](LICENSE)

## Contributing

Issues and pull requests welcome at [GitHub](https://github.com/context-machine-lab/sleepless-agent).
