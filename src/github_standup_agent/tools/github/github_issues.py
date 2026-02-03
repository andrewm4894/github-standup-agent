"""Tools for fetching issues from GitHub."""

import json
import subprocess
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext

# Fields for issue searches
ISSUE_SEARCH_FIELDS = (
    "number,title,url,state,createdAt,updatedAt,closedAt,repository,"
    "author,assignees,labels,commentsCount"
)

# Full fields for issue details
ISSUE_DETAIL_FIELDS = (
    "number,title,body,url,state,stateReason,author,assignees,"
    "createdAt,updatedAt,closedAt,labels,milestone,commentsCount,"
    "comments"
)


@function_tool
def list_issues(
    ctx: RunContextWrapper[StandupContext],
    filter_by: Annotated[
        Literal["authored", "assigned", "mentions", "involves"],
        "Filter mode: 'authored' (issues you created), 'assigned' (assigned to you), "
        "'mentions' (you were mentioned), 'involves' (any involvement)",
    ] = "assigned",
    username: Annotated[
        str | None,
        "GitHub username to search for. Defaults to current user.",
    ] = None,
    state: Annotated[
        Literal["open", "closed", "all"],
        "Issue state filter",
    ] = "all",
    days_back: Annotated[int, "Number of days to look back"] = 7,
    repo: Annotated[
        str | None,
        "Filter to specific repo (e.g., 'owner/repo'). None for all repos.",
    ] = None,
    limit: Annotated[int, "Maximum number of issues to return"] = 50,
) -> str:
    """
    Search for issues with flexible filters.

    Use filter_by to control what issues are returned:
    - 'assigned': Issues assigned to the user (default)
    - 'authored': Issues created by the user
    - 'mentions': Issues where user was mentioned
    - 'involves': Issues where user is involved (author, assignee, mentioned)
    """
    target_user = username or ctx.context.github_username
    if not target_user:
        return "GitHub username not available. Cannot search issues."

    cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    all_issues: list[dict[str, Any]] = []

    # Build base command
    cmd = ["gh", "search", "issues"]

    # Add filter based on filter_by
    filter_map = {
        "authored": ["--author", target_user],
        "assigned": ["--assignee", target_user],
        "mentions": ["--mentions", target_user],
        "involves": ["--involves", target_user],
    }
    cmd.extend(filter_map[filter_by])

    # Add repo filter if specified
    if repo:
        cmd.extend(["--repo", repo])

    # Add date filter
    cmd.append(f"--updated=>={cutoff_date}")

    # Add state filter
    if state in ("open", "closed"):
        cmd.extend(["--state", state])
    # 'all' = no state filter

    # Add output format
    cmd.extend(["--json", ISSUE_SEARCH_FIELDS, "--limit", str(limit)])

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
            return f"Error searching issues: {result.stderr}"

        if result.stdout.strip():
            issues = json.loads(result.stdout)
            all_issues.extend(issues)

    except subprocess.TimeoutExpired:
        return "Timeout while searching issues."
    except json.JSONDecodeError:
        return "Error parsing issue data from GitHub."
    except FileNotFoundError:
        return "GitHub CLI (gh) not found. Please install it first."

    # Store in context
    ctx.context.collected_issues = all_issues

    if not all_issues:
        return f"No issues found matching filter '{filter_by}' in the last {days_back} days."

    # Group by repository
    by_repo: dict[str, list[dict[str, Any]]] = {}
    for issue in all_issues:
        repo_name = issue.get("repository", {}).get("nameWithOwner", "unknown")
        if repo_name not in by_repo:
            by_repo[repo_name] = []
        by_repo[repo_name].append(issue)

    # Format output
    filter_desc = {
        "authored": "authored by",
        "assigned": "assigned to",
        "mentions": "mentioning",
        "involves": "involving",
    }
    lines = [
        f"Found {len(all_issues)} issue(s) {filter_desc[filter_by]} {target_user} "
        f"across {len(by_repo)} repo(s):"
    ]

    for repo_name, repo_issues in by_repo.items():
        lines.append(f"\n{repo_name}:")
        for issue in repo_issues:
            issue_state = issue.get("state", "unknown").upper()

            # Labels
            labels = issue.get("labels", [])
            label_str = ""
            if labels:
                label_names = [lbl.get("name", "") for lbl in labels[:3]]
                label_str = f" [{', '.join(label_names)}]"

            # Comments
            comments = issue.get("commentsCount", 0)
            comment_str = f" ({comments} comments)" if comments else ""

            # Author info (if not filtering by authored)
            author = issue.get("author", {}).get("login", "")
            author_info = f" by @{author}" if author and filter_by != "authored" else ""

            # Assignees
            assignees = issue.get("assignees", [])
            assignee_str = ""
            if assignees and filter_by != "assigned":
                assignee_names = [a.get("login", "") for a in assignees[:2]]
                assignee_str = f" -> @{', @'.join(assignee_names)}"

            line = (
                f"  #{issue['number']} [{issue_state}] {issue['title']}"
                f"{author_info}{assignee_str}{label_str}{comment_str}"
            )
            lines.append(line)

    return "\n".join(lines)


