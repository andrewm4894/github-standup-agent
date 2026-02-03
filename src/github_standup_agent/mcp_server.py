"""FastMCP server exposing task tracking tools for Claude Code.

Run as: python -m github_standup_agent.mcp_server
"""

import os
import subprocess
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Any

from fastmcp import FastMCP

from github_standup_agent.instrumentation import capture_event
from github_standup_agent.tools.tasks.task_store import (
    add_task_update,
    create_task,
    get_task,
    get_tasks_for_standup,
    update_task_status,
)
from github_standup_agent.tools.tasks.task_store import (
    list_tasks as store_list_tasks,
)

mcp = FastMCP(
    "standup-tasks",
    instructions=(
        "Track what you're working on. Detect task intent from natural language: "
        "'working on X' -> log_task, 'finished X' -> complete_task, "
        "'what am I working on?' -> list_tasks."
    ),
)


@lru_cache(maxsize=1)
def _get_github_username() -> str | None:
    """Auto-detect GitHub username, cached for the server lifetime."""
    env_user = os.environ.get("STANDUP_GITHUB_USER")
    if env_user:
        return env_user
    try:
        result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


@mcp.tool
def log_task(title: str, tags: list[str] | None = None) -> dict[str, Any]:
    """Log a new task you're working on.

    Use when the user mentions starting work on something, e.g.:
    - "working on the auth refactor"
    - "picking up the billing bug"
    - "started reviewing the migration PR"
    """
    username = _get_github_username()
    task = create_task(username=username, title=title, tags=tags)

    capture_event(
        event_name="task_created",
        properties={
            "task_id": task["id"],
            "title": title,
            "tags": tags or [],
            "github_username": username,
            "date": date.today().isoformat(),
            "source": "mcp",
        },
    )

    return {
        "status": "ok",
        "message": f'Logged task: "{title}" (id: {task["id"]})',
        "task": task,
    }


@mcp.tool
def update_task(task_id: str, note: str, status: str | None = None) -> dict[str, Any]:
    """Add a progress note to a task, optionally changing its status.

    status can be: "in_progress", "completed", or "abandoned".
    Use when the user provides an update on something they're working on.
    """
    existing = get_task(task_id)
    if not existing:
        return {"status": "error", "message": f"Task {task_id} not found."}

    add_task_update(task_id, note)

    new_status = existing["status"]
    if status and status != existing["status"]:
        result = update_task_status(task_id, status)
        if result:
            new_status = status

    capture_event(
        event_name="task_updated",
        properties={
            "task_id": task_id,
            "title": existing["title"],
            "note": note,
            "new_status": new_status,
            "github_username": _get_github_username(),
            "date": date.today().isoformat(),
            "source": "mcp",
        },
    )

    return {
        "status": "ok",
        "message": f'Updated task "{existing["title"]}": {note}',
        "task_id": task_id,
        "new_status": new_status,
    }


@mcp.tool
def complete_task(task_id: str, note: str | None = None) -> dict[str, Any]:
    """Mark a task as completed.

    Use when the user says they finished something:
    - "finished the auth refactor"
    - "merged the billing PR"
    - "done with code review"
    """
    existing = get_task(task_id)
    if not existing:
        return {"status": "error", "message": f"Task {task_id} not found."}

    if note:
        add_task_update(task_id, note)

    update_task_status(task_id, "completed")

    created = datetime.fromisoformat(existing["created_at"])
    now = datetime.now(UTC)
    duration_hours = round((now - created).total_seconds() / 3600, 1)

    capture_event(
        event_name="task_completed",
        properties={
            "task_id": task_id,
            "title": existing["title"],
            "duration_hours": duration_hours,
            "github_username": _get_github_username(),
            "date": date.today().isoformat(),
            "source": "mcp",
        },
    )

    return {
        "status": "ok",
        "message": f'Completed task "{existing["title"]}" ({duration_hours}h)',
        "task_id": task_id,
        "duration_hours": duration_hours,
    }


@mcp.tool
def list_tasks(status: str | None = None, days_back: int = 7) -> dict[str, Any]:
    """Show your tasks.

    Use when the user asks "what am I working on?" or similar.
    status can filter to: "in_progress", "completed", or "abandoned".
    """
    username = _get_github_username()

    if status:
        tasks = store_list_tasks(username=username, status=status)
    else:
        tasks = get_tasks_for_standup(username=username, days_back=days_back)

    capture_event(
        event_name="work_log_queried",
        properties={
            "task_count": len(tasks),
            "days_back": days_back,
            "github_username": username,
            "date": date.today().isoformat(),
            "source": "mcp",
        },
    )

    return {
        "status": "ok",
        "task_count": len(tasks),
        "tasks": tasks,
    }


@mcp.tool
def get_work_log(days_back: int = 1) -> dict[str, Any]:
    """Get a formatted work log for standup generation.

    Returns tasks logged during the lookback period, formatted as
    high-signal context for standup summaries.
    """
    username = _get_github_username()
    tasks = get_tasks_for_standup(username=username, days_back=days_back)

    capture_event(
        event_name="work_log_queried",
        properties={
            "task_count": len(tasks),
            "days_back": days_back,
            "github_username": username,
            "date": date.today().isoformat(),
            "source": "mcp",
        },
    )

    if not tasks:
        return {
            "status": "ok",
            "task_count": 0,
            "log": "No tasks logged for this period.",
        }

    lines = ["=== USER WORK LOG (HIGH-SIGNAL) ===", ""]
    for t in tasks:
        status_label = t["status"].replace("_", " ").title()
        lines.append(f"• {t['title']} [{status_label}]")
        if t.get("tags"):
            lines.append(f"  Tags: {', '.join(t['tags'])}")
        if t.get("related_prs"):
            lines.append(f"  PRs: {', '.join(t['related_prs'])}")
        if t.get("related_issues"):
            lines.append(f"  Issues: {', '.join(t['related_issues'])}")
        for u in t.get("updates", []):
            lines.append(f"  ↳ {u['note']}")
        lines.append("")

    return {
        "status": "ok",
        "task_count": len(tasks),
        "log": "\n".join(lines),
        "tasks": tasks,
    }


if __name__ == "__main__":
    mcp.run()
