"""Tests for the MCP server tools."""

import pytest

from github_standup_agent.mcp_server import (
    complete_task as _complete_task_tool,
    get_work_log as _get_work_log_tool,
    list_tasks as _list_tasks_tool,
    log_task as _log_task_tool,
    update_task as _update_task_tool,
)

# FastMCP @mcp.tool wraps functions in FunctionTool objects.
# Access the underlying function via .fn for direct testing.
log_task = _log_task_tool.fn
update_task = _update_task_tool.fn
complete_task = _complete_task_tool.fn
list_tasks = _list_tasks_tool.fn
get_work_log = _get_work_log_tool.fn


@pytest.fixture(autouse=True)
def use_tmp_db(tmp_path, monkeypatch):
    """Point the tasks DB to a temp directory for each test."""
    monkeypatch.setattr("github_standup_agent.tools.tasks.task_store.DATA_DIR", tmp_path)
    monkeypatch.setattr(
        "github_standup_agent.tools.tasks.task_store.TASKS_DB_FILE",
        tmp_path / "tasks.db",
    )


@pytest.fixture(autouse=True)
def mock_github_username(monkeypatch):
    """Provide a deterministic GitHub username."""
    monkeypatch.setattr(
        "github_standup_agent.mcp_server._get_github_username",
        lambda: "testuser",
    )


class TestLogTask:
    def test_basic(self):
        result = log_task(title="Fix auth bug")
        assert result["status"] == "ok"
        assert "Fix auth bug" in result["message"]
        assert result["task"]["title"] == "Fix auth bug"
        assert result["task"]["status"] == "in_progress"

    def test_with_tags(self):
        result = log_task(title="Refactor API", tags=["backend", "tech-debt"])
        assert result["task"]["tags"] == ["backend", "tech-debt"]


class TestUpdateTask:
    def test_add_note(self):
        task = log_task(title="Some work")
        task_id = task["task"]["id"]

        result = update_task(task_id=task_id, note="Tests passing now")
        assert result["status"] == "ok"
        assert "Some work" in result["message"]

    def test_change_status(self):
        task = log_task(title="Some work")
        task_id = task["task"]["id"]

        result = update_task(task_id=task_id, note="Done", status="completed")
        assert result["new_status"] == "completed"

    def test_nonexistent_task(self):
        result = update_task(task_id="nonexistent", note="test")
        assert result["status"] == "error"


class TestCompleteTask:
    def test_complete(self):
        task = log_task(title="Auth refactor")
        task_id = task["task"]["id"]

        result = complete_task(task_id=task_id)
        assert result["status"] == "ok"
        assert "Auth refactor" in result["message"]
        assert "duration_hours" in result

    def test_complete_with_note(self):
        task = log_task(title="Auth refactor")
        task_id = task["task"]["id"]

        result = complete_task(task_id=task_id, note="All tests green")
        assert result["status"] == "ok"

    def test_nonexistent_task(self):
        result = complete_task(task_id="nonexistent")
        assert result["status"] == "error"


class TestListTasks:
    def test_empty(self):
        result = list_tasks()
        assert result["task_count"] == 0

    def test_with_tasks(self):
        log_task(title="Task 1")
        log_task(title="Task 2")
        result = list_tasks()
        assert result["task_count"] == 2

    def test_filter_by_status(self):
        task = log_task(title="Active task")
        done_task = log_task(title="Done task")
        complete_task(task_id=done_task["task"]["id"])

        result = list_tasks(status="in_progress")
        assert result["task_count"] == 1
        assert result["tasks"][0]["id"] == task["task"]["id"]


class TestGetWorkLog:
    def test_empty(self):
        result = get_work_log()
        assert result["task_count"] == 0
        assert "No tasks" in result["log"]

    def test_with_tasks(self):
        log_task(title="Auth refactor")
        log_task(title="Fix billing bug")
        result = get_work_log()
        assert result["task_count"] == 2
        assert "Auth refactor" in result["log"]
        assert "Fix billing bug" in result["log"]
        assert "HIGH-SIGNAL" in result["log"]
