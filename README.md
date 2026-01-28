# GitHub Standup Agent

[![CI](https://github.com/andrewm4894/github-standup-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/andrewm4894/github-standup-agent/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/github-standup-agent)](https://pypi.org/project/github-standup-agent/)
[![Python](https://img.shields.io/pypi/pyversions/github-standup-agent)](https://pypi.org/project/github-standup-agent/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

AI-powered daily standup summaries from your GitHub activity, built with the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python).

## Features

- **GitHub Activity Collection** — PRs, issues, commits, and code reviews via the `gh` CLI
- **Slack Integration** — Read team standups and publish your own to Slack threads
- **Interactive Chat** — Refine your standup conversationally ("make it shorter", "ignore the docs PR")
- **Session Persistence** — Resume sessions, use named sessions for recurring standups
- **Style Customization** — Define format with `style.md` and example standups
- **History** — References past standups for continuity
- **Multiple Outputs** — Terminal, clipboard, or Slack

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for agent flow, tool patterns, and component details.

## Quick Start

### Prerequisites

- [GitHub CLI](https://cli.github.com/) (`gh`) — installed and authenticated
- [OpenAI API Key](https://platform.openai.com/api-keys)

### Install

```bash
pip install github-standup-agent
```

### Run

```bash
export OPENAI_API_KEY="sk-..."

# One-shot standup
standup generate

# Look back 3 days, copy to clipboard
standup generate --days 3 --output clipboard

# Save to a text file
standup generate --output file --output-file standup.txt

# Interactive chat mode
standup chat
```

### Chat Example

```
> generate my standup
[standup generated]

> make it less wordy
[shorter version]

> copy to clipboard
✅ Copied!

> publish to slack
✅ Posted to #standups
```

## Configuration

```bash
standup config --show                              # View current config
standup config --set-style "Be concise. Use bullets."  # Set style
standup config --init-style                        # Create style.md template
standup config --init-examples                     # Create examples.md template
standup config --set-slack-channel standups         # Set Slack channel
```

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required) | - |
| `STANDUP_GITHUB_USER` | GitHub username | Auto-detected |
| `STANDUP_COORDINATOR_MODEL` | Coordinator agent model | gpt-5.2 |
| `STANDUP_DATA_GATHERER_MODEL` | Data gatherer model | gpt-5.2 |
| `STANDUP_SUMMARIZER_MODEL` | Summarizer model | gpt-5.2 |
| `STANDUP_SLACK_BOT_TOKEN` | Slack bot token | - |
| `STANDUP_SLACK_CHANNEL` | Default Slack channel | - |
| `STANDUP_CONFIG_DIR` | Config directory | `./config/` |
| `STANDUP_DATA_DIR` | Data directory | `./.standup-data/` |

Priority: `.env` > `config/config.json` > defaults

### Slack Setup

Set `STANDUP_SLACK_BOT_TOKEN` and configure a channel. Required bot permissions: `channels:history`, `channels:read`, `chat:write`.

## Development

```bash
git clone https://github.com/andrewm4894/github-standup-agent
cd github-standup-agent
make install-dev    # Install with dev deps
make check          # Run lint + type-check + tests
make format         # Auto-format
```

## License

MIT — see [LICENSE](LICENSE).
