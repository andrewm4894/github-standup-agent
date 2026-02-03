"""Tests for the task store (SQLite storage layer)."""

import pytest

from github_standup_agent.tools.tasks.task_store import (
    add_task_update,
    clear_all_tasks,
    create_task,
    get_task,
    get_tasks_for_standup,
    link_task_to_issue,
    link_task_to_pr,
    list_tasks,
    update_task_status,
)


@pytest.fixture(autouse=True)
def use_tmp_db(tmp_path, monkeypatch):
    """Point the tasks DB to a temp directory for each test."""
    monkeypatch.setattr("github_standup_agent.tools.tasks.task_store.DATA_DIR", tmp_path)
    monkeypatch.setattr(
        "github_standup_agent.tools.tasks.task_store.TASKS_DB_FILE",
        tmp_path / "tasks.db",
    )


class TestCreateTask:
    def test_creates_task(self):
        task = create_task(username="testuser", title="Fix auth bug")
        assert task["title"] == "Fix auth bug"
        assert task["status"] == "in_progress"
        assert task["github_username"] == "testuser"
        assert task["tags"] == []
        assert len(task["id"]) == 12

    def test_creates_task_with_tags(self):
        task = create_task(username="testuser", title="Refactor API", tags=["backend", "tech-debt"])
        assert task["tags"] == ["backend", "tech-debt"]

    def test_creates_task_without_username(self):
        task = create_task(username=None, title="Anonymous task")
        assert task["github_username"] is None


class TestUpdateTaskStatus:
    def test_complete_task(self):
        task = create_task(username="testuser", title="Some work")
        updated = update_task_status(task["id"], "completed")
        assert updated is not None
        assert updated["status"] == "completed"
        assert updated["completed_at"] is not None

    def test_abandon_task(self):
        task = create_task(username="testuser", title="Abandoned work")
        updated = update_task_status(task["id"], "abandoned")
        assert updated is not None
        assert updated["status"] == "abandoned"

    def test_nonexistent_task_returns_none(self):
        result = update_task_status("nonexistent", "completed")
        assert result is None


class TestTaskUpdates:
    def test_add_update(self):
        task = create_task(username="testuser", title="Work item")
        update = add_task_update(task["id"], "Tests passing now")
        assert update["note"] == "Tests passing now"
        assert update["task_id"] == task["id"]

    def test_updates_appear_in_get_task(self):
        task = create_task(username="testuser", title="Work item")
        add_task_update(task["id"], "First update")
        add_task_update(task["id"], "Second update")

        fetched = get_task(task["id"])
        assert fetched is not None
        assert len(fetched["updates"]) == 2
        assert fetched["updates"][0]["note"] == "First update"
        assert fetched["updates"][1]["note"] == "Second update"


class TestGetTask:
    def test_get_existing_task(self):
        task = create_task(username="testuser", title="Test task")
        fetched = get_task(task["id"])
        assert fetched is not None
        assert fetched["title"] == "Test task"
        assert "updates" in fetched

    def test_get_nonexistent_task(self):
        assert get_task("nonexistent") is None


class TestListTasks:
    def test_list_all(self):
        create_task(username="testuser", title="Task 1")
        create_task(username="testuser", title="Task 2")
        tasks = list_tasks()
        assert len(tasks) == 2

    def test_filter_by_username(self):
        create_task(username="user1", title="Task A")
        create_task(username="user2", title="Task B")
        tasks = list_tasks(username="user1")
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Task A"

    def test_filter_by_status(self):
        t1 = create_task(username="testuser", title="Active")
        t2 = create_task(username="testuser", title="Done")
        update_task_status(t2["id"], "completed")

        active = list_tasks(status="in_progress")
        assert len(active) == 1
        assert active[0]["id"] == t1["id"]

        completed = list_tasks(status="completed")
        assert len(completed) == 1
        assert completed[0]["id"] == t2["id"]


class TestGetTasksForStandup:
    def test_includes_in_progress(self):
        create_task(username="testuser", title="Active task")
        tasks = get_tasks_for_standup(username="testuser", days_back=1)
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Active task"

    def test_includes_updates(self):
        task = create_task(username="testuser", title="With updates")
        add_task_update(task["id"], "Some progress")
        tasks = get_tasks_for_standup(username="testuser", days_back=1)
        assert len(tasks) == 1
        assert len(tasks[0]["updates"]) == 1


class TestLinkTasks:
    def test_link_pr(self):
        task = create_task(username="testuser", title="PR work")
        assert link_task_to_pr(task["id"], "org/repo#123") is True
        fetched = get_task(task["id"])
        assert "org/repo#123" in fetched["related_prs"]

    def test_link_issue(self):
        task = create_task(username="testuser", title="Issue work")
        assert link_task_to_issue(task["id"], "org/repo#456") is True
        fetched = get_task(task["id"])
        assert "org/repo#456" in fetched["related_issues"]

    def test_link_nonexistent_task(self):
        assert link_task_to_pr("nonexistent", "org/repo#1") is False

    def test_no_duplicate_links(self):
        task = create_task(username="testuser", title="Link test")
        link_task_to_pr(task["id"], "org/repo#1")
        link_task_to_pr(task["id"], "org/repo#1")
        fetched = get_task(task["id"])
        assert fetched["related_prs"].count("org/repo#1") == 1


class TestClearAllTasks:
    def test_clear(self):
        create_task(username="testuser", title="Task 1")
        create_task(username="testuser", title="Task 2")
        count = clear_all_tasks()
        assert count == 2
        assert list_tasks() == []