@function_tool
def get_issue_details(
    ctx: RunContextWrapper[StandupContext],
    repo: Annotated[str, "Repository in 'owner/repo' format"],
    number: Annotated[int, "Issue number"],
    include_comments: Annotated[bool, "Include issue comments"] = False,
) -> str:
    """
    Get detailed information about a specific issue.

    Use this when you need full context about an issue including:
    - Full description/body
    - State reason (why it was closed)
    - Comments and discussion
    - Linked PRs that close it
    """
    # Build fields list
    fields = ISSUE_DETAIL_FIELDS
    if not include_comments:
        fields = fields.replace(",comments", "")

    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "view",
                str(number),
                "--repo",
                repo,
                "--json",
                fields,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            return f"Error fetching issue #{number} from {repo}: {result.stderr}"

        issue = json.loads(result.stdout)

        # Cache in context
        cache_key = f"{repo}#{number}"
        if not hasattr(ctx.context, "issue_details_cache"):
            ctx.context.issue_details_cache = {}
        ctx.context.issue_details_cache[cache_key] = issue

        # Format output
        lines = [f"# Issue #{issue['number']}: {issue['title']}\n"]
        lines.append(f"**Repo:** {repo}")
        lines.append(f"**Author:** @{issue.get('author', {}).get('login', 'unknown')}")
        lines.append(f"**State:** {issue.get('state', 'unknown')}")

        # State reason
        state_reason = issue.get("stateReason")
        if state_reason:
            lines.append(f"**State Reason:** {state_reason}")

        # Dates
        if issue.get("createdAt"):
            lines.append(f"**Created:** {issue['createdAt'][:10]}")
        if issue.get("closedAt"):
            lines.append(f"**Closed:** {issue['closedAt'][:10]}")

        # Assignees
        assignees = issue.get("assignees", [])
        if assignees:
            assignee_names = [a.get("login", "") for a in assignees]
            lines.append(f"**Assignees:** @{', @'.join(assignee_names)}")

        # Labels
        labels = issue.get("labels", [])
        if labels:
            label_names = [lbl.get("name", "") for lbl in labels]
            lines.append(f"**Labels:** {', '.join(label_names)}")

        # Milestone
        milestone = issue.get("milestone")
        if milestone:
            lines.append(f"**Milestone:** {milestone.get('title', '')}")

        # Comments count
        comments_count = issue.get("commentsCount", 0)
        lines.append(f"**Comments:** {comments_count}")

        # Body (description)
        body = issue.get("body", "")
        if body:
            # Truncate if too long
            if len(body) > 500:
                body = body[:500] + "..."
            lines.append(f"\n**Description:**\n{body}")

        # Comments
        comments = issue.get("comments", [])
        if comments and include_comments:
            lines.append(f"\n**Recent Comments ({len(comments)}):**")
            for comment in comments[:5]:
                author = comment.get("author", {}).get("login", "unknown")
                body = comment.get("body", "")[:150]
                if len(comment.get("body", "")) > 150:
                    body += "..."
                created = comment.get("createdAt", "")[:10]
                lines.append(f"\n  @{author} ({created}):\n  {body}")
            if len(comments) > 5:
                lines.append(f"\n  ... and {len(comments) - 5} more comments")

        lines.append(f"\n**URL:** {issue.get('url', '')}")

        return "\n".join(lines)

    except subprocess.TimeoutExpired:
        return f"Timeout fetching issue #{number} from {repo}."
    except json.JSONDecodeError:
        return f"Error parsing issue data for #{number} from {repo}."
    except FileNotFoundError:
        return "GitHub CLI (gh) not found. Please install it first."
