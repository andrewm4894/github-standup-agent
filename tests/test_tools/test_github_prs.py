"""Tests for the GitHub PRs tools."""

import json
from unittest.mock import patch, MagicMock

import pytest

from github_standup_agent.context import StandupContext
from github_standup_agent.config import StandupConfig

from .conftest import invoke_tool


def test_context_stores_prs(mock_context: StandupContext):
    """Test that PRs are stored in context."""
    # Initially empty
    assert mock_context.collected_prs == []

    # After adding data
    mock_context.collected_prs = [{"number": 1, "title": "Test PR"}]
    assert len(mock_context.collected_prs) == 1
    assert mock_context.collected_prs[0]["number"] == 1


class TestListPrs:
    """Tests for list_prs tool."""

    @pytest.fixture
    def mock_pr_response(self):
        """Sample PR search response."""
        return json.dumps([
            {
                "number": 123,
                "title": "Add new feature",
                "url": "https://github.com/owner/repo/pull/123",
                "state": "MERGED",
                "createdAt": "2025-01-14T10:00:00Z",
                "updatedAt": "2025-01-15T10:00:00Z",
                "closedAt": "2025-01-15T09:00:00Z",
                "repository": {"nameWithOwner": "owner/repo"},
                "isDraft": False,
                "author": {"login": "testuser"},
                "labels": [{"name": "enhancement"}],
                "body": "This is a test PR",
                "commentsCount": 5,
            },
            {
                "number": 124,
                "title": "Fix bug",
                "url": "https://github.com/owner/repo/pull/124",
                "state": "OPEN",
                "createdAt": "2025-01-15T10:00:00Z",
                "updatedAt": "2025-01-15T12:00:00Z",
                "closedAt": None,
                "repository": {"nameWithOwner": "owner/repo"},
                "isDraft": True,
                "author": {"login": "testuser"},
                "labels": [],
                "body": "",
                "commentsCount": 0,
            },
        ])

    @patch("subprocess.run")
    def test_list_prs_authored(self, mock_run, mock_context, mock_pr_response):
        """Test list_prs with authored filter."""
        from github_standup_agent.tools.github.github_prs import list_prs

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_pr_response,
            stderr="",
        )

        result = invoke_tool(
            list_prs, mock_context, filter_by="authored", days_back=7
        )

        assert "Found 2 PR(s)" in result
        assert "owner/repo" in result
        assert "#123" in result
        assert "#124" in result
        assert "(DRAFT)" in result  # PR 124 is a draft
        assert len(mock_context.collected_prs) == 2

    @patch("subprocess.run")
    def test_list_prs_no_results(self, mock_run, mock_context):
        """Test list_prs with no results."""
        from github_standup_agent.tools.github.github_prs import list_prs

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="[]",
            stderr="",
        )

        result = invoke_tool(
            list_prs, mock_context, filter_by="authored", days_back=1
        )

        assert "No pull requests found" in result

    @patch("subprocess.run")
    def test_list_prs_api_error(self, mock_run, mock_context):
        """Test list_prs handles API errors."""
        from github_standup_agent.tools.github.github_prs import list_prs

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="API rate limit exceeded",
        )

        result = invoke_tool(
            list_prs, mock_context, filter_by="authored", days_back=1
        )

        assert "rate limit" in result.lower()

    @patch("subprocess.run")
    def test_list_prs_different_filters(self, mock_run, mock_context, mock_pr_response):
        """Test list_prs with different filter_by values."""
        from github_standup_agent.tools.github.github_prs import list_prs

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_pr_response,
            stderr="",
        )

        # Test each filter type
        for filter_by in ["authored", "reviewed", "assigned", "involves"]:
            mock_context.collected_prs = []  # Reset
            result = invoke_tool(
                list_prs, mock_context, filter_by=filter_by, days_back=7
            )
            assert "Found 2 PR(s)" in result

    def test_list_prs_no_username(self, mock_config):
        """Test list_prs without username in context."""
        from github_standup_agent.tools.github.github_prs import list_prs

        context = StandupContext(config=mock_config, github_username=None)
        result = invoke_tool(list_prs, context, filter_by="authored")

        assert "username not available" in result.lower()


class TestGetPrDetails:
    """Tests for get_pr_details tool."""

    @pytest.fixture
    def mock_pr_detail_response(self):
        """Sample PR detail response."""
        return json.dumps({
            "number": 123,
            "title": "Add new feature",
            "body": "This is a detailed description of the PR.",
            "url": "https://github.com/owner/repo/pull/123",
            "state": "MERGED",
            "isDraft": False,
            "author": {"login": "testuser"},
            "baseRefName": "main",
            "headRefName": "feature-branch",
            "createdAt": "2025-01-14T10:00:00Z",
            "updatedAt": "2025-01-15T10:00:00Z",
            "mergedAt": "2025-01-15T09:00:00Z",
            "closedAt": "2025-01-15T09:00:00Z",
            "additions": 100,
            "deletions": 50,
            "changedFiles": 5,
            "reviewDecision": "APPROVED",
            "reviews": [
                {
                    "author": {"login": "reviewer1"},
                    "state": "APPROVED",
                    "submittedAt": "2025-01-15T08:00:00Z",
                }
            ],
            "closingIssuesReferences": [
                {"number": 456, "title": "Related issue"}
            ],
            "labels": [{"name": "enhancement"}],
            "milestone": {"title": "v1.0"},
            "statusCheckRollup": [
                {"name": "CI", "conclusion": "SUCCESS"}
            ],
        })

    @patch("subprocess.run")
    def test_get_pr_details_success(
        self, mock_run, mock_context, mock_pr_detail_response
    ):
        """Test get_pr_details returns formatted PR info."""
        from github_standup_agent.tools.github.github_prs import get_pr_details

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_pr_detail_response,
            stderr="",
        )

        result = invoke_tool(get_pr_details, mock_context, repo="owner/repo", number=123)

        assert "PR #123" in result
        assert "Add new feature" in result
        assert "testuser" in result
        assert "APPROVED" in result
        assert "feature-branch" in result
        assert "+100/-50" in result
        assert "enhancement" in result

        # Check caching
        assert "owner/repo#123" in mock_context.pr_details_cache

    @patch("subprocess.run")
    def test_get_pr_details_not_found(self, mock_run, mock_context):
        """Test get_pr_details handles not found."""
        from github_standup_agent.tools.github.github_prs import get_pr_details

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Could not resolve to a PullRequest",
        )

        result = invoke_tool(get_pr_details, mock_context, repo="owner/repo", number=999)

        assert "Error" in result
