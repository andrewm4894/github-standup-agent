# Architecture

This document describes the architecture of the GitHub Standup Agent, a multi-agent system built with the OpenAI Agents SDK.

## High-Level Overview

```mermaid
flowchart TB
    subgraph CLI["CLI Layer"]
        generate["standup generate"]
        chat["standup chat"]
        history["standup history"]
        config["standup config"]
    end

    subgraph Runner["Runner Layer"]
        run_standup["run_standup_generation()"]
        run_chat["run_interactive_chat()"]
    end

    subgraph Agents["Agent Layer"]
        coord["Coordinator Agent"]
        dg["Data Gatherer Agent"]
        sum["Summarizer Agent"]
    end

    subgraph Tools["Tool Layer"]
        gh_tools["GitHub Tools"]
        slack_tools["Slack Tools"]
        util_tools["Utility Tools"]
    end

    subgraph External["External Services"]
        gh_cli["gh CLI"]
        slack_api["Slack API"]
        openai["OpenAI API"]
    end

    subgraph Storage["Persistence Layer"]
        config_json["config.json"]
        style_md["style.md"]
        examples_md["examples.md"]
        history_db["standup_history.db"]
        sessions_db["chat_sessions.db"]
    end

    generate --> run_standup
    chat --> run_chat
    history --> history_db
    config --> config_json

    run_standup --> coord
    run_chat --> coord

    coord -->|"as_tool()"| dg
    coord -->|"as_tool()"| sum
    coord --> util_tools
    coord --> slack_tools

    dg --> gh_tools
    dg --> slack_tools
    sum --> util_tools

    gh_tools --> gh_cli
    slack_tools --> slack_api
    coord --> openai
    dg --> openai
    sum --> openai

    run_standup --> config_json
    run_standup --> style_md
    run_standup --> examples_md
    run_chat --> sessions_db
```

## Agent Architecture

The system uses the **agents-as-tools** pattern from the OpenAI Agents SDK. Sub-agents are wrapped as tools and invoked by the coordinator.

```mermaid
flowchart LR
    subgraph Coordinator["Coordinator Agent"]
        direction TB
        c_inst["Instructions"]
        c_tools["Tools:<br/>- gather_github_data<br/>- create_standup_summary<br/>- copy_to_clipboard<br/>- save_standup<br/>- publish_standup_to_slack"]
    end

    subgraph DataGatherer["Data Gatherer Agent (as tool)"]
        direction TB
        dg_inst["Instructions"]
        dg_tools["Tools:<br/>- get_my_prs<br/>- get_my_issues<br/>- get_my_commits<br/>- get_my_reviews<br/>- get_activity_summary<br/>- get_team_slack_standups"]
    end

    subgraph Summarizer["Summarizer Agent (as tool)"]
        direction TB
        s_inst["Instructions + Style"]
        s_tools["Tools:<br/>- get_recent_standups<br/>- save_standup<br/>- copy_to_clipboard"]
    end

    Coordinator -->|"gather_github_data"| DataGatherer
    Coordinator -->|"create_standup_summary"| Summarizer
```

### Agent Responsibilities

| Agent | Model | Temperature | Responsibility |
|-------|-------|-------------|----------------|
| **Coordinator** | gpt-5.2 | 0.5 | Orchestrates workflow, handles user commands |
| **Data Gatherer** | gpt-5.2 | 0.3 | Collects GitHub activity via `gh` CLI |
| **Summarizer** | gpt-5.2 | 0.7 | Creates human-readable standup summaries |

## Data Flow

### Generate Mode

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Runner
    participant Coordinator
    participant DataGatherer
    participant Summarizer
    participant GitHub as gh CLI
    participant Slack as Slack API

    User->>CLI: standup generate --days 1
    CLI->>Runner: run_standup_generation()
    Runner->>Runner: Load config, style, context
    Runner->>Coordinator: "Generate standup for last 1 day(s)"

    Coordinator->>DataGatherer: gather_github_data
    DataGatherer->>GitHub: get_my_prs
    GitHub-->>DataGatherer: PR data
    DataGatherer->>GitHub: get_my_issues
    GitHub-->>DataGatherer: Issue data
    DataGatherer->>GitHub: get_my_commits
    GitHub-->>DataGatherer: Commit data
    DataGatherer->>GitHub: get_my_reviews
    GitHub-->>DataGatherer: Review data

    opt Slack configured
        DataGatherer->>Slack: get_team_slack_standups
        Slack-->>DataGatherer: Team standups
    end

    DataGatherer-->>Coordinator: "Found X PRs, Y issues..."

    Coordinator->>Summarizer: create_standup_summary
    Summarizer-->>Coordinator: Formatted standup

    Coordinator-->>Runner: Final standup
    Runner-->>CLI: Output
    CLI-->>User: Display standup
