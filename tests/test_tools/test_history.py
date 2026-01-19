"""Tests for the history tools."""

from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from github_standup_agent.context import StandupContext
from github_standup_agent.config import StandupConfig

from .conftest import invoke_tool


class TestGetRecentStandups:
    """Tests for get_recent_standups tool."""

    @patch("github_standup_agent.tools.history.StandupDatabase")
    def test_get_recent_standups_success(self, mock_db_class, mock_context):
        """Test retrieving recent standups."""
        from github_standup_agent.tools.history import get_recent_standups

        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.get_recent.return_value = [
            {"date": "2025-01-15", "summary": "Did: Fixed bug\nWill do: Deploy"},
            {"date": "2025-01-14", "summary": "Did: Code review\nWill do: Testing"},
        ]

        result = invoke_tool(get_recent_standups, mock_context, days=3)

        assert "Found 2 recent standup(s)" in result
        assert "2025-01-15" in result
        assert "2025-01-14" in result
        assert "Fixed bug" in result
        assert mock_context.recent_standups is not None
        assert len(mock_context.recent_standups) == 2

    @patch("github_standup_agent.tools.history.StandupDatabase")
    def test_get_recent_standups_empty(self, mock_db_class, mock_context):
        """Test with no previous standups."""
        from github_standup_agent.tools.history import get_recent_standups

        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.get_recent.return_value = []

        result = invoke_tool(get_recent_standups, mock_context, days=3)

        assert "No previous standups found" in result

    @patch("github_standup_agent.tools.history.StandupDatabase")
    def test_get_recent_standups_truncates_long(self, mock_db_class, mock_context):
        """Test that long summaries are truncated."""
        from github_standup_agent.tools.history import get_recent_standups

        long_summary = "A" * 600  # Longer than 500 char limit
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_db.get_recent.return_value = [
            {"date": "2025-01-15", "summary": long_summary},
        ]

        result = invoke_tool(get_recent_standups, mock_context, days=1)

        assert "..." in result
        # Full 600 char summary should not appear
        assert long_summary not in result


class TestSaveStandup:
    """Tests for save_standup tool."""

    @patch("github_standup_agent.tools.history.capture_event")
    @patch("github_standup_agent.tools.history.StandupDatabase")
    def test_save_standup_success(self, mock_db_class, mock_capture, mock_context):
        """Test saving standup to history."""
        from github_standup_agent.tools.history import save_standup

        mock_db = MagicMock()
        mock_db_class.return_value = mock_db

        mock_context.current_standup = "My standup content"
        mock_context.collected_prs = [{"number": 1}]
        mock_context.collected_issues = []
        mock_context.collected_commits = []
        mock_context.collected_reviews = []

        result = invoke_tool(save_standup, mock_context, summary=None)

        assert "Standup saved" in result
        mock_db.save.assert_called_once()
        mock_capture.assert_called_once()

    @patch("github_standup_agent.tools.history.capture_event")
    @patch("github_standup_agent.tools.history.StandupDatabase")
    def test_save_standup_explicit_summary(
        self, mock_db_class, mock_capture, mock_context
    ):
        """Test saving explicit summary text."""
        from github_standup_agent.tools.history import save_standup

        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        mock_context.collected_prs = []
        mock_context.collected_issues = []
        mock_context.collected_commits = []
        mock_context.collected_reviews = []

        result = invoke_tool(save_standup, mock_context, summary="Custom summary")

        assert "Standup saved" in result
        call_kwargs = mock_db.save.call_args[1]
        assert call_kwargs["summary"] == "Custom summary"

    @patch("github_standup_agent.tools.history.StandupDatabase")
    def test_save_standup_no_content(self, mock_db_class, mock_context):
        """Test saving with no content available."""
        from github_standup_agent.tools.history import save_standup

        mock_context.current_standup = None
        result = invoke_tool(save_standup, mock_context, summary=None)

        assert "No standup to save" in result
        mock_db_class.return_value.save.assert_not_called()


class TestSaveStandupToFile:
    """Tests for save_standup_to_file tool."""

    def test_save_to_file_success(self, mock_context, tmp_path, monkeypatch):
        """Test saving standup to file."""
        from github_standup_agent.tools.history import save_standup_to_file

        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        mock_context.current_standup = "My standup content"
        result = invoke_tool(
            save_standup_to_file, mock_context, summary=None, filename="standup.md"
        )

        assert "Standup saved to" in result
        assert (tmp_path / "standup.md").exists()
        assert (tmp_path / "standup.md").read_text() == "My standup content"

    def test_save_to_file_explicit_summary(self, mock_context, tmp_path, monkeypatch):
        """Test saving explicit summary to file."""
        from github_standup_agent.tools.history import save_standup_to_file

        monkeypatch.chdir(tmp_path)

        result = invoke_tool(
            save_standup_to_file,
            mock_context,
            summary="Custom content",
            filename="custom.md",
        )

        assert "Standup saved to" in result
        assert (tmp_path / "custom.md").exists()
        assert (tmp_path / "custom.md").read_text() == "Custom content"

    def test_save_to_file_no_content(self, mock_context):
        """Test saving to file with no content."""
        from github_standup_agent.tools.history import save_standup_to_file

        mock_context.current_standup = None
        result = invoke_tool(
            save_standup_to_file, mock_context, summary=None, filename="standup.md"
        )

        assert "No standup to save" in result

    def test_save_to_file_error(self, mock_context):
        """Test handling file write errors."""
        from github_standup_agent.tools.history import save_standup_to_file

        mock_context.current_standup = "Content"

        # Try to write to a non-existent directory
        result = invoke_tool(
            save_standup_to_file,
            mock_context,
            summary=None,
            filename="/nonexistent/path/standup.md",
        )

        assert "Failed to save" in result
