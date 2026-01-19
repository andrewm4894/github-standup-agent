"""Context management for passing data through agent workflow."""

from dataclasses import dataclass, field
from typing import Any

from github_standup_agent.config import StandupConfig


@dataclass
class StandupContext:
    """
    Context passed to all tools and agents via RunContextWrapper.

    This is NOT sent to the LLM - it's for sharing state between tools.
    """

    # Configuration
    config: StandupConfig

    # Request parameters
    days_back: int = 1
    with_history: bool = False

    # Data collected during the run (populated by tools)
    collected_prs: list[dict[str, Any]] = field(default_factory=list)
    collected_issues: list[dict[str, Any]] = field(default_factory=list)
    collected_commits: list[dict[str, Any]] = field(default_factory=list)
    collected_reviews: list[dict[str, Any]] = field(default_factory=list)

    # Historical context
    recent_standups: list[dict[str, Any]] = field(default_factory=list)

    # Current standup being generated/refined
    current_standup: str | None = None

    # GitHub username (auto-detected or from config)
    github_username: str | None = None

    # Custom style instructions (loaded from config and/or style.md file)
    style_instructions: str | None = None

    # Slack data (populated by tools)
    collected_slack_standups: list[dict[str, Any]] = field(default_factory=list)
    slack_thread_ts: str | None = None  # Thread timestamp for posting replies
    slack_channel_id: str | None = None  # Resolved channel ID

    # Confirmation tracking for publish safety
    slack_publish_confirmed: bool = False