```

### Chat Mode

```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant Runner
    participant Session as SQLiteSession
    participant Coordinator

    User->>CLI: standup chat --resume
    CLI->>Runner: run_interactive_chat()
    Runner->>Session: Load conversation history
    Session-->>Runner: Previous messages

    loop Interactive Loop
        User->>Runner: User input
        Runner->>Coordinator: Process with context
        Coordinator-->>Runner: Response
        Runner->>Session: Save to history
        Runner-->>User: Display response
    end

    User->>Runner: "exit"
    Runner->>Session: Close connection
```

### Slack Publish Flow

```mermaid
sequenceDiagram
    participant User
    participant Coordinator
    participant SlackTools as Slack Tools
    participant Context as StandupContext
    participant Slack as Slack API

    User->>Coordinator: "publish to slack"
    Coordinator->>Context: Stage standup content
    Coordinator->>SlackTools: publish_standup_to_slack(confirmed=false)
    SlackTools-->>Coordinator: Preview shown, awaiting confirmation

    Coordinator-->>User: "Ready to publish. Confirm?"
    User->>Coordinator: "yes"

    Coordinator->>SlackTools: confirm_slack_publish()
    SlackTools->>Context: Set slack_publish_confirmed=true

    Coordinator->>SlackTools: publish_standup_to_slack(confirmed=true)
    SlackTools->>Slack: Post to thread
    Slack-->>SlackTools: Success
    SlackTools-->>Coordinator: "Published!"
    Coordinator-->>User: Confirmation
```

## Context & State

### StandupContext (Runtime State)

The `StandupContext` dataclass is passed through all agents and tools via `RunContextWrapper`. It holds transient per-run state (not persisted between runs).

```mermaid
classDiagram
    class StandupContext {
        +StandupConfig config
        +int days_back
        +bool with_history
        +list~dict~ collected_prs
        +list~dict~ collected_issues
        +list~dict~ collected_commits
        +list~dict~ collected_reviews
        +list~dict~ recent_standups
        +str current_standup
        +str github_username
        +str style_instructions
        +list~dict~ collected_slack_standups
        +str slack_thread_ts
        +str slack_channel_id
        +bool slack_publish_confirmed
        +str slack_standup_to_publish
    }

    class Tool {
        +function_tool decorator
        +ctx: RunContextWrapper~StandupContext~
    }

    Tool --> StandupContext : reads/writes
```

### Persistence Layer

```mermaid
flowchart TB
    subgraph ConfigDir["~/.config/standup-agent/"]
        config_json["config.json<br/><i>User preferences</i>"]
        style_md["style.md<br/><i>Detailed formatting rules</i>"]
        examples_md["examples.md<br/><i>Few-shot examples</i>"]
        history_db["standup_history.db<br/><i>Generated standups + raw data</i>"]
        sessions_db["chat_sessions.db<br/><i>Conversation history</i>"]
    end

    subgraph LocalDir["./  (optional)"]
        local_style["style.md<br/><i>Project-specific style</i>"]
        local_examples["examples.md<br/><i>Project-specific examples</i>"]
    end

    subgraph Runtime["Runtime"]
        context["StandupContext<br/><i>Ephemeral per-run state</i>"]
        clipboard["System Clipboard<br/><i>Copied standups</i>"]
    end

    subgraph Cloud["Cloud (optional)"]
        posthog["PostHog<br/><i>Analytics events</i>"]
        slack["Slack<br/><i>Published standups</i>"]
    end
