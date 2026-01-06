# Quickstart

Get Sleepless Agent running in 5 minutes.

## Prerequisites

- Python 3.11+
- Docker with Claude Code container running
- Claude Code CLI installed in the container

## Installation

```bash
# Clone and install
git clone https://github.com/context-machine-lab/sleepless-agent.git
cd sleepless-agent
uv sync  # or: pip install -e .
```

## Basic Usage

### 1. Set a prompt

```bash
sle prompt "Implement the authentication feature described in .claude/plan.md. Output STATUS: DONE when complete, STATUS: CONTINUE if more work needed."
```

### 2. Start the daemon

```bash
sle start -w ./workspace -c claude-cc
```

### 3. Check status (in another terminal)

```bash
sle status -w ./workspace
```

### 4. Stop the daemon

```bash
sle stop -w ./workspace
```

## How Continuation Works

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

## Next Steps

- See the [README](https://github.com/context-machine-lab/sleepless-agent) for Zulip observability setup
- Check [.env.example](https://github.com/context-machine-lab/sleepless-agent/blob/main/.env.example) for all configuration options
