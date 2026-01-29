"""Tools for fetching comments from GitHub."""

import json
import subprocess
from datetime import datetime, timedelta
from typing import Annotated, Any

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext


@function_tool
def list_comments(
    ctx: RunContextWrapper[StandupContext],
    username: Annotated[
        str | None,
        "GitHub username to search for. Defaults to current user.",
    ] = None,
    days_back: Annotated[int, "Number of days to look back"] = 7,
    repo: Annotated[
        str | None,
        "Filter to specific repo (e.g., 'owner/repo'). None for all repos.",
    ] = None,
    limit: Annotated[int, "Maximum number of issues/PRs to fetch comments from"] = 20,
) -> str:
    """
    Fetch comments made by a user on issues and PRs.

    Returns comments across repositories with their content and context.
    This searches for issues/PRs where the user has commented, then fetches
    the actual comment content.
    """
    target_user = username or ctx.context.github_username

    if not target_user:
        return "GitHub username not available. Cannot search comments."

    cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

    # Step 1: Find issues/PRs where user commented
    cmd = [
        "gh",
        "search",
        "issues",
        "--commenter",
        target_user,
        f"--updated=>={cutoff_date}",
        "--json",
        "number,title,url,repository,state",
        "--limit",
        str(limit),
    ]

    if repo:
        cmd.extend(["--repo", repo])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            if "API rate limit" in result.stderr:
                return "GitHub API rate limit reached. Try again later."
            return f"Error searching for commented issues: {result.stderr}"

        if not result.stdout.strip():
            return f"No comments found for {target_user} in the last {days_back} day(s)."

        issues = json.loads(result.stdout)

    except subprocess.TimeoutExpired:
        return "Timeout while searching for comments."
    except json.JSONDecodeError:
        return "Error parsing issue data from GitHub."
    except FileNotFoundError:
        return "GitHub CLI (gh) not found. Please install it first."

    if not issues:
        return f"No comments found for {target_user} in the last {days_back} day(s)."

    # Step 2: Fetch comments from each issue/PR
    all_comments: list[dict[str, Any]] = []
    cutoff_dt = datetime.now() - timedelta(days=days_back)

    for issue in issues:
        repo_name = issue.get("repository", {}).get("nameWithOwner", "")
        issue_number = issue.get("number")

        if not repo_name or not issue_number:
            continue

        try:
            # Fetch comments for this issue/PR
            comments_result = subprocess.run(
                [
                    "gh",
                    "api",
                    f"/repos/{repo_name}/issues/{issue_number}/comments",
                    "--jq",
                    f'[.[] | select(.user.login == "{target_user}") | {{body: .body, created_at: .created_at, url: .html_url}}]',
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if comments_result.returncode == 0 and comments_result.stdout.strip():
                comments = json.loads(comments_result.stdout)

                # Filter by date and add context
                for comment in comments:
                    created_at = comment.get("created_at", "")
                    if created_at:
                        try:
                            comment_dt = datetime.fromisoformat(
                                created_at.replace("Z", "+00:00")
                            )
                            if comment_dt.replace(tzinfo=None) < cutoff_dt:
                                continue
                        except ValueError:
                            pass

                    all_comments.append(
                        {
                            "repo": repo_name,
                            "issue_number": issue_number,
                            "issue_title": issue.get("title", ""),
                            "issue_state": issue.get("state", ""),
                            "issue_url": issue.get("url", ""),
                            "body": comment.get("body", ""),
                            "created_at": created_at,
                            "url": comment.get("url", ""),
                        }
                    )

        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            # Skip this issue if we can't fetch comments
            continue

    if not all_comments:
        return f"No comments found for {target_user} in the last {days_back} day(s)."

    # Group by repository
    by_repo: dict[str, list[dict[str, Any]]] = {}
    for comment in all_comments:
        repo_name = comment.get("repo", "unknown")
        if repo_name not in by_repo:
            by_repo[repo_name] = []
        by_repo[repo_name].append(comment)

    # Format output
    lines = [
        f"Found {len(all_comments)} comment(s) by {target_user} "
        f"across {len(issues)} issue(s)/PR(s) in {len(by_repo)} repo(s):"
    ]

    for repo_name, repo_comments in by_repo.items():
        lines.append(f"\n{repo_name}:")

        # Group by issue within repo
        by_issue: dict[int, list[dict[str, Any]]] = {}
        for comment in repo_comments:
            issue_num = comment.get("issue_number")
            if issue_num not in by_issue:
                by_issue[issue_num] = []
            by_issue[issue_num].append(comment)

        for issue_num, issue_comments in by_issue.items():
            first_comment = issue_comments[0]
            issue_state = first_comment.get("issue_state", "").upper()
            issue_title = first_comment.get("issue_title", "")

            lines.append(f"  #{issue_num} [{issue_state}] {issue_title}")

            for comment in issue_comments:
                created = comment.get("created_at", "")[:10]
                body = comment.get("body", "").strip()
                # Show full comment, just clean up excessive whitespace
                body_cleaned = " ".join(body.split())
                if len(body_cleaned) > 300:
                    body_cleaned = body_cleaned[:300] + "..."

                lines.append(f"    [{created}] {body_cleaned}")

    return "\n".join(lines)
