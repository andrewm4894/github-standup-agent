# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
make install-dev      # Install with dev dependencies
make install-posthog  # Install with PostHog instrumentation
make install-all      # Install with all optional dependencies
make test             # Run tests: uv run pytest tests/ -v
make lint             # Run linting: ruff check + ruff format --check
make type-check       # Run mypy: uv run mypy src/ --ignore-missing-imports
make check            # Run all checks (lint + type-check + test)
make format           # Auto-format code with ruff
```

Run a single test:
```bash
uv run pytest tests/test_cli.py -v -k "test_name"
```

## Architecture

This is a multi-agent system built with the OpenAI Agents SDK (`openai-agents`) that generates daily standup summaries from GitHub activity.

### Agent Flow

```
Coordinator Agent (gpt-5.2)
    │
    ├── handoff to → Data Gatherer Agent (gpt-5.2)
    │                   └── uses gh CLI tools to collect PRs, issues, commits, reviews
    │                   └── optionally fetches team standups from Slack
    │
    └── handoff to → Summarizer Agent (gpt-5.2)
                        └── creates formatted standup, can save/copy/publish to Slack
```

### Key Components

- **`runner.py`**: Entry point for agent execution. `run_standup_generation()` for one-shot, `run_interactive_chat()` for chat mode
- **`context.py`**: `StandupContext` dataclass passed through all agents via `RunContextWrapper` - holds collected data, configuration, and current standup state
- **`agents/`**: Three agents with different responsibilities:
  - `coordinator.py`: Orchestrates workflow, handles commands like copy/save
  - `data_gatherer.py`: Collects GitHub data using function tools
  - `summarizer.py`: Creates summaries, supports structured output via `StandupSummary` Pydantic model
- **`tools/`**: Function tools decorated with `@function_tool` that wrap `gh` CLI and Slack API calls
- **`guardrails/`**: Input/output validation (e.g., `validate_days_guardrail` limits lookback range)
- **`hooks.py`**: `RunHooks` and `AgentHooks` for logging/observability

### Tool Pattern

Tools receive context via `RunContextWrapper[StandupContext]` as first parameter:
```python
@function_tool
def list_prs(
    ctx: RunContextWrapper[StandupContext],
    filter_by: Annotated[
        Literal["authored", "reviewed", "assigned", "involves", "review-requested"],
        "Filter mode for PR search",
    ] = "authored",
    username: Annotated[str | None, "GitHub username (defaults to current user)"] = None,
    days_back: Annotated[int, "Number of days to look back"] = 7,
) -> str:
    target_user = username or ctx.context.github_username
    # ... execute gh CLI command
    ctx.context.collected_prs = results  # Store in context
    return formatted_output
```

### GitHub Tools Structure

Tools are organized in `tools/github/` with a two-tier pattern:

**Overview/List Tools** (for discovery):
- `get_activity_feed` - Chronological feed of all GitHub activity (start here)
- `list_prs` - Search PRs with flexible `filter_by` (authored/reviewed/assigned/involves/review-requested)
- `list_issues` - Search issues with flexible `filter_by` (authored/assigned/mentions/involves)
- `list_commits` - Search commits by user
- `list_reviews` - Fetch reviews given or received with actual states (APPROVED, CHANGES_REQUESTED, etc.)

**Assigned Items** (no date filter):
- `list_assigned_items` - All open issues/PRs assigned to user, regardless of activity date

**Detail Tools** (for drill-down):
- `get_pr_details(repo, number)` - Full PR context (body, reviews, CI status, linked issues)
- `get_issue_details(repo, number)` - Full issue context (body, linked PRs, labels)

### CLI Commands

Entry point is `standup` (defined in `cli.py` using Typer):
- `standup generate [--days N] [--output stdout|clipboard|file] [--output-file FILE] [--with-history] [--verbose/--quiet]`
- `standup chat [--days N] [--verbose/--quiet] [--resume] [--session NAME]` - interactive refinement session
- `standup sessions [--list] [--clear]` - manage chat sessions
- `standup history [--list] [--date YYYY-MM-DD] [--clear]`
- `standup config [--show] [--set-github-user X] [--set-model X] [--set-style X] [--set-slack-channel X] [--init-style] [--edit-style] [--init-examples] [--edit-examples]`

Verbose mode (on by default) shows agent activity: tool calls, handoffs, timing. Use `--quiet` to disable.

## Configuration

Environment variables (`.env` takes priority over config file):
- `OPENAI_API_KEY` (required)
- `STANDUP_GITHUB_USER` - override auto-detected username
- `STANDUP_COORDINATOR_MODEL`, `STANDUP_DATA_GATHERER_MODEL`, `STANDUP_SUMMARIZER_MODEL`
- `STANDUP_SLACK_BOT_TOKEN` - Slack bot token for reading/publishing standups
- `STANDUP_SLACK_CHANNEL` - default Slack channel (can also set via CLI)
- `STANDUP_CONFIG_DIR` - config directory (default: platform-specific user config dir, e.g., `~/.config/github-standup-agent` on Linux, `~/Library/Application Support/github-standup-agent` on macOS)
- `STANDUP_DATA_DIR` - data directory (default: platform-specific user data dir, e.g., `~/.local/share/github-standup-agent` on Linux)

Config file location: `$STANDUP_CONFIG_DIR/config.json` (see `config/config.example.json` in the repo for template)

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
standup config --init-style    # Creates style.md in your config directory
standup config --edit-style    # Opens the file in your editor
```

