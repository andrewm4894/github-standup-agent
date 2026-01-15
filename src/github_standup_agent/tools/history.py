"""Tools for managing standup history."""

from typing import Annotated

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext
from github_standup_agent.db import StandupDatabase


@function_tool
def get_recent_standups(
    ctx: RunContextWrapper[StandupContext],
    days: Annotated[int, "Number of recent standups to retrieve"] = 3,
) -> str:
    """
    Retrieve recent standups from history for context.

    This helps maintain continuity between standups, avoiding repetition
    and tracking progress on ongoing work.
    """
    db = StandupDatabase()
    standups = db.get_recent(limit=days)

    if not standups:
        return "No previous standups found in history."

    # Store in context
    ctx.context.recent_standups = standups

    # Format for the agent
    lines = [f"Found {len(standups)} recent standup(s):\n"]

    for s in standups:
        lines.append(f"📅 {s['date']}:")
        # Include summary, truncated if very long
        summary = s["summary"]
        if len(summary) > 500:
            summary = summary[:500] + "..."
        lines.append(summary)
        lines.append("")

    return "\n".join(lines)


@function_tool
def save_standup(
    ctx: RunContextWrapper[StandupContext],
    summary: Annotated[str | None, "Summary to save. Defaults to current standup."] = None,
) -> str:
    """
    Save the current standup to history.

    This persists the standup for future reference and continuity.
    """
    content = summary or ctx.context.current_standup

    if not content:
        return "No standup to save. Generate one first."

    db = StandupDatabase()

    # Collect raw data from context
    raw_data = {
        "prs": ctx.context.collected_prs,
        "issues": ctx.context.collected_issues,
        "commits": ctx.context.collected_commits,
        "reviews": ctx.context.collected_reviews,
    }

    db.save(summary=content, raw_data=raw_data)

    return "✅ Standup saved to history."
