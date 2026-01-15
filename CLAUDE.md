# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
make install-dev    # Install with dev dependencies
make test           # Run tests: uv run pytest tests/ -v
make lint           # Run linting: ruff check + ruff format --check
make type-check     # Run mypy: uv run mypy src/ --ignore-missing-imports
make check          # Run all checks (lint + type-check + test)
make format         # Auto-format code with ruff
```

Run a single test:
```bash
uv run pytest tests/test_cli.py -v -k "test_name"
```

## Architecture

This is a multi-agent system built with the OpenAI Agents SDK (`openai-agents`) that generates daily standup summaries from GitHub activity.

### Agent Flow

```
Coordinator Agent (gpt-4o)
    │
    ├── handoff to → Data Gatherer Agent (gpt-4o-mini)
    │                   └── uses gh CLI tools to collect PRs, issues, commits, reviews
    │
    └── handoff to → Summarizer Agent (gpt-4o)
                        └── creates formatted standup, can save/copy
```

### Key Components

- **`runner.py`**: Entry point for agent execution. `run_standup_generation()` for one-shot, `run_interactive_chat()` for chat mode
- **`context.py`**: `StandupContext` dataclass passed through all agents via `RunContextWrapper` - holds collected data, configuration, and current standup state
- **`agents/`**: Three agents with different responsibilities:
  - `coordinator.py`: Orchestrates workflow, handles commands like copy/save
  - `data_gatherer.py`: Collects GitHub data using function tools
  - `summarizer.py`: Creates summaries, supports structured output via `StandupSummary` Pydantic model
- **`tools/`**: Function tools decorated with `@function_tool` that wrap `gh` CLI commands
- **`guardrails/`**: Input/output validation (e.g., `validate_days_guardrail` limits lookback range)
- **`hooks.py`**: `RunHooks` and `AgentHooks` for logging/observability
- **`db.py`**: SQLite persistence for standup history at `~/.config/standup-agent/standups.db`

### Tool Pattern

Tools receive context via `RunContextWrapper[StandupContext]` as first parameter:
```python
@function_tool
def get_my_prs(
    ctx: RunContextWrapper[StandupContext],
    days_back: Annotated[int, "Number of days to look back"] = 1,
) -> str:
    username = ctx.context.github_username
    # ... execute gh CLI command
    ctx.context.collected_prs = results  # Store in context
    return formatted_output
```

### CLI Commands

Entry point is `standup` (defined in `cli.py` using Typer):
- `standup generate [--days N] [--output clipboard] [--with-history]`
- `standup chat [--days N]` - interactive refinement session
- `standup history [--list] [--date YYYY-MM-DD] [--clear]`
- `standup config [--show] [--set-github-user X] [--set-model X]`

## Configuration

Environment variables:
- `OPENAI_API_KEY` (required)
- `STANDUP_GITHUB_USER` - override auto-detected username
- `STANDUP_COORDINATOR_MODEL`, `STANDUP_DATA_GATHERER_MODEL`, `STANDUP_SUMMARIZER_MODEL`

Config file: `~/.config/standup-agent/config.json`
