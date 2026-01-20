# GitHub Standup Agent

AI-powered daily standup summaries from your GitHub activity, built with the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python).

## Features

- **Automatic GitHub Activity Collection**: Pulls your PRs, issues, commits, and code reviews using the `gh` CLI
- **Slack Integration**: Read team standups for context and publish your standup directly to Slack threads
- **AI-Powered Summarization**: Creates concise, well-formatted standup summaries
- **Interactive Chat Mode**: Refine your standup through conversation ("make it shorter", "ignore the docs PR")
- **Session Persistence**: Resume chat sessions later, use named sessions for recurring standups
- **Style Customization**: Define your team's standup format with `style.md` and example standups
- **Historical Context**: References past standups to maintain continuity and avoid repetition
- **Multiple Output Options**: Print to terminal, copy to clipboard, or publish to Slack
- **Fully Local**: Your data never leaves your machine (except for OpenAI/Slack API calls)

## Architecture

This project showcases many features of the OpenAI Agents SDK:

- **Multi-Agent Workflow**: Coordinator → Data Gatherer → Summarizer
- **Function Tools**: `@function_tool` decorated functions for GitHub CLI operations
- **Handoffs**: Agents delegate to specialized sub-agents
- **Guardrails**: Input validation and PII detection
- **Hooks**: Logging and observability
- **Sessions**: SQLite-based history for past standups

## Installation

### Prerequisites

1. **GitHub CLI**: Install and authenticate with `gh`
   ```bash
   # macOS
   brew install gh

   # Then authenticate
   gh auth login
   ```

2. **OpenAI API Key**: Get one from [OpenAI](https://platform.openai.com/api-keys)

### Install from PyPI

```bash
pip install github-standup-agent
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv pip install github-standup-agent
```

### Install from Source

```bash
git clone https://github.com/andymaguire/github-standup-agent
cd github-standup-agent
uv pip install -e ".[dev]"
```

## Usage

### Set your OpenAI API key

```bash
export OPENAI_API_KEY="sk-..."
```

### Generate a Standup (One-Shot)

```bash
# Generate standup for today
standup generate

# Look back 3 days
standup generate --days 3

# Copy directly to clipboard
standup generate --output clipboard

# Include context from recent standups
standup generate --with-history
```

### Interactive Chat Mode

Start an interactive session to refine your standup:

```bash
standup chat
```

Example session:
```
> generate my standup

**Yesterday:**
- Merged PR #123: Add user authentication
- Reviewed PR #456: Fix login bug
- Closed issue #789: Update documentation

**Today:**
- Working on PR #124: Add OAuth support (in progress)
- Assigned to issue #790: Performance optimization

**Blockers:**
- Waiting for API access from platform team

> make it less wordy

**Yesterday:** Merged auth PR, reviewed login fix, updated docs
**Today:** OAuth support PR, performance optimization
**Blockers:** Waiting on platform team API access

> ignore the docs, focus on auth work

**Yesterday:** Merged user authentication PR #123
**Today:** Continuing OAuth support (PR #124)
**Blockers:** Waiting on platform team API access

> perfect, copy to clipboard
✅ Copied to clipboard!

> publish to slack
✅ Posted standup to #standups
```

### View History

```bash
# List recent standups
standup history --list

# View a specific date
standup history --date 2025-01-14

# Clear history
standup history --clear
```

### Chat Sessions

Chat sessions are automatically saved and can be resumed:

```bash
# Start a new session (auto-named by date)
standup chat

# Resume the last session
standup chat --resume

# Use a named session
standup chat --session weekly

# List recent sessions
standup sessions --list

# Clear all sessions
standup sessions --clear
```

### Style Customization

Customize how your standups are generated to match your team's format:

```bash
# Set quick style instructions
standup config --set-style "Use 'Did:' and 'Will Do:' sections. Be concise."

# Create and edit a detailed style guide
standup config --init-style
standup config --edit-style
```

### Example Standups (Few-Shot Prompting)

Provide real examples of standups you like. The AI uses these to match your preferred tone and format:

```bash
# Create and edit examples file
standup config --init-examples
standup config --edit-examples
```

See `config/style.example.md` and `config/examples.example.md` for templates.

**File locations:** Config files live in `./config/` by default (customizable via `STANDUP_CONFIG_DIR`). Personal config files are gitignored while templates (`*.example.*`) are committed.

### Slack Integration

Optionally connect to Slack to read team standups and publish your own:

```bash
# Set your Slack channel
standup config --set-slack-channel standups

# Set your Slack bot token (keep this secure)
export STANDUP_SLACK_BOT_TOKEN="xoxb-..."
```

**Required Slack Bot Permissions:**
- `channels:history` - Read messages in public channels
- `channels:read` - View basic channel info
- `chat:write` - Post messages

**In chat mode, you can publish directly to Slack:**
```
> generate my standup
[standup generated]

> publish to slack
Preview: Your standup will be posted to #standups...
Please confirm by saying "yes" or "publish it"

> yes
✅ Posted standup to #standups
```

The agent reads existing standup threads (posts starting with "Standup") and publishes your standup as a reply to the most recent thread.

### Configuration

```bash
# Show current config
standup config --show

# Set GitHub username (auto-detected by default)
standup config --set-github-user myusername

# Set model for summarization
standup config --set-model gpt-5.2
```

## Configuration Options

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required) | - |
| `STANDUP_GITHUB_USER` | GitHub username | Auto-detected |
| `STANDUP_COORDINATOR_MODEL` | Model for coordinator agent | gpt-5.2 |
| `STANDUP_DATA_GATHERER_MODEL` | Model for data gathering | gpt-5.2 |
| `STANDUP_SUMMARIZER_MODEL` | Model for summarization | gpt-5.2 |
| `STANDUP_SLACK_BOT_TOKEN` | Slack bot token for integration | - |
| `STANDUP_SLACK_CHANNEL` | Default Slack channel (or use config) | - |
| `STANDUP_CONFIG_DIR` | Config directory location | `./config/` |
| `STANDUP_DATA_DIR` | Data directory location | `./.standup-data/` |

**Priority:** `.env` > `config/config.json` > defaults

Config file: `./config/config.json` (see `config/config.example.json` for template)

## Development

```bash
# Clone the repo
git clone https://github.com/andymaguire/github-standup-agent
cd github-standup-agent

# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check src/

# Run type checking
mypy src/
```

## How It Works

```
┌─────────────────────────────┐
│    Coordinator Agent        │
│  (Orchestrates workflow)    │
└────────────┬────────────────┘
             │ handoffs
     ┌───────┴───────┐
     ▼               ▼
┌──────────────┐ ┌──────────────┐
│ Data Gatherer│ │  Summarizer  │
│  (gpt-5.2)   │ │  (gpt-5.2)   │
└──────────────┘ └──────────────┘
       │                │
       ▼                ▼
  GitHub CLI        Past Standups
  (gh commands)     (SQLite DB)
```

1. **Coordinator** receives your request and routes it appropriately
2. **Data Gatherer** uses `gh` CLI tools to collect PRs, issues, commits, reviews
3. **Summarizer** creates a formatted standup, referencing past standups for context
4. You can refine through chat, copy to clipboard, or save to history

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please open an issue or PR.

## Acknowledgments

- Built with the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
- Uses the [GitHub CLI](https://cli.github.com/) for data gathering
- CLI powered by [Typer](https://typer.tiangolo.com/)