```

### Storage Summary

| Storage | File | Persisted | Purpose |
|---------|------|-----------|---------|
| **Config** | `config.json` | Yes | User preferences (model, channel, etc.) |
| **Style** | `style.md` | Yes | Detailed standup formatting instructions |
| **Examples** | `examples.md` | Yes | Few-shot prompting examples |
| **History DB** | `standup_history.db` | Yes | Generated standups + raw GitHub data |
| **Sessions DB** | `chat_sessions.db` | Yes | Chat conversation history (SDK managed) |
| **Context** | In-memory | No | Per-run state shared between agents/tools |
| **Clipboard** | System | No | Temporary standup copy |
| **PostHog** | Cloud | Yes | Usage analytics (opt-in) |
| **Slack** | Cloud | Yes | Published standups in threads |

## Tool Inventory

### GitHub Tools (Data Gatherer)

| Tool | File | Description |
|------|------|-------------|
| `get_my_prs` | `tools/github_prs.py` | Fetch PRs authored by user |
| `get_my_issues` | `tools/github_issues.py` | Fetch issues assigned/created |
| `get_my_commits` | `tools/github_commits.py` | Fetch recent commits |
| `get_my_reviews` | `tools/github_reviews.py` | Fetch code review activity |
| `get_activity_summary` | `tools/github_activity.py` | Overall activity summary |

### Slack Tools

| Tool | File | Description |
|------|------|-------------|
| `get_team_slack_standups` | `tools/slack_standups.py` | Read team standup threads |
| `publish_standup_to_slack` | `tools/slack_publish.py` | Post standup to thread |
| `confirm_slack_publish` | `tools/slack_publish.py` | Set confirmation flag |

### Utility Tools

| Tool | File | Description |
|------|------|-------------|
| `copy_to_clipboard` | `tools/clipboard.py` | Copy standup to clipboard |
| `get_recent_standups` | `tools/history.py` | Fetch from history DB |
| `save_standup` | `tools/history.py` | Save to history DB |
| `save_standup_to_file` | `tools/history.py` | Export to markdown file |

## Guardrails

The system includes input/output guardrails for validation:

| Guardrail | Type | Purpose |
|-----------|------|---------|
| `validate_days_guardrail` | Input | Limits `days_back` to reasonable range |
| `pii_check_guardrail` | Output | Checks for PII in generated content |

## Configuration Hierarchy

Style and examples are loaded with the following priority:

```mermaid
flowchart TB
    subgraph Priority["Load Order (highest to lowest)"]
        local_style["./style.md"] --> global_style["~/.config/standup-agent/style.md"]
        local_examples["./examples.md"] --> global_examples["~/.config/standup-agent/examples.md"]
        config_style["config.json: style_instructions"]
    end

    global_style --> combined["get_combined_style_instructions()"]
    global_examples --> combined
    config_style --> combined
    combined --> summarizer["Summarizer Agent Prompt"]
```

## Observability

### Hooks

The system uses the OpenAI Agents SDK hooks for logging:

- **`StandupRunHooks`**: Run-level events (start, end, tool calls)
- **`StandupAgentHooks`**: Agent-level events (for verbose mode)

### PostHog Integration (Optional)

When `POSTHOG_API_KEY` is set:

| Event | When | Properties |
|-------|------|------------|
| `standup_generated` | After every generation | summary, username, days_back, metadata |
| `standup_saved` | When explicitly saved | Same as above |

## Directory Structure

```
src/github_standup_agent/
├── cli.py                 # Typer CLI entry point
├── runner.py              # Agent execution (generate/chat modes)
├── context.py             # StandupContext dataclass
├── config.py              # Configuration loading/saving
├── db.py                  # SQLite history database
├── hooks.py               # Run/Agent hooks for logging
├── instrumentation.py     # PostHog integration
├── agents/
│   ├── coordinator.py     # Main orchestrator agent
│   ├── data_gatherer.py   # GitHub data collection agent
│   └── summarizer.py      # Summary generation agent
├── tools/
│   ├── github_*.py        # GitHub CLI wrappers
│   ├── slack_*.py         # Slack API tools
│   ├── clipboard.py       # System clipboard
│   └── history.py         # History DB tools
└── guardrails/
    ├── input_guardrails.py
    └── output_guardrails.py
```

## Key Design Decisions

1. **Agents-as-Tools Pattern**: Sub-agents are invoked as tools rather than handoffs for more reliable execution flow.

2. **Context Passing**: `StandupContext` is passed via `RunContextWrapper`, keeping state out of the LLM but accessible to all tools.

3. **Two-Step Slack Publish**: Requires explicit user confirmation before publishing to prevent accidental posts.

4. **Style Priority**: Local project files override global config, allowing per-repo customization.

5. **Dual Database Design**:
   - `standup_history.db`: Custom schema for standups + raw data (app-managed)
   - `chat_sessions.db`: SDK-managed conversation persistence

## Open Questions

- **Is `standup_history.db` still needed?** With Slack integration, standups now live in Slack threads. The local DB provides offline access and raw data storage, but may be redundant for users who publish to Slack.
