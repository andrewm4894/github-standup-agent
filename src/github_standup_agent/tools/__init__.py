"""Tools for data gathering and integration."""

from github_standup_agent.tools.clipboard import copy_to_clipboard
from github_standup_agent.tools.feedback import (
    capture_feedback_rating,
    capture_feedback_text,
)
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
from github_standup_agent.tools.history import save_standup_to_file
from github_standup_agent.tools.slack import (
    confirm_slack_publish,
    get_team_slack_standups,
    publish_standup_to_slack,
)
from github_standup_agent.tools.tasks import (
    complete_task,
    get_todays_work_log,
    link_task,
    list_my_tasks,
    log_task,
    update_task,
)

__all__ = [
    # GitHub tools - overview
    "get_activity_feed",
    "get_activity_summary",
    # GitHub tools - list (with date filters)
    "list_prs",
    "list_issues",
    "list_commits",
    "list_reviews",
    "list_comments",
    # GitHub tools - assigned (no date filter)
    "list_assigned_items",
    # GitHub tools - details
    "get_pr_details",
    "get_issue_details",
    # Utility tools
    "copy_to_clipboard",
    "save_standup_to_file",
    # Slack tools
    "get_team_slack_standups",
    "publish_standup_to_slack",
    "confirm_slack_publish",
    # Feedback tools
    "capture_feedback_rating",
    "capture_feedback_text",
    # Task tracking tools
    "log_task",
    "update_task",
    "complete_task",
    "list_my_tasks",
    "get_todays_work_log",
    "link_task",
]
