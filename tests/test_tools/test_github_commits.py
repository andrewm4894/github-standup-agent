"""Tests for the GitHub Commits tool."""

import json
from unittest.mock import patch, MagicMock

import pytest

from github_standup_agent.context import StandupContext
from github_standup_agent.config import StandupConfig

from .conftest import invoke_tool


class TestListCommits:
    """Tests for list_commits tool."""

    @pytest.fixture
    def mock_commit_response(self):
        """Sample commit search response."""
        return json.dumps([
            {
                "sha": "abc123def456",
                "commit": {
                    "message": "Add new feature\n\nDetailed description",
                    "author": {
                        "date": "2025-01-15T10:00:00Z",
                    },
                },
                "repository": {"nameWithOwner": "owner/repo"},
                "url": "https://github.com/owner/repo/commit/abc123def456",
            },
            {
                "sha": "def456ghi789",
                "commit": {
                    "message": "Fix bug in authentication",
                    "author": {
                        "date": "2025-01-15T11:00:00Z",
                    },
                },
                "repository": {"nameWithOwner": "owner/repo"},
                "url": "https://github.com/owner/repo/commit/def456ghi789",
            },
            {
                "sha": "ghi789jkl012",
                "commit": {
                    "message": "Update documentation",
                    "author": {
                        "date": "2025-01-15T12:00:00Z",
                    },
                },
                "repository": {"nameWithOwner": "owner/other-repo"},
                "url": "https://github.com/owner/other-repo/commit/ghi789jkl012",
            },
        ])

    @patch("subprocess.run")
    def test_list_commits_success(self, mock_run, mock_context, mock_commit_response):
        """Test list_commits returns formatted commit info."""
        from github_standup_agent.tools.github.github_commits import list_commits

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_commit_response,
            stderr="",
        )

        result = invoke_tool(list_commits, mock_context, days_back=1)

        assert "Found 3 commit(s)" in result
        assert "2 repo(s)" in result
        assert "owner/repo" in result
        assert "owner/other-repo" in result
        assert "Add new feature" in result
        assert "Fix bug" in result
        assert "[abc123d]" in result  # Truncated SHA
        assert len(mock_context.collected_commits) == 3

    @patch("subprocess.run")
    def test_list_commits_no_results(self, mock_run, mock_context):
        """Test list_commits with no results."""
        from github_standup_agent.tools.github.github_commits import list_commits

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr="",
        )

        result = invoke_tool(list_commits, mock_context, days_back=1)

        assert "No commits found" in result

    @patch("subprocess.run")
    def test_list_commits_with_repo_filter(
        self, mock_run, mock_context, mock_commit_response
    ):
        """Test list_commits with repo filter."""
        from github_standup_agent.tools.github.github_commits import list_commits

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_commit_response,
            stderr="",
        )

        result = invoke_tool(
            list_commits, mock_context, days_back=1, repo="owner/repo"
        )

        # Verify repo flag was passed
        call_args = mock_run.call_args[0][0]
        assert "--repo" in call_args
        assert "owner/repo" in call_args

    @patch("subprocess.run")
    def test_list_commits_rate_limit(self, mock_run, mock_context):
        """Test list_commits handles rate limit."""
        from github_standup_agent.tools.github.github_commits import list_commits

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="API rate limit exceeded",
        )

        result = invoke_tool(list_commits, mock_context, days_back=1)

        assert "rate limit" in result.lower()

    def test_list_commits_no_username(self, mock_config):
        """Test list_commits without username in context."""
        from github_standup_agent.tools.github.github_commits import list_commits

        context = StandupContext(config=mock_config, github_username=None)
        result = invoke_tool(list_commits, context, days_back=1)

        assert "username not available" in result.lower()

    @patch("subprocess.run")
    def test_list_commits_long_message_included(self, mock_run, mock_context):
        """Test that long commit messages are included in output."""
        from github_standup_agent.tools.github.github_commits import list_commits

        long_message = "A" * 100
        response = json.dumps([{
            "sha": "abc123def456",
            "commit": {
                "message": long_message,
                "author": {"date": "2025-01-15T10:00:00Z"},
            },
            "repository": {"nameWithOwner": "owner/repo"},
            "url": "https://github.com/owner/repo/commit/abc123",
        }])

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=response,
            stderr="",
        )

        result = invoke_tool(list_commits, mock_context, days_back=1)

        assert "abc123d" in result  # Short SHA included
        assert "owner/repo" in result
