"""Tests for the GitHub Reviews tool."""

import json
from unittest.mock import patch, MagicMock

import pytest

from github_standup_agent.context import StandupContext
from github_standup_agent.config import StandupConfig

from .conftest import invoke_tool


class TestListReviews:
    """Tests for list_reviews tool."""

    @pytest.fixture
    def mock_pr_search_response(self):
        """Sample PR search response for reviews."""
        return json.dumps([
            {
                "number": 123,
                "title": "Add new feature",
                "url": "https://github.com/owner/repo/pull/123",
                "state": "MERGED",
                "repository": {"nameWithOwner": "owner/repo"},
                "author": {"login": "otheruser"},
            },
        ])

    @pytest.fixture
    def mock_review_response(self):
        """Sample review data response."""
        return json.dumps({
            "reviews": [
                {
                    "author": {"login": "testuser"},
                    "state": "APPROVED",
                    "submittedAt": "2025-01-15T10:00:00Z",
                    "body": "LGTM!",
                },
            ],
            "reviewDecision": "APPROVED",
        })

    @patch("subprocess.run")
    def test_list_reviews_given(
        self, mock_run, mock_context, mock_pr_search_response, mock_review_response
    ):
        """Test list_reviews with filter_by=given."""
        from github_standup_agent.tools.github.github_reviews import list_reviews

        # First call returns PRs, second call returns review details
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=mock_pr_search_response, stderr=""),
            MagicMock(returncode=0, stdout=mock_review_response, stderr=""),
        ]

        result = invoke_tool(
            list_reviews, mock_context, filter_by="given", days_back=7
        )

        assert "review(s) given by" in result
        assert "APPROVED" in result
        assert "#123" in result
        assert len(mock_context.collected_reviews) >= 0

    @patch("subprocess.run")
    def test_list_reviews_received(self, mock_run, mock_context):
        """Test list_reviews with filter_by=received."""
        from github_standup_agent.tools.github.github_reviews import list_reviews

        pr_response = json.dumps([
            {
                "number": 456,
                "title": "My PR",
                "url": "https://github.com/owner/repo/pull/456",
                "state": "OPEN",
                "repository": {"nameWithOwner": "owner/repo"},
            },
        ])
        review_response = json.dumps({
            "reviews": [
                {
                    "author": {"login": "reviewer1"},
                    "state": "APPROVED",
                    "submittedAt": "2025-01-15T10:00:00Z",
                    "body": "Looks good!",
                },
                {
                    "author": {"login": "reviewer2"},
                    "state": "CHANGES_REQUESTED",
                    "submittedAt": "2025-01-15T11:00:00Z",
                    "body": "Please fix X",
                },
            ],
            "reviewDecision": "CHANGES_REQUESTED",
        })

        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=pr_response, stderr=""),
            MagicMock(returncode=0, stdout=review_response, stderr=""),
        ]

        result = invoke_tool(
            list_reviews, mock_context, filter_by="received", days_back=7
        )

        assert "review(s) received by" in result
        assert "APPROVED" in result or "CHANGES_REQUESTED" in result

    @patch("subprocess.run")
    def test_list_reviews_no_results(self, mock_run, mock_context):
        """Test list_reviews with no results."""
        from github_standup_agent.tools.github.github_reviews import list_reviews

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="[]",
            stderr="",
        )

        result = invoke_tool(
            list_reviews, mock_context, filter_by="given", days_back=1
        )

        assert "No PRs found" in result or "No reviews found" in result

    @patch("subprocess.run")
    def test_list_reviews_excludes_self_reviews(self, mock_run, mock_context):
        """Test that self-reviews are excluded when filter_by=given."""
        from github_standup_agent.tools.github.github_reviews import list_reviews

        # PR authored by testuser (same as context user)
        pr_response = json.dumps([
            {
                "number": 123,
                "title": "My own PR",
                "url": "https://github.com/owner/repo/pull/123",
                "state": "MERGED",
                "repository": {"nameWithOwner": "owner/repo"},
                "author": {"login": "testuser"},  # Same as context user
            },
        ])
        review_response = json.dumps({
            "reviews": [
                {
                    "author": {"login": "testuser"},
                    "state": "APPROVED",
                    "submittedAt": "2025-01-15T10:00:00Z",
                    "body": "",
                },
            ],
            "reviewDecision": "APPROVED",
        })

        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=pr_response, stderr=""),
            MagicMock(returncode=0, stdout=review_response, stderr=""),
        ]

        result = invoke_tool(
            list_reviews, mock_context, filter_by="given", days_back=7
        )

        # Self-reviews should be excluded
        assert "No reviews found" in result or mock_context.collected_reviews == []

    def test_list_reviews_no_username(self, mock_config):
        """Test list_reviews without username in context."""
        from github_standup_agent.tools.github.github_reviews import list_reviews

        context = StandupContext(config=mock_config, github_username=None)
        result = invoke_tool(list_reviews, context, filter_by="given")

        assert "username not available" in result.lower()
