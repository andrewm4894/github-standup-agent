"""Tools for fetching pull requests from GitHub."""

import json
import subprocess
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext

# Fields available for gh search prs (subset of full PR fields)
PR_SEARCH_FIELDS = (
    "number,title,url,state,createdAt,updatedAt,closedAt,repository,isDraft,"
    "author,labels,body,commentsCount"
)

# Full fields for PR details
PR_DETAIL_FIELDS = (
    "number,title,body,url,state,isDraft,author,baseRefName,headRefName,"
    "createdAt,updatedAt,mergedAt,closedAt,additions,deletions,changedFiles,"
    "reviewDecision,reviews,closingIssuesReferences,labels,milestone,"
    "statusCheckRollup,files"
)


@function_tool
def list_prs(
    ctx: RunContextWrapper[StandupContext],
    filter_by: Annotated[
        Literal["authored", "reviewed", "assigned", "involves", "review-requested"],
        "Filter mode: 'authored' (PRs you wrote), 'reviewed' (PRs you reviewed), "
        "'assigned' (PRs assigned to you), 'involves' (any involvement), "
        "'review-requested' (PRs awaiting your review)",
    ] = "authored",
    username: Annotated[
        str | None,
        "GitHub username to search for. Defaults to current user.",
    ] = None,
    state: Annotated[
        Literal["open", "closed", "merged", "all"],
        "PR state filter",
    ] = "all",
    days_back: Annotated[int, "Number of days to look back"] = 7,
    repo: Annotated[
        str | None,
        "Filter to specific repo (e.g., 'owner/repo'). None for all repos.",
    ] = None,
    limit: Annotated[int, "Maximum number of PRs to return"] = 50,
) -> str:
    """
    Search for pull requests with flexible filters.

    Use filter_by to control what PRs are returned:
    - 'authored': PRs created by the user (default)
    - 'reviewed': PRs the user has reviewed
    - 'assigned': PRs assigned to the user
    - 'involves': PRs where user is involved (author, assignee, reviewer, mentioned)
    - 'review-requested': PRs where user's review is requested
    """
    target_user = username or ctx.context.github_username
    if not target_user:
        return "GitHub username not available. Cannot search PRs."

    cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    all_prs: list[dict[str, Any]] = []

    # Build base command
    cmd = ["gh", "search", "prs"]

    # Add filter based on filter_by
    filter_map = {
        "authored": ["--author", target_user],
        "reviewed": ["--reviewed-by", target_user],
        "assigned": ["--assignee", target_user],
        "involves": ["--involves", target_user],
        "review-requested": ["--review-requested", target_user],
    }
    cmd.extend(filter_map[filter_by])

    # Add repo filter if specified
    if repo:
        cmd.extend(["--repo", repo])

    # Add date filter
    cmd.append(f"--updated=>={cutoff_date}")

    # Add state filter
    if state == "merged":
        cmd.append("--merged")
    elif state in ("open", "closed"):
        cmd.extend(["--state", state])
    # 'all' = no state filter

    # Add output format
    cmd.extend(["--json", PR_SEARCH_FIELDS, "--limit", str(limit)])

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
            return f"Error searching PRs: {result.stderr}"

        if result.stdout.strip():
            prs = json.loads(result.stdout)
            all_prs.extend(prs)

    except subprocess.TimeoutExpired:
        return "Timeout while searching PRs."
    except json.JSONDecodeError:
        return "Error parsing PR data from GitHub."
    except FileNotFoundError:
        return "GitHub CLI (gh) not found. Please install it first."

    # Store in context
    ctx.context.collected_prs = all_prs

    if not all_prs:
        return f"No pull requests found matching filter '{filter_by}' in the last {days_back} days."

    # Group by repository
    by_repo: dict[str, list[dict[str, Any]]] = {}
    for pr in all_prs:
        repo_name = pr.get("repository", {}).get("nameWithOwner", "unknown")
        if repo_name not in by_repo:
            by_repo[repo_name] = []
        by_repo[repo_name].append(pr)

    # Format output
    filter_desc = {
        "authored": "authored by",
        "reviewed": "reviewed by",
        "assigned": "assigned to",
        "involves": "involving",
        "review-requested": "awaiting review from",
    }
    lines = [
        f"Found {len(all_prs)} PR(s) {filter_desc[filter_by]} {target_user} "
        f"across {len(by_repo)} repo(s):"
    ]

    for repo_name, repo_prs in by_repo.items():
        lines.append(f"\n{repo_name}:")
        for pr in repo_prs:
            pr_state = pr.get("state", "unknown").upper()
            draft = " DRAFT" if pr.get("isDraft") else ""
            author = pr.get("author", {}).get("login", "")
            author_info = f" by @{author}" if author and filter_by != "authored" else ""

            # Labels
            labels = pr.get("labels", [])
            label_str = ""
            if labels:
                label_names = [lbl.get("name", "") for lbl in labels[:3]]
                label_str = f" [{', '.join(label_names)}]"

            lines.append(
                f"  #{pr['number']} [{pr_state}{draft}] {pr['title']}{author_info}{label_str}"
            )

    return "\n".join(lines)


