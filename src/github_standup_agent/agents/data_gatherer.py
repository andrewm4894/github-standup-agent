"""Data Gatherer Agent - collects GitHub activity data."""

from agents import Agent, ModelSettings

from github_standup_agent.context import StandupContext
from github_standup_agent.tools.github_prs import get_my_prs
from github_standup_agent.tools.github_issues import get_my_issues
from github_standup_agent.tools.github_commits import get_my_commits
from github_standup_agent.tools.github_reviews import get_my_reviews
from github_standup_agent.tools.github_activity import get_activity_summary


DATA_GATHERER_INSTRUCTIONS = """You are a GitHub data gathering specialist. Your job is to collect
comprehensive information about a user's GitHub activity.

When asked to gather data, use ALL available tools to collect:
1. Pull Requests (open and recently merged)
2. Issues (assigned and created)
3. Recent commits
4. Code review activity
5. Overall activity summary

Be thorough - gather everything that might be relevant for a standup summary.
After gathering data, provide a brief summary of what you found.

Important: Use the context's days_back value to determine the time range for data gathering.
"""


def create_data_gatherer_agent(model: str = "gpt-4o-mini") -> Agent[StandupContext]:
    """Create the data gatherer agent with all GitHub tools."""
    return Agent[StandupContext](
        name="Data Gatherer",
        handoff_description="Gathers GitHub activity data (PRs, issues, commits, reviews)",
        instructions=DATA_GATHERER_INSTRUCTIONS,
        tools=[
            get_my_prs,
            get_my_issues,
            get_my_commits,
            get_my_reviews,
            get_activity_summary,
        ],
        model=model,
        model_settings=ModelSettings(
            temperature=0.3,  # Lower temperature for more deterministic tool usage
        ),
    )


# Default instance
data_gatherer_agent = create_data_gatherer_agent()
