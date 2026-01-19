"""Tools for data gathering and integration."""

from github_standup_agent.tools.clipboard import copy_to_clipboard
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
from github_standup_agent.tools.history import (
    get_recent_standups,
    save_standup,
    save_standup_to_file,
)
from github_standup_agent.tools.slack import (
    confirm_slack_publish,
    get_team_slack_standups,
    publish_standup_to_slack,
)

__all__ = [
    # GitHub tools - overview
    "get_activity_feed",
    "get_activity_summary",
    # GitHub tools - list
    "list_prs",
    "list_issues",
    "list_commits",
    "list_reviews",
    # GitHub tools - details
    "get_pr_details",
    "get_issue_details",
    # Utility tools
    "copy_to_clipboard",
    "get_recent_standups",
    "save_standup",
    "save_standup_to_file",
    # Slack tools
    "get_team_slack_standups",
    "publish_standup_to_slack",
    "confirm_slack_publish",
]
