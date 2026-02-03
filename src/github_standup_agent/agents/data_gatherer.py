"""Data Gatherer Agent - collects GitHub activity data."""

from agents import Agent, AgentHooks, ModelSettings

from github_standup_agent.config import DEFAULT_MODEL
from github_standup_agent.context import StandupContext
from github_standup_agent.prompts import get_prompt
from github_standup_agent.tools.github import (
    get_activity_feed,
    get_activity_summary,
    get_issue_details,
    get_pr_details,
    list_assigned_items,
    list_comments,
    list_commits,
    list_issues,
    list_prs,
    list_reviews,
)
from github_standup_agent.tools.slack import get_team_slack_standups


def create_data_gatherer_agent(
    model: str = DEFAULT_MODEL,
    hooks: AgentHooks[StandupContext] | None = None,
) -> Agent[StandupContext]:
    """Create the data gatherer agent with all GitHub tools."""
    return Agent[StandupContext](
        name="Data Gatherer",
        handoff_description="Gathers GitHub activity data (PRs, issues, commits, reviews)",
        instructions=get_prompt("data-gatherer-instructions"),
        tools=[
            # Overview tools
            get_activity_feed,
            get_activity_summary,
            # List tools (with date filters)
            list_prs,
            list_issues,
            list_commits,
            list_reviews,
            list_comments,
            # Assigned items (no date filter)
            list_assigned_items,
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
