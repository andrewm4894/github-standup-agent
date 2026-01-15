"""Tool for fetching commits from GitHub."""

import json
import subprocess
from datetime import datetime, timedelta
from typing import Annotated, Any

from agents import function_tool

from github_standup_agent.context import StandupContext


@function_tool
def get_my_commits(
    context: StandupContext,
    days_back: Annotated[int, "Number of days to look back for commits"] = 1,
) -> str:
    """
    Fetch recent commits by the current user.

    Uses GitHub search to find commits across repositories.
    """
    username = context.github_username

    if not username:
        return "GitHub username not available. Cannot search commits."

    cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    try:
        result = subprocess.run(
            [
                "gh", "search", "commits",
                "--author", username,
                "--author-date", f">={cutoff_date}",
                "--json", "sha,commit,repository,url",
                "--limit", "50",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            # Fallback error message
            if "API rate limit" in result.stderr:
                return "GitHub API rate limit reached. Try again later."
            return f"Error fetching commits: {result.stderr}"

        if not result.stdout.strip():
            return "No commits found in the specified time range."

        commits = json.loads(result.stdout)

        # Store in context
        context.collected_commits = commits

        # Format output
        lines = [f"Found {len(commits)} commit(s):\n"]

        # Group by repository
        by_repo: dict[str, list[dict[str, Any]]] = {}
        for commit in commits:
            repo = commit.get("repository", {}).get("nameWithOwner", "unknown")
            if repo not in by_repo:
                by_repo[repo] = []
            by_repo[repo].append(commit)

        for repo, repo_commits in by_repo.items():
            lines.append(f"\n📁 {repo}:")
            for c in repo_commits[:5]:  # Limit per repo
                sha_short = c.get("sha", "")[:7]
                message = c.get("commit", {}).get("message", "").split("\n")[0][:60]
                lines.append(f"   • [{sha_short}] {message}")

            if len(repo_commits) > 5:
                lines.append(f"   ... and {len(repo_commits) - 5} more")

        return "\n".join(lines)

    except subprocess.TimeoutExpired:
        return "Timeout while fetching commits. Try reducing the number of days."
    except json.JSONDecodeError:
        return "Error parsing commit data from GitHub."
    except FileNotFoundError:
        return "GitHub CLI (gh) not found. Please install it first."
