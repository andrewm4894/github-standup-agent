"""Data Gatherer Agent - collects GitHub activity data."""

from agents import Agent, AgentHooks, ModelSettings

from github_standup_agent.config import DEFAULT_MODEL
from github_standup_agent.context import StandupContext
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

DATA_GATHERER_INSTRUCTIONS = """You are a GitHub data gathering specialist. Your job is to collect
comprehensive information about a user's GitHub activity and team context.

RECOMMENDED APPROACH:
1. Start with get_activity_feed() - chronological list of all your GitHub activity
2. Call get_team_slack_standups() - get team context from recent standups (IMPORTANT for context)
3. Use list tools for more detail on specific categories (PRs, issues, reviews, commits, comments)
4. Use detail tools (get_pr_details, get_issue_details) to drill into specific items when needed

AVAILABLE TOOLS:

Overview tools:
- get_activity_feed: Complete chronological feed of all GitHub activity (START HERE)
- get_activity_summary: Aggregate contribution statistics

Team context (ALWAYS call this if Slack is configured):
- get_team_slack_standups: Recent team standups from Slack showing what teammates are working on
  This provides valuable context about team priorities, blockers, and collaboration opportunities.
  IMPORTANT: Add 3 extra days to days_back for better context
  (e.g., if days_back=1, use days_back=4)

List tools (with date filters):
- list_prs: PRs with filter_by options: authored, reviewed, assigned, involves, review-requested
- list_issues: Issues with filter_by options: authored, assigned, mentions, involves
- list_commits: Commits with optional repo filter
- list_reviews: Code reviews given or received, with actual states (APPROVED, etc.)
- list_comments: Comments made on issues and PRs

Assigned items (NO date filter - shows all open assignments):
- list_assigned_items: All open issues/PRs assigned to user, regardless of activity

Detail tools (drill-down for full context):
- get_pr_details: Full PR context - body, review decision, linked issues, CI status, labels
- get_issue_details: Full issue context - body, linked PRs, labels, milestone

DRILL-DOWN PATTERN:
After getting the overview and team context:
- If a PR looks significant, use get_pr_details(repo, number) for full context
- If an issue needs more context, use get_issue_details(repo, number)
- For reviews you gave on others' PRs, use list_reviews(filter_by="given")
- For all open assignments (regardless of activity), use list_assigned_items

Be thorough - gather everything that might be relevant for a standup summary.

CRITICAL OUTPUT FORMAT:
Return the RAW data you collected - do NOT format it as a standup.
Just list the factual information:
- PRs: titles, numbers, repos, status (merged/open/draft), URLs
- Issues: titles, numbers, repos, status, URLs
- Reviews: what you reviewed, what state (approved, commented, etc.)
- Commits: notable commits
- Team context: what teammates mentioned in their standups

Do NOT use standup headers like "Did:" or "### Yesterday" or "**Did:**".
Do NOT try to be concise - include all the raw data for the summarizer to work with.
The summarizer will format it according to the user's style preferences.

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
