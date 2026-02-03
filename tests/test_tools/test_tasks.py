"""Tests for the task tracking function tools."""

from unittest.mock import patch

import pytest

from github_standup_agent.config import StandupConfig
from github_standup_agent.context import StandupContext

from .conftest import invoke_tool


@pytest.fixture(autouse=True)
def use_tmp_db(tmp_path, monkeypatch):
    """Point the tasks DB to a temp directory for each test."""
    monkeypatch.setattr("github_standup_agent.tools.tasks.task_store.DATA_DIR", tmp_path)
    monkeypatch.setattr(
        "github_standup_agent.tools.tasks.task_store.TASKS_DB_FILE",
        tmp_path / "tasks.db",
    )


@pytest.fixture
def mock_context():
    """Create a mock context for testing."""
    config = StandupConfig(github_username="testuser")
    return StandupContext(
        config=config,
        days_back=1,
        github_username="testuser",
    )


class TestLogTask:
    @patch("github_standup_agent.tools.tasks.task_tools.capture_event")
    def test_log_task(self, mock_capture, mock_context):
        from github_standup_agent.tools.tasks.task_tools import log_task

        result = invoke_tool(log_task, mock_context, title="Fix auth bug")
        assert "Fix auth bug" in result
        assert "id:" in result
        mock_capture.assert_called_once()
        assert mock_capture.call_args[1]["event_name"] == "task_created"

    @patch("github_standup_agent.tools.tasks.task_tools.capture_event")
    def test_log_task_with_tags(self, mock_capture, mock_context):
        from github_standup_agent.tools.tasks.task_tools import log_task

        result = invoke_tool(log_task, mock_context, title="Refactor API", tags=["backend"])
        assert "backend" in result


class TestUpdateTask:
    @patch("github_standup_agent.tools.tasks.task_tools.capture_event")
    def test_update_task(self, mock_capture, mock_context):
        from github_standup_agent.tools.tasks.task_tools import log_task, update_task
        from github_standup_agent.tools.tasks.task_store import list_tasks

        # First create a task
        invoke_tool(log_task, mock_context, title="Auth work")
        tasks = list_tasks()
        task_id = tasks[0]["id"]

        result = invoke_tool(update_task, mock_context, task_id=task_id, note="Tests passing")
        assert "Auth work" in result
        assert "Tests passing" in result

    @patch("github_standup_agent.tools.tasks.task_tools.capture_event")
    def test_update_nonexistent_task(self, mock_capture, mock_context):
        from github_standup_agent.tools.tasks.task_tools import update_task

        result = invoke_tool(update_task, mock_context, task_id="nonexistent", note="Some note")
        assert "not found" in result.lower()


class TestCompleteTask:
    @patch("github_standup_agent.tools.tasks.task_tools.capture_event")
    def test_complete_task(self, mock_capture, mock_context):
        from github_standup_agent.tools.tasks.task_tools import complete_task, log_task
        from github_standup_agent.tools.tasks.task_store import get_task, list_tasks

        invoke_tool(log_task, mock_context, title="Fix bug")
        tasks = list_tasks()
        task_id = tasks[0]["id"]

        result = invoke_tool(complete_task, mock_context, task_id=task_id)
        assert "Completed" in result
        assert "Fix bug" in result

        # Verify it's marked completed
        task = get_task(task_id)
        assert task["status"] == "completed"

        # Check PostHog event
        complete_call = [
            c for c in mock_capture.call_args_list if c[1].get("event_name") == "task_completed"
        ]
        assert len(complete_call) == 1
        props = complete_call[0][1]["properties"]
        assert "duration_hours" in props

    @patch("github_standup_agent.tools.tasks.task_tools.capture_event")
    def test_complete_nonexistent_task(self, mock_capture, mock_context):
        from github_standup_agent.tools.tasks.task_tools import complete_task

        result = invoke_tool(complete_task, mock_context, task_id="nonexistent")
        assert "not found" in result.lower()


class TestListMyTasks:
    @patch("github_standup_agent.tools.tasks.task_tools.capture_event")
    def test_list_tasks_empty(self, mock_capture, mock_context):
        from github_standup_agent.tools.tasks.task_tools import list_my_tasks

        result = invoke_tool(list_my_tasks, mock_context)
        assert "No tasks found" in result

    @patch("github_standup_agent.tools.tasks.task_tools.capture_event")
    def test_list_tasks_with_data(self, mock_capture, mock_context):
        from github_standup_agent.tools.tasks.task_tools import list_my_tasks, log_task

        invoke_tool(log_task, mock_context, title="Task A")
        invoke_tool(log_task, mock_context, title="Task B")

        result = invoke_tool(list_my_tasks, mock_context)
        assert "Task A" in result
        assert "Task B" in result
        assert "2 task(s)" in result


class TestGetTodaysWorkLog:
    @patch("github_standup_agent.tools.tasks.task_tools.capture_event")
    def test_empty_work_log(self, mock_capture, mock_context):
        from github_standup_agent.tools.tasks.task_tools import get_todays_work_log

        result = invoke_tool(get_todays_work_log, mock_context)
        assert "No tasks logged" in result

    @patch("github_standup_agent.tools.tasks.task_tools.capture_event")
    def test_work_log_with_tasks(self, mock_capture, mock_context):
        from github_standup_agent.tools.tasks.task_tools import (
            get_todays_work_log,
            log_task,
        )

        invoke_tool(log_task, mock_context, title="Auth refactor", tags=["backend"])
        result = invoke_tool(get_todays_work_log, mock_context)
        assert "HIGH-SIGNAL" in result
        assert "Auth refactor" in result
        assert "backend" in result


class TestLinkTask:
    @patch("github_standup_agent.tools.tasks.task_tools.capture_event")
    def test_link_pr(self, mock_capture, mock_context):
        from github_standup_agent.tools.tasks.task_tools import link_task, log_task
        from github_standup_agent.tools.tasks.task_store import list_tasks

        invoke_tool(log_task, mock_context, title="PR work")
        tasks = list_tasks()
        task_id = tasks[0]["id"]

        result = invoke_tool(link_task, mock_context, task_id=task_id, pr="org/repo#123")
        assert "Linked" in result
        assert "PR org/repo#123" in result

    @patch("github_standup_agent.tools.tasks.task_tools.capture_event")
    def test_link_no_refs(self, mock_capture, mock_context):
        from github_standup_agent.tools.tasks.task_tools import link_task

        result = invoke_tool(link_task, mock_context, task_id="some-id")
        assert "Provide" in result
