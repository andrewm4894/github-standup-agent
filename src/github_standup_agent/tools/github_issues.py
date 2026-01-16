"""Tool for fetching issues from GitHub."""

import json
import subprocess
from datetime import datetime, timedelta
from typing import Annotated, Any

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext


@function_tool
def get_my_issues(
    ctx: RunContextWrapper[StandupContext],
    days_back: Annotated[int, "Number of days to look back for issues"] = 7,
    include_assigned: Annotated[bool, "Include issues assigned to you"] = True,
    include_created: Annotated[bool, "Include issues you created"] = True,
) -> str:
    """
    Fetch issues assigned to or created by the current user across ALL repositories.

    Returns issues that are open or were recently updated.
    Searches across all GitHub repositories the user has access to.
    """
    username = ctx.context.github_username
    if not username:
        return "GitHub username not available. Cannot search issues."

    cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    all_issues: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    # Fetch assigned issues across all repos
    if include_assigned:
        try:
            result = subprocess.run(
                [
                    "gh",
                    "search",
                    "issues",
                    "--assignee",
                    username,
                    f"--updated=>={cutoff_date}",
                    "--json",
                    "number,title,url,state,createdAt,updatedAt,repository,labels",
                    "--limit",
                    "50",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and result.stdout.strip():
                issues = json.loads(result.stdout)
                for issue in issues:
                    if issue["url"] not in seen_urls:
                        issue["source"] = "assigned"
                        all_issues.append(issue)
                        seen_urls.add(issue["url"])
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

    # Fetch created issues across all repos
    if include_created:
        try:
            result = subprocess.run(
                [
                    "gh",
                    "search",
                    "issues",
                    "--author",
                    username,
                    f"--updated=>={cutoff_date}",
                    "--json",
                    "number,title,url,state,createdAt,updatedAt,repository,labels",
                    "--limit",
                    "50",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and result.stdout.strip():
                issues = json.loads(result.stdout)
                for issue in issues:
                    if issue["url"] not in seen_urls:
                        issue["source"] = "created"
                        all_issues.append(issue)
                        seen_urls.add(issue["url"])
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

    # Store in context
    ctx.context.collected_issues = all_issues

    if not all_issues:
        return "No issues found in the specified time range."

    # Group by repository
    by_repo: dict[str, list[dict[str, Any]]] = {}
    for issue in all_issues:
        repo = issue.get("repository", {}).get("nameWithOwner", "unknown")
        if repo not in by_repo:
            by_repo[repo] = []
        by_repo[repo].append(issue)

    # Format output
    lines = [f"Found {len(all_issues)} issue(s) across {len(by_repo)} repo(s):\n"]

    for repo, repo_issues in by_repo.items():
        lines.append(f"\n📁 {repo}:")
        for issue in repo_issues:
            status_emoji = "🔵" if issue["state"] == "open" else "⚫"
            labels = ", ".join(lbl["name"] for lbl in issue.get("labels", [])) or "no labels"
            source = f"({issue['source']})" if issue.get("source") else ""
            lines.append(
                f"   {status_emoji} #{issue['number']}: {issue['title']} {source}\n"
                f"      State: {issue['state']} | Labels: {labels}\n"
                f"      URL: {issue['url']}"
            )

    return "\n".join(lines)