@function_tool
def get_pr_details(
    ctx: RunContextWrapper[StandupContext],
    repo: Annotated[str, "Repository in 'owner/repo' format"],
    number: Annotated[int, "PR number"],
    include_files: Annotated[bool, "Include list of changed files"] = False,
) -> str:
    """
    Get detailed information about a specific pull request.

    Use this when you need full context about a PR including:
    - Full description/body
    - Review status and reviewers
    - CI/check status
    - Linked issues
    - File changes
    """
    # Build fields list
    fields = PR_DETAIL_FIELDS
    if not include_files:
        fields = fields.replace(",files", "")

    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
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
            return f"Error fetching PR #{number} from {repo}: {result.stderr}"

        pr = json.loads(result.stdout)

        # Cache in context
        cache_key = f"{repo}#{number}"
        if not hasattr(ctx.context, "pr_details_cache"):
            ctx.context.pr_details_cache = {}
        ctx.context.pr_details_cache[cache_key] = pr

        # Format output
        lines = [f"# PR #{pr['number']}: {pr['title']}\n"]
        lines.append(f"**Repo:** {repo}")
        lines.append(f"**Author:** @{pr.get('author', {}).get('login', 'unknown')}")
        lines.append(f"**State:** {pr.get('state', 'unknown')}")
        lines.append(f"**Branch:** {pr.get('headRefName', '')} → {pr.get('baseRefName', '')}")

        # Dates
        if pr.get("createdAt"):
            lines.append(f"**Created:** {pr['createdAt'][:10]}")
        if pr.get("mergedAt"):
            lines.append(f"**Merged:** {pr['mergedAt'][:10]}")
        elif pr.get("closedAt"):
            lines.append(f"**Closed:** {pr['closedAt'][:10]}")

        # Size
        lines.append(
            f"**Changes:** +{pr.get('additions', 0)}/-{pr.get('deletions', 0)} "
            f"across {pr.get('changedFiles', 0)} files"
        )

        # Review status
        review_decision = pr.get("reviewDecision")
        if review_decision:
            lines.append(f"**Review Status:** {review_decision}")

        # Reviews
        reviews = pr.get("reviews", [])
        if reviews:
            lines.append(f"\n**Reviews ({len(reviews)}):**")
            for review in reviews[:5]:
                reviewer = review.get("author", {}).get("login", "unknown")
                state = review.get("state", "unknown")
                emoji = {"APPROVED": "✅", "CHANGES_REQUESTED": "🔄", "COMMENTED": "💬"}.get(
                    state, "👀"
                )
                lines.append(f"  {emoji} @{reviewer}: {state}")
            if len(reviews) > 5:
                lines.append(f"  ... and {len(reviews) - 5} more")

        # Linked issues
        closing_issues = pr.get("closingIssuesReferences", [])
        if closing_issues:
            lines.append(f"\n**Closes Issues ({len(closing_issues)}):**")
            for issue in closing_issues:
                lines.append(f"  - #{issue.get('number')}: {issue.get('title', '')}")

        # CI Status
        status_rollup = pr.get("statusCheckRollup", [])
        if status_rollup:
            # statusCheckRollup is a list of check suites
            lines.append("\n**CI Status:**")
            for check in status_rollup[:5]:
                name = check.get("name", check.get("context", "unknown"))
                state = check.get("conclusion") or check.get("state", "pending")
                emoji = {"SUCCESS": "✅", "FAILURE": "❌", "PENDING": "⏳"}.get(state.upper(), "❓")
                lines.append(f"  {emoji} {name}: {state}")

        # Labels
        labels = pr.get("labels", [])
        if labels:
            label_names = [lbl.get("name", "") for lbl in labels]
            lines.append(f"\n**Labels:** {', '.join(label_names)}")

        # Milestone
        milestone = pr.get("milestone")
        if milestone:
            lines.append(f"**Milestone:** {milestone.get('title', '')}")

        # Body (description)
        body = pr.get("body", "")
        if body:
            # Truncate if too long
            if len(body) > 500:
                body = body[:500] + "..."
            lines.append(f"\n**Description:**\n{body}")

        # Files changed
        files = pr.get("files", [])
        if files and include_files:
            lines.append(f"\n**Files Changed ({len(files)}):**")
            for f in files[:15]:
                path = f.get("path", "")
                adds = f.get("additions", 0)
                dels = f.get("deletions", 0)
                lines.append(f"  {path} (+{adds}/-{dels})")
            if len(files) > 15:
                lines.append(f"  ... and {len(files) - 15} more files")

        lines.append(f"\n**URL:** {pr.get('url', '')}")

        return "\n".join(lines)

    except subprocess.TimeoutExpired:
        return f"Timeout fetching PR #{number} from {repo}."
    except json.JSONDecodeError:
        return f"Error parsing PR data for #{number} from {repo}."
    except FileNotFoundError:
        return "GitHub CLI (gh) not found. Please install it first."
