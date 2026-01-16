"""Tool for fetching code reviews from GitHub."""

import json
import subprocess
from typing import Annotated, Any

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext


@function_tool
def get_my_reviews(
    ctx: RunContextWrapper[StandupContext],
    include_given: Annotated[bool, "Include reviews you gave on others' PRs"] = True,
    include_received: Annotated[bool, "Include reviews on your PRs"] = True,
) -> str:
    """
    Fetch code review activity.

    Shows PRs you've reviewed and reviews received on your PRs.
    """
    username = ctx.context.github_username or "@me"
    all_reviews: list[dict[str, Any]] = []

    # Reviews given (PRs you reviewed)
    if include_given:
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "list",
                    "--search",
                    f"reviewed-by:{username}",
                    "--state",
                    "all",
                    "--json",
                    "number,title,url,state,author,reviewDecision",
                    "--limit",
                    "20",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                prs = json.loads(result.stdout)
                for pr in prs:
                    pr["review_type"] = "given"
                    all_reviews.append(pr)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

    # Reviews received (on your PRs)
    if include_received:
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "list",
                    "--author",
                    username,
                    "--state",
                    "all",
                    "--json",
                    "number,title,url,state,reviewDecision,reviews",
                    "--limit",
                    "20",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                prs = json.loads(result.stdout)
                for pr in prs:
                    reviews = pr.get("reviews", [])
                    if reviews:
                        pr["review_type"] = "received"
                        pr["review_count"] = len(reviews)
                        all_reviews.append(pr)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

    # Store in context
    ctx.context.collected_reviews = all_reviews

    if not all_reviews:
        return "No code review activity found."

    # Format output
    lines = ["Code review activity:\n"]

    given = [r for r in all_reviews if r["review_type"] == "given"]
    received = [r for r in all_reviews if r["review_type"] == "received"]

    if given:
        lines.append("📝 Reviews given:")
        for pr in given[:5]:
            author = pr.get("author", {}).get("login", "unknown")
            decision = pr.get("reviewDecision", "PENDING")
            emoji_map = {"APPROVED": "✅", "CHANGES_REQUESTED": "🔄", "COMMENTED": "💬"}
            emoji = emoji_map.get(decision, "⏳")
            lines.append(f"   {emoji} #{pr['number']}: {pr['title']} (by @{author})")

    if received:
        lines.append("\n📥 Reviews received on your PRs:")
        for pr in received[:5]:
            count = pr.get("review_count", 0)
            decision = pr.get("reviewDecision", "PENDING")
            emoji = {"APPROVED": "✅", "CHANGES_REQUESTED": "🔄"}.get(decision, "⏳")
            lines.append(f"   {emoji} #{pr['number']}: {pr['title']} ({count} review(s))")

    return "\n".join(lines)
