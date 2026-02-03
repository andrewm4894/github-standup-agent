"""Function tools for task tracking / work log."""

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext
from github_standup_agent.instrumentation import capture_event
from github_standup_agent.tools.tasks.task_store import (
    add_task_update,
    create_task,
    get_task,
    get_tasks_for_standup,
    link_task_to_issue,
    link_task_to_pr,
    update_task_status,
)
from github_standup_agent.tools.tasks.task_store import (
    list_tasks as store_list_tasks,
)


@function_tool
def log_task(
    ctx: RunContextWrapper[StandupContext],
    title: Annotated[str, "Short description of what you're working on"],
    tags: Annotated[list[str] | None, "Optional tags like 'frontend', 'bugfix'"] = None,
) -> str:
    """
    Log a new task the user is working on. Use when the user mentions starting work on something.

    Examples of user messages that should trigger this:
    - "I'm working on the auth refactor"
    - "picking up the billing bug"
    - "started reviewing the migration PR"
    """
    username = ctx.context.github_username
    task = create_task(username=username, title=title, tags=tags)

    capture_event(
        event_name="task_created",
        properties={
            "task_id": task["id"],
            "title": title,
            "tags": tags or [],
            "github_username": username,
            "date": date.today().isoformat(),
        },
    )

    tags_str = f" [{', '.join(tags)}]" if tags else ""
    return f'Logged task: "{title}"{tags_str} (id: {task["id"]})'


@function_tool
def update_task(
    ctx: RunContextWrapper[StandupContext],
    task_id: Annotated[str, "The task ID to update"],
    note: Annotated[str, "Progress note or status update"],
    status: Annotated[
        Literal["in_progress", "completed", "abandoned"] | None,
        "Optionally change the task status",
    ] = None,
) -> str:
    """
    Add a progress note to a task and optionally change its status.

    Use when the user provides an update on something they're working on.
    """
    existing = get_task(task_id)
    if not existing:
        return f"Task {task_id} not found."

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
            "github_username": ctx.context.github_username,
            "date": date.today().isoformat(),
        },
    )

    status_msg = f" → {new_status}" if status else ""
    return f'Updated task "{existing["title"]}"{status_msg}: {note}'


@function_tool
def complete_task(
    ctx: RunContextWrapper[StandupContext],
    task_id: Annotated[str, "The task ID to complete"],
    note: Annotated[str | None, "Optional completion note"] = None,
) -> str:
    """
    Mark a task as completed.

    Use when the user says they finished something:
    - "finished the auth refactor"
    - "merged the billing PR"
    - "done with code review"
    """
    existing = get_task(task_id)
    if not existing:
        return f"Task {task_id} not found."

    if note:
        add_task_update(task_id, note)

    update_task_status(task_id, "completed")

    # Calculate duration
    created = datetime.fromisoformat(existing["created_at"])
    now = datetime.now(UTC)
    duration_hours = round((now - created).total_seconds() / 3600, 1)
    update_count = len(existing.get("updates", [])) + (1 if note else 0)

    capture_event(
        event_name="task_completed",
        properties={
            "task_id": task_id,
            "title": existing["title"],
            "duration_hours": duration_hours,
            "update_count": update_count,
            "github_username": ctx.context.github_username,
            "date": date.today().isoformat(),
        },
    )

    return f'Completed task "{existing["title"]}" ({duration_hours}h)'


@function_tool
def list_my_tasks(
    ctx: RunContextWrapper[StandupContext],
    status: Annotated[
        Literal["in_progress", "completed", "abandoned"] | None,
        "Filter by status (default: show all)",
    ] = None,
    days_back: Annotated[int | None, "How many days to look back (default: 7)"] = None,
) -> str:
    """
    Show the user's tasks. Use when they ask "what am I working on?" or similar.
    """
    username = ctx.context.github_username
    lookback = days_back or 7

    if status:
        tasks = store_list_tasks(username=username, status=status)
    else:
        tasks = get_tasks_for_standup(username=username, days_back=lookback)

    # Store in context for cross-referencing
    ctx.context.collected_tasks = tasks

    capture_event(
        event_name="work_log_queried",
        properties={
            "task_count": len(tasks),
            "days_back": lookback,
            "github_username": username,
            "date": date.today().isoformat(),
        },
    )

    if not tasks:
        return "No tasks found. Log a task by telling me what you're working on."

    lines = [f"Found {len(tasks)} task(s):\n"]
    for t in tasks:
        status_icon = {"in_progress": "[active]", "completed": "[done]", "abandoned": "[dropped]"}
        icon = status_icon.get(t["status"], "")
        tags_str = f" [{', '.join(t.get('tags', []))}]" if t.get("tags") else ""
        lines.append(f"  {icon} {t['title']}{tags_str} (id: {t['id']})")
        for u in t.get("updates", []):
            lines.append(f"      ↳ {u['note']}")
    return "\n".join(lines)


@function_tool
def get_todays_work_log(
    ctx: RunContextWrapper[StandupContext],
    days_back: Annotated[int | None, "Override days to look back"] = None,
) -> str:
    """
    Get a formatted work log for standup generation.

    HIGH-SIGNAL context: These are tasks the user explicitly logged throughout the day.
    Should be called alongside get_activity_feed when generating standups.
    """
    username = ctx.context.github_username
    lookback = days_back or ctx.context.days_back

    tasks = get_tasks_for_standup(username=username, days_back=lookback)

    # Store in context
    ctx.context.collected_tasks = tasks

    capture_event(
        event_name="work_log_queried",
        properties={
            "task_count": len(tasks),
            "days_back": lookback,
            "github_username": username,
            "date": date.today().isoformat(),
        },
    )

    if not tasks:
        return "No tasks logged for this period."

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

    lines.append("Use these tasks as PRIMARY context for the standup summary.")
    return "\n".join(lines)


@function_tool
def link_task(
    ctx: RunContextWrapper[StandupContext],
    task_id: Annotated[str, "The task ID"],
    pr: Annotated[str | None, "PR reference like 'owner/repo#123'"] = None,
    issue: Annotated[str | None, "Issue reference like 'owner/repo#456'"] = None,
) -> str:
    """Link a task to a GitHub PR or issue."""
    if not pr and not issue:
        return "Provide a PR or issue reference to link."

    existing = get_task(task_id)
    if not existing:
        return f"Task {task_id} not found."

    linked: list[str] = []
    if pr:
        link_task_to_pr(task_id, pr)
        linked.append(f"PR {pr}")
    if issue:
        link_task_to_issue(task_id, issue)
        linked.append(f"issue {issue}")

    return f'Linked {", ".join(linked)} to task "{existing["title"]}"'
