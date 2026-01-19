"""Data Gatherer Agent - collects GitHub activity data."""

from agents import Agent, AgentHooks, ModelSettings

from github_standup_agent.config import DEFAULT_MODEL
from github_standup_agent.context import StandupContext
from github_standup_agent.tools.github import (
    get_activity_feed,
    get_activity_summary,
    get_issue_details,
    get_pr_details,
    list_commits,
    list_issues,
    list_prs,
    list_reviews,
)
from github_standup_agent.tools.slack import get_team_slack_standups

DATA_GATHERER_INSTRUCTIONS = """You are a GitHub data gathering specialist. Your job is to collect
comprehensive information about a user's GitHub activity.

RECOMMENDED APPROACH:
1. Start with get_activity_feed() - this gives you a complete chronological list of all activity
   (commits, PRs, reviews, issues, comments) in one call
2. Use list tools for more detail on specific categories (PRs, issues, reviews, commits)
3. Use detail tools (get_pr_details, get_issue_details) to drill into specific items when needed
4. Fetch team standups from Slack (if configured)

AVAILABLE TOOLS:

Overview tools:
- get_activity_feed: Complete chronological feed of all GitHub activity (START HERE)
- get_activity_summary: Aggregate contribution statistics

List tools (flexible filtering):
- list_prs: PRs with filter_by options: authored, reviewed, assigned, involves, review-requested
- list_issues: Issues with filter_by options: authored, assigned, mentions, involves
- list_commits: Commits with optional repo filter
- list_reviews: Code reviews given or received, with actual states (APPROVED, etc.)

Detail tools (drill-down for full context):
- get_pr_details: Full PR context - body, review decision, linked issues, CI status, labels
- get_issue_details: Full issue context - body, linked PRs, labels, milestone

Slack tools:
- get_team_slack_standups: Team standups from Slack (if configured)

DRILL-DOWN PATTERN:
Use get_activity_feed() first for the overview, then:
- If a PR looks significant, use get_pr_details(repo, number) for full context
- If an issue needs more context, use get_issue_details(repo, number)
- For reviews you gave on others' PRs, use list_reviews(filter_by="given")

Be thorough - gather everything that might be relevant for a standup summary.
After gathering data, provide a brief summary of what you found.

Important: Use the context's days_back value to determine the time range for data gathering.
"""


def create_data_gatherer_agent(
    model: str = DEFAULT_MODEL,
    hooks: AgentHooks[StandupContext] | None = None,
) -> Agent[StandupContext]:
    """Create the data gatherer agent with all GitHub tools."""
    return Agent[StandupContext](
        name="Data Gatherer",
        handoff_description="Gathers GitHub activity data (PRs, issues, commits, reviews)",
        instructions=DATA_GATHERER_INSTRUCTIONS,
        tools=[
            # Overview tools
            get_activity_feed,
            get_activity_summary,
            # List tools
            list_prs,
            list_issues,
            list_commits,
            list_reviews,
            # Detail tools
            get_pr_details,
            get_issue_details,
            # Slack tools
            get_team_slack_standups,
        ],
        model=model,
        model_settings=ModelSettings(
            temperature=0.3,  # Lower temperature for more deterministic tool usage
        ),
        hooks=hooks,
    )


# Default instance
data_gatherer_agent = create_data_gatherer_agent()
