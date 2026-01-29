"""Tests for the history tools."""

from pathlib import Path

import pytest

from github_standup_agent.context import StandupContext
from github_standup_agent.config import StandupConfig

from .conftest import invoke_tool


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
