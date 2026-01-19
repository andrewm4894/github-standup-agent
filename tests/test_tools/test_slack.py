"""Tests for the Slack tools."""

import json
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime, timedelta

import pytest

from github_standup_agent.context import StandupContext
from github_standup_agent.config import StandupConfig

from .conftest import invoke_tool


@pytest.fixture
def mock_config_with_slack():
    """Create a mock configuration with Slack enabled."""
    config = StandupConfig(
        github_username="testuser",
        slack_channel="standups",
    )
    return config


@pytest.fixture
def mock_context_with_slack(mock_config_with_slack):
    """Create a mock context with Slack configured."""
    return StandupContext(
        config=mock_config_with_slack,
        days_back=1,
        github_username="testuser",
    )


class TestGetTeamSlackStandups:
    """Tests for get_team_slack_standups tool."""

    @patch("github_standup_agent.tools.slack.slack_standups.get_slack_client")
    @patch("github_standup_agent.tools.slack.slack_standups.resolve_channel_id")
    @patch("github_standup_agent.tools.slack.slack_standups.get_channel_messages")
    @patch("github_standup_agent.tools.slack.slack_standups.get_thread_replies")
    @patch.object(StandupConfig, "get_slack_token", return_value="xoxb-test")
    def test_get_team_slack_standups_success(
        self,
        mock_get_token,
        mock_get_replies,
        mock_get_messages,
        mock_resolve_channel,
        mock_get_client,
        mock_context_with_slack,
    ):
        """Test get_team_slack_standups returns formatted standups."""
        from github_standup_agent.tools.slack.slack_standups import (
            get_team_slack_standups,
        )

        # Mock the Slack client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_resolve_channel.return_value = "C123456"

        # Create a recent timestamp
        now = datetime.now()
        recent_ts = str(now.timestamp())

        mock_get_messages.return_value = [
            {
                "ts": recent_ts,
                "text": "Standup - January 15, 2025",
                "thread_ts": recent_ts,
            }
        ]
        mock_get_replies.return_value = [
            {
                "user": "U123",
                "text": "Did: Fixed bug\nWill do: Deploy",
                "ts": recent_ts,
            }
        ]

        result = invoke_tool(
            get_team_slack_standups, mock_context_with_slack, days_back=1
        )

        assert "standup thread(s)" in result.lower()
        assert mock_context_with_slack.slack_channel_id == "C123456"
        assert len(mock_context_with_slack.collected_slack_standups) > 0

    @patch.object(StandupConfig, "get_slack_token", return_value=None)
    def test_get_team_slack_standups_no_token(self, mock_get_token, mock_config):
        """Test get_team_slack_standups without token configured."""
        from github_standup_agent.tools.slack.slack_standups import (
            get_team_slack_standups,
        )

        context = StandupContext(config=mock_config, github_username="testuser")
        result = invoke_tool(get_team_slack_standups, context, days_back=1)

        assert "not configured" in result.lower()

    @patch.object(StandupConfig, "get_slack_token", return_value="xoxb-test")
    def test_get_team_slack_standups_no_channel(self, mock_get_token):
        """Test get_team_slack_standups without channel configured."""
        from github_standup_agent.tools.slack.slack_standups import (
            get_team_slack_standups,
        )

        # Config with token but no channel
        config = StandupConfig(github_username="testuser", slack_channel=None)
        context = StandupContext(config=config, github_username="testuser")
        result = invoke_tool(get_team_slack_standups, context, days_back=1)

        assert "channel not configured" in result.lower()


class TestPublishStandupToSlack:
    """Tests for publish_standup_to_slack tool."""

    @patch("github_standup_agent.tools.slack.slack_publish.get_slack_client")
    @patch("github_standup_agent.tools.slack.slack_publish.post_to_thread")
    @patch.object(StandupConfig, "get_slack_token", return_value="xoxb-test")
    def test_publish_standup_confirmed(
        self,
        mock_get_token,
        mock_post_thread,
        mock_get_client,
        mock_context_with_slack,
    ):
        """Test publishing standup when confirmed."""
        from github_standup_agent.tools.slack.slack_publish import (
            publish_standup_to_slack,
        )

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_post_thread.return_value = {"ok": True, "ts": "123.456"}

        # Set up context
        mock_context_with_slack.slack_publish_confirmed = True
        mock_context_with_slack.slack_channel_id = "C123456"
        mock_context_with_slack.slack_thread_ts = "123.456"
        mock_context_with_slack.current_standup = "My standup content"

        result = invoke_tool(
            publish_standup_to_slack,
            mock_context_with_slack,
            standup_text="My standup content",
            confirmed=True,
        )

        assert "posted" in result.lower()
        mock_post_thread.assert_called_once()

    @patch.object(StandupConfig, "get_slack_token", return_value="xoxb-test")
    def test_publish_standup_not_confirmed(
        self, mock_get_token, mock_context_with_slack
    ):
        """Test publishing standup when not confirmed shows preview."""
        from github_standup_agent.tools.slack.slack_publish import (
            publish_standup_to_slack,
        )

        mock_context_with_slack.slack_publish_confirmed = False
        mock_context_with_slack.slack_channel_id = "C123456"
        mock_context_with_slack.slack_thread_ts = "123.456"

        result = invoke_tool(
            publish_standup_to_slack,
            mock_context_with_slack,
            standup_text="My standup content",
        )

        assert "confirm" in result.lower() or "preview" in result.lower()
        # Should stage the content
        assert mock_context_with_slack.slack_standup_to_publish == "My standup content"

    @patch.object(StandupConfig, "get_slack_token", return_value="xoxb-test")
    def test_publish_standup_no_thread(self, mock_get_token, mock_context_with_slack):
        """Test publishing standup without thread_ts."""
        from github_standup_agent.tools.slack.slack_publish import (
            publish_standup_to_slack,
        )

        mock_context_with_slack.slack_channel_id = "C123456"
        mock_context_with_slack.slack_thread_ts = None  # No thread

        result = invoke_tool(
            publish_standup_to_slack,
            mock_context_with_slack,
            standup_text="My standup",
        )

        assert "thread" in result.lower() or "no standup thread" in result.lower()


class TestConfirmSlackPublish:
    """Tests for confirm_slack_publish tool."""

    def test_confirm_slack_publish_sets_flag(self, mock_context_with_slack):
        """Test confirm_slack_publish sets the confirmation flag."""
        from github_standup_agent.tools.slack.slack_publish import confirm_slack_publish

        mock_context_with_slack.slack_publish_confirmed = False

        result = invoke_tool(confirm_slack_publish, mock_context_with_slack)

        assert mock_context_with_slack.slack_publish_confirmed is True
        assert "confirmation" in result.lower()

    def test_confirm_slack_publish_already_confirmed(self, mock_context_with_slack):
        """Test confirm_slack_publish when already confirmed."""
        from github_standup_agent.tools.slack.slack_publish import confirm_slack_publish

        mock_context_with_slack.slack_publish_confirmed = True

        result = invoke_tool(confirm_slack_publish, mock_context_with_slack)

        assert mock_context_with_slack.slack_publish_confirmed is True
