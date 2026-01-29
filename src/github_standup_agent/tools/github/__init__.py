"""GitHub CLI tools for data gathering."""

from github_standup_agent.tools.github.github_activity import get_activity_summary
from github_standup_agent.tools.github.github_assigned import list_assigned_items
from github_standup_agent.tools.github.github_comments import list_comments
from github_standup_agent.tools.github.github_commits import list_commits
from github_standup_agent.tools.github.github_events import get_activity_feed
from github_standup_agent.tools.github.github_issues import get_issue_details, list_issues
from github_standup_agent.tools.github.github_prs import get_pr_details, list_prs
from github_standup_agent.tools.github.github_reviews import list_reviews

__all__ = [
    # Activity overview
    "get_activity_feed",
    "get_activity_summary",
    # List tools (with date filters)
    "list_prs",
    "list_issues",
    "list_commits",
    "list_reviews",
    "list_comments",
    # Assigned items (no date filter)
    "list_assigned_items",
    # Detail tools
    "get_pr_details",
    "get_issue_details",
]
