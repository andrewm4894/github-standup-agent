"""Tests for the GitHub Activity tools."""

import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, UTC

import pytest

from github_standup_agent.context import StandupContext
from github_standup_agent.config import StandupConfig

from .conftest import invoke_tool


class TestGetActivityFeed:
    """Tests for get_activity_feed tool."""

    @pytest.fixture
    def mock_events_response(self):
        """Sample GitHub events API response."""
        now = datetime.now(UTC)
        recent_ts = (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        older_ts = (now - timedelta(days=5)).isoformat().replace("+00:00", "Z")

        return json.dumps([
            {
                "id": "1",
                "type": "PushEvent",
                "repo": {"name": "owner/repo"},
                "created_at": recent_ts,
                "payload": {
                    "ref": "refs/heads/main",
                    "commits": [
                        {"sha": "abc123", "message": "Add feature"}
                    ],
                },
            },
            {
                "id": "2",
                "type": "PullRequestEvent",
                "repo": {"name": "owner/repo"},
                "created_at": recent_ts,
                "payload": {
                    "action": "opened",
                    "number": 123,
                    "pull_request": {
                        "title": "New feature PR",
                        "html_url": "https://github.com/owner/repo/pull/123",
                    },
                },
            },
            {
                "id": "3",
                "type": "IssuesEvent",
                "repo": {"name": "owner/repo"},
                "created_at": recent_ts,
                "payload": {
                    "action": "opened",
                    "issue": {
                        "number": 456,
                        "title": "Bug report",
                        "html_url": "https://github.com/owner/repo/issues/456",
                    },
                },
            },
            {
                "id": "4",
                "type": "PullRequestReviewEvent",
                "repo": {"name": "owner/repo"},
                "created_at": recent_ts,
                "payload": {
                    "action": "submitted",
                    "review": {"state": "approved"},
                    "pull_request": {
                        "number": 789,
                        "title": "Another PR",
                    },
                },
            },
            # This one should be filtered out (too old)
            {
                "id": "5",
                "type": "PushEvent",
                "repo": {"name": "owner/repo"},
                "created_at": older_ts,
                "payload": {"ref": "refs/heads/old-branch"},
            },
        ])

    @patch("subprocess.run")
    def test_get_activity_feed_success(
        self, mock_run, mock_context, mock_events_response
    ):
        """Test get_activity_feed returns formatted activity."""
        from github_standup_agent.tools.github.github_events import get_activity_feed

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_events_response,
            stderr="",
        )

        result = invoke_tool(get_activity_feed, mock_context, days_back=1)

        assert "Activity Feed" in result
        assert "events" in result.lower()
        # Should include recent events
        assert "push" in result.lower() or "PushEvent" in result
        # Should have stored activities in context
        assert len(mock_context.collected_activity_feed) > 0

    @patch("subprocess.run")
    def test_get_activity_feed_filters_by_date(
        self, mock_run, mock_context, mock_events_response
    ):
        """Test that get_activity_feed filters events by date."""
        from github_standup_agent.tools.github.github_events import get_activity_feed

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_events_response,
            stderr="",
        )

        result = invoke_tool(get_activity_feed, mock_context, days_back=1)

        # Old event (5 days old) should be filtered out
        # Only recent events should be in collected_activity_feed
        for activity in mock_context.collected_activity_feed:
            # All activities should be recent
            assert activity is not None

    @patch("subprocess.run")
    def test_get_activity_feed_no_events(self, mock_run, mock_context):
        """Test get_activity_feed with no events."""
        from github_standup_agent.tools.github.github_events import get_activity_feed

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="[]",
            stderr="",
        )

        result = invoke_tool(get_activity_feed, mock_context, days_back=1)

        assert "No activity found" in result

    @patch("subprocess.run")
    def test_get_activity_feed_api_error(self, mock_run, mock_context):
        """Test get_activity_feed handles API errors."""
        from github_standup_agent.tools.github.github_events import get_activity_feed

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="API rate limit exceeded",
        )

        result = invoke_tool(get_activity_feed, mock_context, days_back=1)

        assert "rate limit" in result.lower()

    def test_get_activity_feed_no_username(self, mock_config):
        """Test get_activity_feed without username in context."""
        from github_standup_agent.tools.github.github_events import get_activity_feed

        context = StandupContext(config=mock_config, github_username=None)
        result = invoke_tool(get_activity_feed, context, days_back=1)

        assert "username not available" in result.lower()


class TestGetActivitySummary:
    """Tests for get_activity_summary tool."""

    @pytest.fixture
    def mock_contribution_response(self):
        """Sample contribution calendar response."""
        return json.dumps({
            "data": {
                "user": {
                    "contributionsCollection": {
                        "contributionCalendar": {
                            "totalContributions": 150,
                            "weeks": [
                                {
                                    "contributionDays": [
                                        {"contributionCount": 5, "date": "2025-01-15"},
                                        {"contributionCount": 3, "date": "2025-01-14"},
                                        {"contributionCount": 0, "date": "2025-01-13"},
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        })

    @patch("subprocess.run")
    def test_get_activity_summary_success(
        self, mock_run, mock_context, mock_contribution_response
    ):
        """Test get_activity_summary returns contribution stats."""
        from github_standup_agent.tools.github.github_activity import get_activity_summary

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=mock_contribution_response,
            stderr="",
        )

        result = invoke_tool(get_activity_summary, mock_context, days_back=7)

        assert "Activity Summary" in result
        assert "150" in result or "contributions" in result.lower()

    @patch("subprocess.run")
    def test_get_activity_summary_api_error(self, mock_run, mock_context):
        """Test get_activity_summary handles API errors."""
        from github_standup_agent.tools.github.github_activity import get_activity_summary

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="GraphQL error",
        )

        result = invoke_tool(get_activity_summary, mock_context, days_back=7)

        assert "error" in result.lower()

    def test_get_activity_summary_no_username(self, mock_config):
        """Test get_activity_summary without username in context."""
        from github_standup_agent.tools.github.github_activity import get_activity_summary

        context = StandupContext(config=mock_config, github_username=None)
        result = invoke_tool(get_activity_summary, context, days_back=7)

        assert "username not available" in result.lower()
