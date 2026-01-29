"""Tools for fetching commits from GitHub."""

import json
import subprocess
from datetime import datetime, timedelta
from typing import Annotated, Any

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext


@function_tool
def list_commits(
    ctx: RunContextWrapper[StandupContext],
    username: Annotated[
        str | None,
        "GitHub username to search for. Defaults to current user.",
    ] = None,
    days_back: Annotated[int, "Number of days to look back"] = 1,
    repo: Annotated[
        str | None,
        "Filter to specific repo (e.g., 'owner/repo'). None for all repos.",
    ] = None,
    limit: Annotated[int, "Maximum number of commits to return"] = 50,
) -> str:
    """
    Search for commits authored by a user.

    Returns commits across repositories with their messages and metadata.
    """
    target_user = username or ctx.context.github_username

    if not target_user:
        return "GitHub username not available. Cannot search commits."

    cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    # Build command
    cmd = [
        "gh",
        "search",
        "commits",
        "--author",
        target_user,
        "--author-date",
        f">={cutoff_date}",
        "--json",
        "sha,commit,repository,url",
        "--limit",
        str(limit),
    ]

    if repo:
        cmd.extend(["--repo", repo])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            if "API rate limit" in result.stderr:
                return "GitHub API rate limit reached. Try again later."
            return f"Error fetching commits: {result.stderr}"

        if not result.stdout.strip():
            return f"No commits found for {target_user} in the last {days_back} day(s)."

        commits = json.loads(result.stdout)

        # Store in context
        ctx.context.collected_commits = commits

        # Group by repository
        by_repo: dict[str, list[dict[str, Any]]] = {}
        for commit in commits:
            repo_data = commit.get("repository", {})
            repo_name = repo_data.get("fullName") or repo_data.get("nameWithOwner", "unknown")
            if repo_name not in by_repo:
                by_repo[repo_name] = []
            by_repo[repo_name].append(commit)

        # Format output
        lines = [
            f"Found {len(commits)} commit(s) by {target_user} across {len(by_repo)} repo(s):"
        ]

        for repo_name, repo_commits in by_repo.items():
            lines.append(f"\n{repo_name}:")
            for c in repo_commits:
                sha_short = c.get("sha", "")[:7]
                commit_data = c.get("commit", {})
                # First line of commit message
                message = commit_data.get("message", "").split("\n")[0]

                # Get date if available
                author_date = commit_data.get("author", {}).get("date", "")
                date_str = author_date[:10] if author_date else ""

                lines.append(f"  [{sha_short}] {date_str} {message}")

        return "\n".join(lines)

    except subprocess.TimeoutExpired:
        return "Timeout while fetching commits. Try reducing the number of days."
    except json.JSONDecodeError:
        return "Error parsing commit data from GitHub."
    except FileNotFoundError:
        return "GitHub CLI (gh) not found. Please install it first."
