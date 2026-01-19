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
- `standup generate [--days N] [--output clipboard] [--with-history] [--verbose/--quiet]`
- `standup chat [--days N] [--verbose/--quiet] [--resume] [--session NAME]` - interactive refinement session
- `standup sessions [--list] [--clear]` - manage chat sessions
- `standup history [--list] [--date YYYY-MM-DD] [--clear]`
- `standup config [--show] [--set-github-user X] [--set-model X] [--set-style X] [--init-style] [--edit-style] [--init-examples] [--edit-examples]`

Verbose mode (on by default) shows agent activity: tool calls, handoffs, timing. Use `--quiet` to disable.

## Configuration

Environment variables:
- `OPENAI_API_KEY` (required)
- `STANDUP_GITHUB_USER` - override auto-detected username
- `STANDUP_COORDINATOR_MODEL`, `STANDUP_DATA_GATHERER_MODEL`, `STANDUP_SUMMARIZER_MODEL`

Config file: `~/.config/standup-agent/config.json`

## Style Customization

Customize how standup summaries are generated with your own style preferences.

### Quick Style (via config)

Set a brief style instruction:
```bash
standup config --set-style "Be very concise. Use bullet points only. Skip blockers unless critical."
```

### Detailed Style (via style.md file)

For more detailed customization, create and edit a style file:
```bash
standup config --init-style    # Creates ~/.config/standup-agent/style.md
standup config --edit-style    # Opens the file in your editor
```

Example `style.md` content:
```markdown
# My Standup Style

- Keep summaries very concise (3-5 bullet points max)
- Use emoji for status: completed, in progress, blocked
- Group items by project/repo instead of activity type
- Skip the blockers section unless there's something critical
- Focus on outcomes and impact, not just what was done
- Use past tense for completed work, present for ongoing
```

**Priority order**: style.md file + config style_instructions + examples.md are combined.

### Example Standups (via examples.md file)

Provide real examples of standups you like. This is "few-shot prompting" - the AI will match the tone, format, and level of detail from your examples.

```bash
standup config --init-examples    # Creates ~/.config/standup-agent/examples.md
standup config --edit-examples    # Opens the file in your editor
```

Example `examples.md` content:
```markdown
# Example Standups

## Example 1

Did:
- merged js sdk for llma / error tracking - pr
- added prom metrics for nodejs ai processing stuff - pr
- deep dive on why my code not deployed - learned some stuff - thread in dev
- refactored eval pr to add NA option following Carlos suggestion - pr

Will Do:
- if get clustering pr3 merged then will manually register both temporal workflows in prod
- docs and next steps for errors tab out of alpha work
```

### CLI Commands

- `standup config --show` - Shows current style and examples configuration
- `standup config --set-style "..."` - Set quick style instructions
- `standup config --init-style` - Create style.md template
- `standup config --edit-style` - Open style.md in editor
- `standup config --init-examples` - Create examples.md template
- `standup config --edit-examples` - Open examples.md in editor

## Chat Sessions

Chat mode uses the OpenAI Agents SDK's `SQLiteSession` for automatic conversation persistence. Sessions are stored at `~/.config/standup-agent/chat_sessions.db`.

### Basic Usage

```bash
standup chat                    # Start new session (auto-named by date)
standup chat --resume           # Resume the last session
standup chat --session weekly   # Use a named session
```

### Session Features

- **Automatic persistence**: Conversation history is saved automatically
- **Resume later**: Continue refining a standup from where you left off
- **Named sessions**: Create reusable sessions for recurring standups (e.g., `--session weekly`)
- **Context maintained**: The agent remembers previous messages in the session

### Managing Sessions

```bash
standup sessions --list    # List recent sessions
standup sessions --clear   # Delete all sessions
```

### How It Works

Sessions use the SDK's memory feature to automatically:
1. Load previous conversation history when resuming
2. Save new messages after each turn
3. Provide full context to the agent for better responses

Session IDs follow the pattern `chat_{name}` or `chat_{username}_{date}` for auto-generated sessions.

## PostHog Instrumentation (optional)

Enable agent tracing to PostHog by setting environment variables:
- `POSTHOG_API_KEY` - Enables PostHog agent tracing when set
- `POSTHOG_HOST` - PostHog host (default: https://us.posthog.com)
- `POSTHOG_DISTINCT_ID` - User identifier (defaults to github_username)
- `POSTHOG_DEBUG` - Set to "true" for verbose PostHog logging

Install the PostHog SDK:
```bash
uv pip install posthog>=7.6.0
# Or for local development with unreleased features:
uv pip install -e ../posthog-python
```

### Custom Events

When PostHog is enabled, the following custom events are emitted:
- `standup_generated` - Emitted after every standup generation with full summary and metadata
- `standup_saved` - Emitted when the agent explicitly calls the `save_standup` tool

Event properties include: `summary`, `github_username`, `days_back`, `date`, `summary_length`, `has_prs`, `has_issues`, `has_commits`, `has_reviews`

## Slack Integration (optional)

Post standups directly to Slack channels or threads.

### Setup

1. Create a Slack app at https://api.slack.com/apps
2. Add the following OAuth scopes under "OAuth & Permissions":
   - `chat:write` - Post messages
   - `channels:history` - Find existing standup threads (optional, for auto-thread feature)
3. Install the app to your workspace
4. Copy the "Bot User OAuth Token" (starts with `xoxb-`)

### Configuration

Set environment variables:
- `STANDUP_SLACK_BOT_TOKEN` - Your Slack Bot OAuth token (required for Slack)
- `STANDUP_SLACK_CHANNEL` - Default channel ID to post to (e.g., `C01234567`)

Install the Slack SDK:
```bash
uv pip install slack-sdk
# Or with the slack extra:
uv pip install github-standup-agent[slack]
```

### Usage

In chat mode, ask the agent to post to Slack:
```
> post my standup to slack
```

The tool will automatically try to find the latest standup thread in the channel (within the last 7 days) and post as a reply. If no thread is found, it posts as a new message.

### Finding Your Channel ID

Channel IDs are different from channel names. To find your channel ID:
1. Open Slack in a browser
2. Navigate to the channel
3. The URL will be like `https://app.slack.com/client/T.../C01234567`
4. The `C01234567` part is your channel ID

### Troubleshooting

- **"Bot is not in channel"**: Invite the bot to the channel with `/invite @your-bot-name`
- **"Channel not found"**: Make sure you're using the channel ID (e.g., `C01234567`), not the channel name
- **"Invalid auth"**: Check your `STANDUP_SLACK_BOT_TOKEN` is correct and the app is installed