The file is created at `$STANDUP_CONFIG_DIR/style.md` (defaults to platform-specific user config directory).

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
standup config --init-examples    # Creates examples.md in your config directory
standup config --edit-examples    # Opens the file in your editor
```

The file is created at `$STANDUP_CONFIG_DIR/examples.md` (defaults to platform-specific user config directory).

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

Chat mode uses the OpenAI Agents SDK's `SQLiteSession` for automatic conversation persistence. Sessions are stored at `.standup-data/chat_sessions.db`.

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

## Slack Integration (optional)

Enable Slack integration to read team standups and publish your own standup to Slack threads.

### Setup

```bash
# Set channel via CLI
standup config --set-slack-channel standups

# Set bot token via environment variable (recommended for security)
export STANDUP_SLACK_BOT_TOKEN="xoxb-..."
```

### Required Bot Permissions

- `channels:history` - Read messages in public channels
- `channels:read` - View basic channel info
- `chat:write` - Post messages

### Slack Tools

- **`get_team_slack_standups`**: Fetches recent standup threads from configured channel, collects replies from team members
- **`publish_standup_to_slack`**: Posts standup as a reply to the most recent standup thread (requires user confirmation)
- **`confirm_slack_publish`**: Sets confirmation flag after user approves publishing

### Context Fields

The `StandupContext` includes Slack-related state:
- `collected_slack_standups: list[dict]` - Team standup threads and replies
- `slack_thread_ts: str | None` - Thread timestamp for publishing
- `slack_channel_id: str | None` - Resolved channel ID
- `slack_publish_confirmed: bool` - Confirmation flag for publish safety

### Workflow

1. Data Gatherer optionally calls `get_team_slack_standups` if Slack is configured
2. Summarizer can use team context when generating standups
3. User requests "publish to slack" - Coordinator shows preview
4. User confirms - Coordinator calls `confirm_slack_publish` then `publish_standup_to_slack`

## PostHog Instrumentation (optional)

Enable agent tracing to PostHog by setting environment variables:
- `POSTHOG_API_KEY` - Enables PostHog agent tracing when set
- `POSTHOG_HOST` - PostHog host (default: https://us.posthog.com)
- `POSTHOG_DISTINCT_ID` - User identifier (defaults to github_username)
- `POSTHOG_DEBUG` - Set to "true" for verbose PostHog logging

Install the PostHog SDK:
```bash
make install-posthog    # Install with PostHog SDK (v7.7.0+)
# Or install everything:
make install-all        # Install dev + posthog dependencies
```

### Custom Events

When PostHog is enabled, the following custom events are emitted:
- `standup_generated` - Emitted after every standup generation with full summary and metadata
- `$ai_metric` - Emitted when user provides thumbs up/down feedback (linked via `$ai_trace_id`)
- `$ai_feedback` - Emitted when user provides detailed text feedback (linked via `$ai_trace_id`)

Event properties include: `summary`, `github_username`, `days_back`, `date`, `summary_length`, `has_prs`, `has_issues`, `has_commits`, `has_reviews`

### Feedback Tools

The agent can capture user feedback via two tools:
- **`capture_feedback_rating`** - Capture thumbs up/down with optional comment
- **`capture_feedback_text`** - Capture detailed text feedback

These use a hybrid approach: creating both an SDK `custom_span` (shows in trace hierarchy) and a PostHog event (for dashboard queries). The agent automatically detects feedback signals like "good job", "thanks", "not great", etc.
