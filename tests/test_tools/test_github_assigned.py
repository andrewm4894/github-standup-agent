"""Tests for the GitHub Assigned Items tool."""

import json
from unittest.mock import patch, MagicMock

import pytest

from github_standup_agent.context import StandupContext
from github_standup_agent.config import StandupConfig

from .conftest import invoke_tool


class TestListAssignedItems:
    """Tests for list_assigned_items tool."""

    @pytest.fixture
    def mock_assigned_issues_response(self):
        """Sample assigned issues response."""
        return json.dumps([
            {
                "number": 100,
                "title": "Implement feature X",
                "url": "https://github.com/owner/repo/issues/100",
                "state": "open",
                "repository": {"nameWithOwner": "owner/repo"},
                "labels": [{"name": "feature"}, {"name": "in-progress"}],
                "updatedAt": "2025-01-10T10:00:00Z",
            },
            {
                "number": 200,
                "title": "Fix critical bug",
                "url": "https://github.com/owner/other-repo/issues/200",
                "state": "open",
                "repository": {"nameWithOwner": "owner/other-repo"},
                "labels": [{"name": "bug"}, {"name": "critical"}],
                "updatedAt": "2025-01-05T10:00:00Z",
            },
        ])

    @pytest.fixture
    def mock_assigned_prs_response(self):
        """Sample assigned PRs response."""
        return json.dumps([
            {
                "number": 50,
                "title": "Add new endpoint",
                "url": "https://github.com/owner/repo/pull/50",
                "state": "open",
                "repository": {"nameWithOwner": "owner/repo"},
                "labels": [],
                "updatedAt": "2025-01-12T10:00:00Z",
                "isDraft": False,
            },
            {
                "number": 75,
                "title": "WIP: Refactor auth",
                "url": "https://github.com/owner/repo/pull/75",
                "state": "open",
                "repository": {"nameWithOwner": "owner/repo"},
                "labels": [{"name": "wip"}],
                "updatedAt": "2025-01-08T10:00:00Z",
                "isDraft": True,
            },
        ])

    @patch("subprocess.run")
    def test_list_assigned_items_success(
        self,
        mock_run,
        mock_context,
        mock_assigned_issues_response,
        mock_assigned_prs_response,
    ):
        """Test list_assigned_items returns both issues and PRs."""
        from github_standup_agent.tools.github.github_assigned import list_assigned_items

        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=mock_assigned_issues_response, stderr=""),
            MagicMock(returncode=0, stdout=mock_assigned_prs_response, stderr=""),
        ]

        result = invoke_tool(list_assigned_items, mock_context)

        assert "Found 4 open item(s)" in result
        assert "Issues (2)" in result
        assert "Pull Requests (2)" in result
        assert "#100" in result
        assert "#200" in result
        assert "#50" in result
        assert "#75" in result
        assert "(DRAFT)" in result  # PR 75 is a draft
        assert "feature" in result
        assert "critical" in result

    @patch("subprocess.run")
    def test_list_assigned_items_issues_only(
        self, mock_run, mock_context, mock_assigned_issues_response
    ):
        """Test list_assigned_items with only issues."""
        from github_standup_agent.tools.github.github_assigned import list_assigned_items

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_assigned_issues_response,
            stderr="",
        )

        result = invoke_tool(list_assigned_items, mock_context, include_prs=False)

        assert "Issues" in result
        assert "Pull Requests" not in result

    @patch("subprocess.run")
    def test_list_assigned_items_prs_only(
        self, mock_run, mock_context, mock_assigned_prs_response
    ):
        """Test list_assigned_items with only PRs."""
        from github_standup_agent.tools.github.github_assigned import list_assigned_items

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_assigned_prs_response,
            stderr="",
        )

        result = invoke_tool(list_assigned_items, mock_context, include_issues=False)

        assert "Pull Requests" in result
        assert "Issues" not in result

    @patch("subprocess.run")
    def test_list_assigned_items_no_results(self, mock_run, mock_context):
        """Test list_assigned_items with no results."""
        from github_standup_agent.tools.github.github_assigned import list_assigned_items

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="[]",
            stderr="",
        )

        result = invoke_tool(list_assigned_items, mock_context)

        assert "No open items assigned" in result

    @patch("subprocess.run")
    def test_list_assigned_items_with_repo_filter(
        self, mock_run, mock_context, mock_assigned_issues_response
    ):
        """Test list_assigned_items with repo filter."""
        from github_standup_agent.tools.github.github_assigned import list_assigned_items

        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=mock_assigned_issues_response, stderr=""),
            MagicMock(returncode=0, stdout="[]", stderr=""),
        ]

        result = invoke_tool(list_assigned_items, mock_context, repo="owner/repo")

        # Verify repo flag was passed in commands
        for call in mock_run.call_args_list:
            cmd = call[0][0]
            if "--repo" in cmd:
                assert "owner/repo" in cmd

    def test_list_assigned_items_no_username(self, mock_config):
        """Test list_assigned_items without username in context."""
        from github_standup_agent.tools.github.github_assigned import list_assigned_items

        context = StandupContext(config=mock_config, github_username=None)
        result = invoke_tool(list_assigned_items, context)

        assert "username not available" in result.lower()

    @patch("subprocess.run")
    def test_list_assigned_items_groups_by_repo(
        self,
        mock_run,
        mock_context,
        mock_assigned_issues_response,
        mock_assigned_prs_response,
    ):
        """Test that items are grouped by repository."""
        from github_standup_agent.tools.github.github_assigned import list_assigned_items

        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=mock_assigned_issues_response, stderr=""),
            MagicMock(returncode=0, stdout=mock_assigned_prs_response, stderr=""),
        ]

        result = invoke_tool(list_assigned_items, mock_context)

        # Both repos should appear
        assert "owner/repo" in result
        assert "owner/other-repo" in result
