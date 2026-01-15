"""Tool for fetching pull requests from GitHub."""

import json
import subprocess
from datetime import datetime, timedelta
from typing import Annotated

from agents import function_tool

from github_standup_agent.context import StandupContext


@function_tool
def get_my_prs(
    context: StandupContext,
    days_back: Annotated[int, "Number of days to look back for PRs"] = 1,
    include_open: Annotated[bool, "Include currently open PRs"] = True,
    include_merged: Annotated[bool, "Include recently merged PRs"] = True,
) -> str:
    """
    Fetch pull requests authored by the current user.

    Returns PRs that were created, updated, or merged within the specified time range.
    """
    username = context.github_username or "@me"
    cutoff_date = datetime.now() - timedelta(days=days_back)

    all_prs: list[dict] = []

    # Fetch open PRs
    if include_open:
        try:
            result = subprocess.run(
                [
                    "gh", "pr", "list",
                    "--author", username,
                    "--state", "open",
                    "--json", "number,title,url,state,createdAt,updatedAt,baseRefName,headRefName,isDraft,additions,deletions",
                    "--limit", "50",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                prs = json.loads(result.stdout)
                for pr in prs:
                    pr["status"] = "open"
                    all_prs.append(pr)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

    # Fetch merged PRs
    if include_merged:
        try:
            result = subprocess.run(
                [
                    "gh", "pr", "list",
                    "--author", username,
                    "--state", "merged",
                    "--json", "number,title,url,state,createdAt,updatedAt,mergedAt,baseRefName,headRefName,additions,deletions",
                    "--limit", "50",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                prs = json.loads(result.stdout)
                for pr in prs:
                    # Filter by merge date
                    merged_at = pr.get("mergedAt")
                    if merged_at:
                        merged_date = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
                        if merged_date.replace(tzinfo=None) >= cutoff_date:
                            pr["status"] = "merged"
                            all_prs.append(pr)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

    # Store in context for later use
    context.collected_prs = all_prs

    if not all_prs:
        return "No pull requests found in the specified time range."

    # Format output for the agent
    lines = [f"Found {len(all_prs)} pull request(s):\n"]
    for pr in all_prs:
        status_emoji = "🟢" if pr["status"] == "open" else "🟣"
        draft = " (DRAFT)" if pr.get("isDraft") else ""
        changes = f"+{pr.get('additions', 0)}/-{pr.get('deletions', 0)}"
        lines.append(
            f"{status_emoji} #{pr['number']}: {pr['title']}{draft}\n"
            f"   Status: {pr['status']} | Changes: {changes}\n"
            f"   URL: {pr['url']}\n"
        )

    return "\n".join(lines)
