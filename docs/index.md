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

## Architecture

### What This Is

A **minimal supervisor runtime** that:

- Runs Claude Code via `docker exec`
- Parses stdout for continuation signals
- Loops until `STATUS: DONE` or timeout
- Optionally reports events to Zulip

### What This Is NOT

- Not a task queue (single active task)
- Not a Slack bot (no chat interface)
- Not a multi-agent system (Claude does everything)
- Not a Git automation tool (no auto-commits)
- No database (JSON state file only)

### Design Principles

1. **Deletion > Addition** — Minimal code, minimal features
2. **No intelligent judgment** — All decisions come from Claude's output
3. **All state in workspace** — Single JSON file, no external dependencies

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
└── README.md
```

## Quick Links

- [Quickstart](quickstart.md) — Get running in 5 minutes
- [GitHub Repository](https://github.com/context-machine-lab/sleepless-agent)
- [Issue Tracker](https://github.com/context-machine-lab/sleepless-agent/issues)

## License

MIT License
