"""Tests for the GitHub Issues tools."""

import json
from unittest.mock import patch, MagicMock

import pytest

from github_standup_agent.context import StandupContext
from github_standup_agent.config import StandupConfig

from .conftest import invoke_tool


class TestListIssues:
    """Tests for list_issues tool."""

    @pytest.fixture
    def mock_issue_response(self):
        """Sample issue search response."""
        return json.dumps([
            {
                "number": 456,
                "title": "Bug in login flow",
                "url": "https://github.com/owner/repo/issues/456",
                "state": "open",
                "createdAt": "2025-01-14T10:00:00Z",
                "updatedAt": "2025-01-15T10:00:00Z",
                "closedAt": None,
                "repository": {"nameWithOwner": "owner/repo"},
                "author": {"login": "testuser"},
                "labels": [{"name": "bug"}, {"name": "priority:high"}],
                "body": "The login form is broken",
            },
            {
                "number": 789,
                "title": "Add dark mode",
                "url": "https://github.com/owner/repo/issues/789",
                "state": "closed",
                "createdAt": "2025-01-10T10:00:00Z",
                "updatedAt": "2025-01-14T10:00:00Z",
                "closedAt": "2025-01-14T10:00:00Z",
                "repository": {"nameWithOwner": "owner/repo"},
                "author": {"login": "testuser"},
                "labels": [{"name": "enhancement"}],
                "body": "Feature request",
            },
        ])

    @patch("subprocess.run")
    def test_list_issues_authored(self, mock_run, mock_context, mock_issue_response):
        """Test list_issues with authored filter."""
        from github_standup_agent.tools.github.github_issues import list_issues

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_issue_response,
            stderr="",
        )

        result = invoke_tool(
            list_issues, mock_context, filter_by="authored", days_back=7
        )

        assert "Found 2 issue(s)" in result
        assert "#456" in result
        assert "#789" in result
        assert "bug" in result
        assert len(mock_context.collected_issues) == 2

    @patch("subprocess.run")
    def test_list_issues_no_results(self, mock_run, mock_context):
        """Test list_issues with no results."""
        from github_standup_agent.tools.github.github_issues import list_issues

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="[]",
            stderr="",
        )

        result = invoke_tool(
            list_issues, mock_context, filter_by="authored", days_back=1
        )

        assert "No issues found" in result

    @patch("subprocess.run")
    def test_list_issues_different_filters(
        self, mock_run, mock_context, mock_issue_response
    ):
        """Test list_issues with different filter_by values."""
        from github_standup_agent.tools.github.github_issues import list_issues

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_issue_response,
            stderr="",
        )

        for filter_by in ["authored", "assigned", "mentions", "involves"]:
            mock_context.collected_issues = []  # Reset
            result = invoke_tool(
                list_issues, mock_context, filter_by=filter_by, days_back=7
            )
            assert "Found 2 issue(s)" in result

    def test_list_issues_no_username(self, mock_config):
        """Test list_issues without username in context."""
        from github_standup_agent.tools.github.github_issues import list_issues

        context = StandupContext(config=mock_config, github_username=None)
        result = invoke_tool(list_issues, context, filter_by="authored")

        assert "username not available" in result.lower()


class TestGetIssueDetails:
    """Tests for get_issue_details tool."""

    @pytest.fixture
    def mock_issue_detail_response(self):
        """Sample issue detail response."""
        return json.dumps({
            "number": 456,
            "title": "Bug in login flow",
            "body": "Detailed description of the bug...",
            "url": "https://github.com/owner/repo/issues/456",
            "state": "OPEN",
            "stateReason": None,
            "author": {"login": "reporter"},
            "assignees": [{"login": "testuser"}],
            "createdAt": "2025-01-14T10:00:00Z",
            "updatedAt": "2025-01-15T10:00:00Z",
            "closedAt": None,
            "labels": [{"name": "bug"}],
            "milestone": {"title": "v1.1"},
            "closedByPullRequestsReferences": [],
            "comments": [
                {
                    "author": {"login": "testuser"},
                    "body": "I'm working on this",
                    "createdAt": "2025-01-15T08:00:00Z",
                }
            ],
        })

    @patch("subprocess.run")
    def test_get_issue_details_success(
        self, mock_run, mock_context, mock_issue_detail_response
    ):
        """Test get_issue_details returns formatted issue info."""
        from github_standup_agent.tools.github.github_issues import get_issue_details

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_issue_detail_response,
            stderr="",
        )

        result = invoke_tool(
            get_issue_details, mock_context, repo="owner/repo", number=456
        )

        assert "Issue #456" in result
        assert "Bug in login flow" in result
        assert "OPEN" in result
        assert "reporter" in result
        assert "bug" in result

        # Check caching
        assert "owner/repo#456" in mock_context.issue_details_cache

    @patch("subprocess.run")
    def test_get_issue_details_not_found(self, mock_run, mock_context):
        """Test get_issue_details handles not found."""
        from github_standup_agent.tools.github.github_issues import get_issue_details

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Could not resolve to an Issue",
        )

        result = invoke_tool(
            get_issue_details, mock_context, repo="owner/repo", number=999
        )

        assert "Error" in result

    @patch("subprocess.run")
    def test_get_issue_details_closed_issue(self, mock_run, mock_context):
        """Test get_issue_details shows closed issue info."""
        from github_standup_agent.tools.github.github_issues import get_issue_details

        response = json.dumps({
            "number": 456,
            "title": "Bug in login flow",
            "body": "Description",
            "url": "https://github.com/owner/repo/issues/456",
            "state": "CLOSED",
            "stateReason": "COMPLETED",
            "author": {"login": "reporter"},
            "assignees": [],
            "createdAt": "2025-01-14T10:00:00Z",
            "updatedAt": "2025-01-15T10:00:00Z",
            "closedAt": "2025-01-15T10:00:00Z",
            "labels": [],
            "milestone": None,
            "comments": [],
            "commentsCount": 0,
        })

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=response,
            stderr="",
        )

        result = invoke_tool(
            get_issue_details, mock_context, repo="owner/repo", number=456
        )

        assert "CLOSED" in result
        assert "COMPLETED" in result or "completed" in result.lower()
