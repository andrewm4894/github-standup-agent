"""Tool for fetching issues from GitHub."""

import json
import subprocess
from datetime import datetime, timedelta
from typing import Annotated

from agents import function_tool

from github_standup_agent.context import StandupContext


@function_tool
def get_my_issues(
    context: StandupContext,
    days_back: Annotated[int, "Number of days to look back for issues"] = 7,
    include_assigned: Annotated[bool, "Include issues assigned to you"] = True,
    include_created: Annotated[bool, "Include issues you created"] = True,
) -> str:
    """
    Fetch issues assigned to or created by the current user.

    Returns issues that are open or were recently closed.
    """
    username = context.github_username or "@me"
    cutoff_date = datetime.now() - timedelta(days=days_back)

    all_issues: list[dict] = []

    # Fetch assigned issues
    if include_assigned:
        try:
            result = subprocess.run(
                [
                    "gh", "issue", "list",
                    "--assignee", username,
                    "--state", "all",
                    "--json", "number,title,url,state,createdAt,updatedAt,closedAt,labels",
                    "--limit", "50",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                issues = json.loads(result.stdout)
                for issue in issues:
                    # Filter by date
                    updated_at = issue.get("updatedAt")
                    if updated_at:
                        updated_date = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                        if updated_date.replace(tzinfo=None) >= cutoff_date:
                            issue["source"] = "assigned"
                            all_issues.append(issue)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

    # Fetch created issues (if different from assigned)
    if include_created:
        try:
            result = subprocess.run(
                [
                    "gh", "issue", "list",
                    "--author", username,
                    "--state", "all",
                    "--json", "number,title,url,state,createdAt,updatedAt,closedAt,labels",
                    "--limit", "50",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                issues = json.loads(result.stdout)
                existing_numbers = {i["number"] for i in all_issues}
                for issue in issues:
                    if issue["number"] not in existing_numbers:
                        updated_at = issue.get("updatedAt")
                        if updated_at:
                            updated_date = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                            if updated_date.replace(tzinfo=None) >= cutoff_date:
                                issue["source"] = "created"
                                all_issues.append(issue)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

    # Store in context
    context.collected_issues = all_issues

    if not all_issues:
        return "No issues found in the specified time range."

    # Format output
    lines = [f"Found {len(all_issues)} issue(s):\n"]
    for issue in all_issues:
        status_emoji = "🔵" if issue["state"] == "OPEN" else "⚫"
        labels = ", ".join(l["name"] for l in issue.get("labels", [])) or "no labels"
        lines.append(
            f"{status_emoji} #{issue['number']}: {issue['title']}\n"
            f"   State: {issue['state']} | Labels: {labels}\n"
            f"   URL: {issue['url']}\n"
        )

    return "\n".join(lines)
