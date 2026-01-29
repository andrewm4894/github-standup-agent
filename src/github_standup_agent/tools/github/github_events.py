"""Tool for fetching a chronological activity feed from GitHub."""

import json
import subprocess
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext


def _parse_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Parse a GitHub event into a structured activity item."""
    event_type = event.get("type", "")
    payload = event.get("payload", {})
    repo = event.get("repo", {}).get("name", "unknown")
    created_at = event.get("created_at", "")

    if event_type == "PushEvent":
        # Events API may not include full commit details
        commits = payload.get("commits", [])
        branch = payload.get("ref", "").replace("refs/heads/", "")
        # If no commits array, we can still show that a push happened
        head = payload.get("head", "")[:7] if payload.get("head") else ""
        return {
            "type": "push",
            "repo": repo,
            "branch": branch,
            "commits": [
                {"sha": c.get("sha", "")[:7], "message": c.get("message", "").split("\n")[0]}
                for c in commits
            ]
            if commits
            else [],
            "commit_count": len(commits) if commits else None,  # None = unknown
            "head": head,
            "timestamp": created_at,
        }

    elif event_type == "PullRequestEvent":
        pr = payload.get("pull_request", {})
        action = payload.get("action", "")
        merged = pr.get("merged", False)
        if action == "closed" and merged:
            action = "merged"
        # Get number from payload directly if not in pr object
        number = pr.get("number") or payload.get("number")
        # Try to get title from head ref as fallback
        head_ref = pr.get("head", {}).get("ref", "")
        return {
            "type": "pull_request",
            "repo": repo,
            "action": action,
            "number": number,
            "title": pr.get("title", ""),
            "branch": head_ref,
            "url": pr.get("html_url", ""),
            "draft": pr.get("draft", False),
            "timestamp": created_at,
        }

    elif event_type == "PullRequestReviewEvent":
        pr = payload.get("pull_request", {})
        review = payload.get("review", {})
        head_ref = pr.get("head", {}).get("ref", "")
        return {
            "type": "review",
            "repo": repo,
            "pr_number": pr.get("number"),
            "pr_title": pr.get("title", ""),
            "pr_branch": head_ref,
            "state": review.get("state", "").lower(),  # approved, changes_requested, commented
            "url": review.get("html_url", ""),
            "timestamp": created_at,
        }

    elif event_type == "IssuesEvent":
        issue = payload.get("issue", {})
        return {
            "type": "issue",
            "repo": repo,
            "action": payload.get("action", ""),
            "number": issue.get("number"),
            "title": issue.get("title", ""),
            "url": issue.get("html_url", ""),
            "timestamp": created_at,
        }

    elif event_type == "IssueCommentEvent":
        issue = payload.get("issue", {})
        comment = payload.get("comment", {})
        is_pr = "pull_request" in issue
        return {
            "type": "comment",
            "repo": repo,
            "on": "pr" if is_pr else "issue",
            "number": issue.get("number"),
            "title": issue.get("title", ""),
            "body_preview": comment.get("body", "")[:100],
            "url": comment.get("html_url", ""),
            "timestamp": created_at,
        }

    elif event_type == "CreateEvent":
        ref_type = payload.get("ref_type", "")
        if ref_type in ("branch", "tag"):
            return {
                "type": "create",
                "repo": repo,
                "ref_type": ref_type,
                "ref": payload.get("ref", ""),
                "timestamp": created_at,
            }

    elif event_type == "PullRequestReviewCommentEvent":
        pr = payload.get("pull_request", {})
        comment = payload.get("comment", {})
        head_ref = pr.get("head", {}).get("ref", "")
        return {
            "type": "review_comment",
            "repo": repo,
            "pr_number": pr.get("number"),
            "pr_title": pr.get("title", ""),
            "pr_branch": head_ref,
            "body_preview": comment.get("body", "")[:100],
            "url": comment.get("html_url", ""),
            "timestamp": created_at,
        }

    return None


def _format_activity(activity: dict[str, Any]) -> str:
    """Format a single activity item for display."""
    activity_type = activity.get("type", "")
    repo = activity.get("repo", "")
    timestamp = activity.get("timestamp", "")

    # Parse timestamp for display
    time_str = ""
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            time_str = timestamp[:16]

    if activity_type == "push":
        branch = activity.get("branch", "")
        count = activity.get("commit_count")
        commits = activity.get("commits", [])
        head = activity.get("head", "")

        if commits:
            lines = [f"[{time_str}] PUSH {repo} ({branch}) - {count} commit(s)"]
            for c in commits[:3]:
                lines.append(f"    - {c['sha']}: {c['message'][:60]}")
            if len(commits) > 3:
                lines.append(f"    ... and {len(commits) - 3} more")
            return "\n".join(lines)
        else:
            return f"[{time_str}] PUSH {repo} ({branch}) [{head}]"

    elif activity_type == "pull_request":
        action = activity.get("action", "")
        number = activity.get("number", "")
        title = activity.get("title", "")
        branch = activity.get("branch", "")
        draft = " (draft)" if activity.get("draft") else ""
        display = title if title else branch
        return f"[{time_str}] PR {action.upper()} {repo}#{number} - {display}{draft}"

    elif activity_type == "review":
        pr_num = activity.get("pr_number", "")
        pr_title = activity.get("pr_title", "")
        pr_branch = activity.get("pr_branch", "")
        state = activity.get("state", "")
        display = pr_title if pr_title else pr_branch
        return f"[{time_str}] REVIEW {state.upper()} {repo}#{pr_num} - {display}"

    elif activity_type == "issue":
        action = activity.get("action", "")
        number = activity.get("number", "")
        title = activity.get("title", "")
        return f"[{time_str}] ISSUE {action.upper()} {repo}#{number} - {title}"

    elif activity_type == "comment":
        on = activity.get("on", "")
        number = activity.get("number", "")
        title = activity.get("title", "")
        return f"[{time_str}] COMMENT on {on} {repo}#{number} - {title}"

    elif activity_type == "create":
        ref_type = activity.get("ref_type", "")
        ref = activity.get("ref", "")
        return f"[{time_str}] CREATED {ref_type} {repo} ({ref})"

    elif activity_type == "review_comment":
        pr_num = activity.get("pr_number", "")
        pr_title = activity.get("pr_title", "")
        pr_branch = activity.get("pr_branch", "")
        display = pr_title if pr_title else pr_branch
        return f"[{time_str}] REVIEW_COMMENT {repo}#{pr_num} - {display}"

    return f"[{time_str}] {activity_type.upper()} {repo}"


@function_tool
def get_activity_feed(
    ctx: RunContextWrapper[StandupContext],
    days_back: Annotated[int, "Number of days to look back"] = 1,
) -> str:
    """
    Fetch a chronological feed of all GitHub activity for the user.

    Returns a unified list of events including:
    - Commits pushed
    - Pull requests opened/merged/closed
    - Code reviews submitted
    - Issues opened/closed
    - Comments on issues and PRs
    - Branches/tags created

    This provides a complete picture of recent work for standup generation.
    """
    username = ctx.context.github_username

    if not username:
        return "GitHub username not available. Cannot fetch activity feed."

    try:
        # Fetch user events (includes both public and private for authenticated user)
        # Note: Don't use --paginate as it concatenates multiple JSON arrays.
        # Use per_page=100 to get enough events for most use cases.
        result = subprocess.run(
            [
                "gh",
                "api",
                f"/users/{username}/events?per_page=100",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            if "API rate limit" in result.stderr:
                return "GitHub API rate limit reached. Try again later."
            return f"Error fetching activity: {result.stderr}"

        if not result.stdout.strip():
            return "No activity found."

        events = json.loads(result.stdout)

        # Filter by date
        cutoff = datetime.now(UTC) - timedelta(days=days_back)
        activities: list[dict[str, Any]] = []

        for event in events:
            created_at = event.get("created_at", "")
            if created_at:
                try:
                    event_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    if event_time < cutoff:
                        continue
                except ValueError:
                    continue

            parsed = _parse_event(event)
            if parsed:
                activities.append(parsed)

        # Store in context for agent access
        ctx.context.collected_activity_feed = activities

        if not activities:
            return f"No activity found in the last {days_back} day(s)."

        # Group by type for summary
        by_type: dict[str, int] = {}
        for a in activities:
            t = a.get("type", "other")
            by_type[t] = by_type.get(t, 0) + 1

        # Format output
        lines = [
            f"Activity Feed: {len(activities)} events in last {days_back} day(s)",
            "Summary: " + ", ".join(f"{count} {t}" for t, count in sorted(by_type.items())),
            "",
            "Events (newest first):",
        ]

        for activity in activities:
            lines.append(_format_activity(activity))

        return "\n".join(lines)

    except subprocess.TimeoutExpired:
        return "Timeout while fetching activity feed."
    except json.JSONDecodeError:
        return "Error parsing activity data from GitHub."
    except FileNotFoundError:
        return "GitHub CLI (gh) not found. Please install it first."
