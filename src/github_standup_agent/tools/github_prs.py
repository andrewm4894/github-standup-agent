"""Tool for fetching pull requests from GitHub."""

import json
import subprocess
from datetime import datetime, timedelta
from typing import Annotated, Any

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext


@function_tool
def get_my_prs(
    ctx: RunContextWrapper[StandupContext],
    days_back: Annotated[int, "Number of days to look back for PRs"] = 1,
    include_open: Annotated[bool, "Include currently open PRs"] = True,
    include_merged: Annotated[bool, "Include recently merged PRs"] = True,
) -> str:
    """
    Fetch pull requests authored by the current user across ALL repositories.

    Returns PRs that were created, updated, or merged within the specified time range.
    Searches across all GitHub repositories the user has access to.
    """
    username = ctx.context.github_username
    if not username:
        return "GitHub username not available. Cannot search PRs."

    cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    all_prs: list[dict[str, Any]] = []

    # Fetch open PRs across all repos
    if include_open:
        try:
            result = subprocess.run(
                [
                    "gh",
                    "search",
                    "prs",
                    "--author",
                    username,
                    "--state",
                    "open",
                    f"--created=>={cutoff_date}",
                    "--json",
                    "number,title,url,state,createdAt,updatedAt,repository,isDraft",
                    "--limit",
                    "50",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and result.stdout.strip():
                prs = json.loads(result.stdout)
                for pr in prs:
                    pr["status"] = "open"
                    all_prs.append(pr)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

    # Fetch merged PRs across all repos
    if include_merged:
        try:
            result = subprocess.run(
                [
                    "gh",
                    "search",
                    "prs",
                    "--author",
                    username,
                    "--merged",
                    f"--merged=>={cutoff_date}",
                    "--json",
                    "number,title,url,state,createdAt,updatedAt,closedAt,repository,isDraft",
                    "--limit",
                    "50",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and result.stdout.strip():
                prs = json.loads(result.stdout)
                for pr in prs:
                    pr["status"] = "merged"
                    all_prs.append(pr)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

    # Store in context for later use
    ctx.context.collected_prs = all_prs

    if not all_prs:
        return "No pull requests found in the specified time range."

    # Group by repository
    by_repo: dict[str, list[dict[str, Any]]] = {}
    for pr in all_prs:
        repo = pr.get("repository", {}).get("nameWithOwner", "unknown")
        if repo not in by_repo:
            by_repo[repo] = []
        by_repo[repo].append(pr)

    # Format output for the agent
    lines = [f"Found {len(all_prs)} pull request(s) across {len(by_repo)} repo(s):\n"]

    for repo, repo_prs in by_repo.items():
        lines.append(f"\n📁 {repo}:")
        for pr in repo_prs:
            status_emoji = "🟢" if pr["status"] == "open" else "🟣"
            draft = " (DRAFT)" if pr.get("isDraft") else ""
            lines.append(
                f"   {status_emoji} #{pr['number']}: {pr['title']}{draft}\n"
                f"      Status: {pr['status']} | URL: {pr['url']}"
            )

    return "\n".join(lines)
