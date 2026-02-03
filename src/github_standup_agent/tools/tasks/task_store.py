"""SQLite storage layer for task tracking / work log."""

import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from github_standup_agent.config import DATA_DIR, TASKS_DB_FILE

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    github_username TEXT,
    tags TEXT,
    related_prs TEXT,
    related_issues TEXT
);

CREATE TABLE IF NOT EXISTS task_updates (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(TASKS_DB_FILE))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_tasks_db() -> None:
    """Create the tasks database and tables if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = _connect()
    conn.executescript(_CREATE_TABLES_SQL)
    conn.close()


def create_task(
    username: str | None,
    title: str,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Insert a new task and return it as a dict."""
    ensure_tasks_db()
    task_id = uuid.uuid4().hex[:12]
    now = _now_iso()
    conn = _connect()
    conn.execute(
        """INSERT INTO tasks (id, title, status, created_at, updated_at, github_username, tags,
           related_prs, related_issues)
           VALUES (?, ?, 'in_progress', ?, ?, ?, ?, '[]', '[]')""",
        (task_id, title, now, now, username, json.dumps(tags or [])),
    )
    conn.commit()
    task = _row_to_dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())
    conn.close()
    return task


def update_task_status(task_id: str, status: str) -> dict[str, Any] | None:
    """Update a task's status. Returns updated task or None if not found."""
    ensure_tasks_db()
    now = _now_iso()
    conn = _connect()
    completed_at = now if status == "completed" else None

    conn.execute(
        "UPDATE tasks SET status = ?, updated_at = ?,"
        " completed_at = COALESCE(?, completed_at) WHERE id = ?",
        (status, now, completed_at, task_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return _row_to_dict(row)


def add_task_update(task_id: str, note: str) -> dict[str, Any]:
    """Insert a note into task_updates and touch the task's updated_at."""
    ensure_tasks_db()
    update_id = uuid.uuid4().hex[:12]
    now = _now_iso()
    conn = _connect()
    conn.execute(
        "INSERT INTO task_updates (id, task_id, note, created_at) VALUES (?, ?, ?, ?)",
        (update_id, task_id, note, now),
    )
    conn.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (now, task_id))
    conn.commit()
    row = conn.execute("SELECT * FROM task_updates WHERE id = ?", (update_id,)).fetchone()
    conn.close()
    return dict(row)


def get_task(task_id: str) -> dict[str, Any] | None:
    """Get a single task with its updates."""
    ensure_tasks_db()
    conn = _connect()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        conn.close()
        return None
    task = _row_to_dict(row)
    updates = conn.execute(
        "SELECT * FROM task_updates WHERE task_id = ? ORDER BY created_at ASC", (task_id,)
    ).fetchall()
    task["updates"] = [dict(u) for u in updates]
    conn.close()
    return task


def list_tasks(
    username: str | None = None,
    status: str | None = None,
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    """List tasks with optional filters."""
    ensure_tasks_db()
    clauses: list[str] = []
    params: list[Any] = []
    if username:
        clauses.append("github_username = ?")
        params.append(username)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if since:
        clauses.append("updated_at >= ?")
        params.append(since.isoformat())

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    conn = _connect()
    rows = conn.execute(f"SELECT * FROM tasks {where} ORDER BY updated_at DESC", params).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def get_tasks_for_standup(username: str | None, days_back: int = 1) -> list[dict[str, Any]]:
    """Get tasks active or completed within the lookback window, with updates joined."""
    ensure_tasks_db()
    since = datetime.now(UTC) - timedelta(days=days_back)
    since_iso = since.isoformat()

    conn = _connect()
    # Tasks updated within window OR still in_progress
    params: list[Any] = [since_iso]
    username_clause = ""
    if username:
        username_clause = "AND github_username = ?"
        params.append(username)

    rows = conn.execute(
        f"""SELECT * FROM tasks
            WHERE (updated_at >= ? OR status = 'in_progress')
            {username_clause}
            ORDER BY updated_at DESC""",
        params,
    ).fetchall()

    tasks = []
    for row in rows:
        task = _row_to_dict(row)
        updates = conn.execute(
            "SELECT * FROM task_updates WHERE task_id = ? ORDER BY created_at ASC",
            (task["id"],),
        ).fetchall()
        task["updates"] = [dict(u) for u in updates]
        tasks.append(task)

    conn.close()
    return tasks


def link_task_to_pr(task_id: str, pr_ref: str) -> bool:
    """Add a PR reference to a task. Returns False if task not found."""
    return _add_to_json_list(task_id, "related_prs", pr_ref)


def link_task_to_issue(task_id: str, issue_ref: str) -> bool:
    """Add an issue reference to a task. Returns False if task not found."""
    return _add_to_json_list(task_id, "related_issues", issue_ref)


def clear_all_tasks() -> int:
    """Delete all tasks and updates. Returns number of tasks deleted."""
    ensure_tasks_db()
    conn = _connect()
    conn.execute("DELETE FROM task_updates")
    cursor = conn.execute("DELETE FROM tasks")
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


def _add_to_json_list(task_id: str, column: str, value: str) -> bool:
    """Append a value to a JSON array column on a task."""
    ensure_tasks_db()
    conn = _connect()
    row = conn.execute(f"SELECT {column} FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        conn.close()
        return False
    current: list[str] = json.loads(row[column] or "[]")
    if value not in current:
        current.append(value)
    now = _now_iso()
    conn.execute(
        f"UPDATE tasks SET {column} = ?, updated_at = ? WHERE id = ?",
        (json.dumps(current), now, task_id),
    )
    conn.commit()
    conn.close()
    return True


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a sqlite3.Row to a dict, parsing JSON columns."""
    d = dict(row)
    for col in ("tags", "related_prs", "related_issues"):
        if col in d and isinstance(d[col], str):
            d[col] = json.loads(d[col])
    return d
