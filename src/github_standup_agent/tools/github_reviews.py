"""Tool for fetching code reviews from GitHub."""

import json
import subprocess
from datetime import datetime, timedelta
from typing import Annotated, Any

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext


@function_tool
def get_my_reviews(
    ctx: RunContextWrapper[StandupContext],
    days_back: Annotated[int, "Number of days to look back for reviews"] = 7,
    include_given: Annotated[bool, "Include reviews you gave on others' PRs"] = True,
    include_received: Annotated[bool, "Include reviews on your PRs"] = True,
) -> str:
    """
    Fetch code review activity across ALL repositories.

    Shows PRs you've reviewed and reviews received on your PRs.
    Searches across all GitHub repositories the user has access to.
    """
    username = ctx.context.github_username
    if not username:
        return "GitHub username not available. Cannot search reviews."

    cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    all_reviews: list[dict[str, Any]] = []

    # Reviews given (PRs you reviewed) across all repos
    if include_given:
        try:
            result = subprocess.run(
                [
                    "gh",
                    "search",
                    "prs",
                    "--reviewed-by",
                    username,
                    f"--updated=>={cutoff_date}",
                    "--json",
                    "number,title,url,state,repository,author",
                    "--limit",
                    "30",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and result.stdout.strip():
                prs = json.loads(result.stdout)
                for pr in prs:
                    # Exclude self-reviews
                    author = pr.get("author", {}).get("login", "")
                    if author != username:
                        pr["review_type"] = "given"
                        all_reviews.append(pr)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

    # Reviews received (on your PRs) across all repos
    if include_received:
        try:
            result = subprocess.run(
                [
                    "gh",
                    "search",
                    "prs",
                    "--author",
                    username,
                    f"--updated=>={cutoff_date}",
                    "--json",
                    "number,title,url,state,repository,commentsCount",
                    "--limit",
                    "30",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and result.stdout.strip():
                prs = json.loads(result.stdout)
                for pr in prs:
                    # Only include PRs with some activity (comments as proxy for reviews)
                    if pr.get("commentsCount", 0) > 0:
                        pr["review_type"] = "received"
                        all_reviews.append(pr)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

    # Store in context
    ctx.context.collected_reviews = all_reviews

    if not all_reviews:
        return "No code review activity found."

    # Group by type
    given = [r for r in all_reviews if r["review_type"] == "given"]
    received = [r for r in all_reviews if r["review_type"] == "received"]

    # Format output
    lines = ["Code review activity:\n"]

    if given:
        # Group by repo
        by_repo: dict[str, list[dict[str, Any]]] = {}
        for pr in given:
            repo = pr.get("repository", {}).get("nameWithOwner", "unknown")
            if repo not in by_repo:
                by_repo[repo] = []
            by_repo[repo].append(pr)

        lines.append(f"📝 Reviews given ({len(given)} PRs across {len(by_repo)} repos):")
        for repo, repo_prs in by_repo.items():
            lines.append(f"\n   📁 {repo}:")
            for pr in repo_prs[:5]:
                author = pr.get("author", {}).get("login", "unknown")
                state = pr.get("state", "unknown")
                lines.append(f"      • #{pr['number']}: {pr['title']}")
                lines.append(f"        by @{author} | {state}")
            if len(repo_prs) > 5:
                lines.append(f"      ... and {len(repo_prs) - 5} more")

    if received:
        # Group by repo
        by_repo = {}
        for pr in received:
            repo = pr.get("repository", {}).get("nameWithOwner", "unknown")
            if repo not in by_repo:
                by_repo[repo] = []
            by_repo[repo].append(pr)

        lines.append(f"\n📥 Reviews received ({len(received)} PRs across {len(by_repo)} repos):")
        for repo, repo_prs in by_repo.items():
            lines.append(f"\n   📁 {repo}:")
            for pr in repo_prs[:5]:
                comments = pr.get("commentsCount", 0)
                state = pr.get("state", "unknown")
                lines.append(f"      • #{pr['number']}: {pr['title']}")
                lines.append(f"        {comments} comment(s) | {state}")
            if len(repo_prs) > 5:
                lines.append(f"      ... and {len(repo_prs) - 5} more")

    return "\n".join(lines)
