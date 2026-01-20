"""Tests for the feedback tools."""

from unittest.mock import patch, MagicMock

import pytest

from github_standup_agent.context import StandupContext
from github_standup_agent.config import StandupConfig

from .conftest import invoke_tool


@pytest.fixture
def mock_context():
    """Create a mock context for testing."""
    config = StandupConfig(github_username="testuser")
    return StandupContext(
        config=config,
        days_back=1,
        github_username="testuser",
    )


class TestCaptureFeedbackRating:
    """Tests for capture_feedback_rating tool."""

    @patch("github_standup_agent.tools.feedback.get_current_trace")
    @patch("github_standup_agent.tools.feedback.capture_ai_metric")
    @patch("github_standup_agent.tools.feedback.custom_span")
    def test_capture_good_rating(
        self,
        mock_custom_span,
        mock_capture_metric,
        mock_get_trace,
        mock_context,
    ):
        """Test capturing a positive rating."""
        from github_standup_agent.tools.feedback import capture_feedback_rating

        # Mock the trace
        mock_trace = MagicMock()
        mock_trace.trace_id = "test-trace-id-123"
        mock_get_trace.return_value = mock_trace

        # Mock the custom_span context manager
        mock_custom_span.return_value.__enter__ = MagicMock(return_value=None)
        mock_custom_span.return_value.__exit__ = MagicMock(return_value=None)

        result = invoke_tool(capture_feedback_rating, mock_context, rating="good")

        assert "positive" in result.lower()
        mock_capture_metric.assert_called_once_with(
            "test-trace-id-123", "quality", "good", comment=None
        )
        mock_custom_span.assert_called_once()

    @patch("github_standup_agent.tools.feedback.get_current_trace")
    @patch("github_standup_agent.tools.feedback.capture_ai_metric")
    @patch("github_standup_agent.tools.feedback.custom_span")
    def test_capture_bad_rating_with_comment(
        self,
        mock_custom_span,
        mock_capture_metric,
        mock_get_trace,
        mock_context,
    ):
        """Test capturing a negative rating with comment."""
        from github_standup_agent.tools.feedback import capture_feedback_rating

        mock_trace = MagicMock()
        mock_trace.trace_id = "test-trace-id-456"
        mock_get_trace.return_value = mock_trace

        mock_custom_span.return_value.__enter__ = MagicMock(return_value=None)
        mock_custom_span.return_value.__exit__ = MagicMock(return_value=None)

        result = invoke_tool(
            capture_feedback_rating,
            mock_context,
            rating="bad",
            comment="missed the auth PR review",
        )

        assert "negative" in result.lower()
        assert "missed the auth PR review" in result
        mock_capture_metric.assert_called_once_with(
            "test-trace-id-456", "quality", "bad", comment="missed the auth PR review"
        )

    @patch("github_standup_agent.tools.feedback.get_current_trace")
    @patch("github_standup_agent.tools.feedback.capture_ai_metric")
    @patch("github_standup_agent.tools.feedback.custom_span")
    def test_no_trace_id_graceful(
        self,
        mock_custom_span,
        mock_capture_metric,
        mock_get_trace,
        mock_context,
    ):
        """Test that feedback is handled gracefully when no trace is active."""
        from github_standup_agent.tools.feedback import capture_feedback_rating

        # No active trace
        mock_get_trace.return_value = None

        mock_custom_span.return_value.__enter__ = MagicMock(return_value=None)
        mock_custom_span.return_value.__exit__ = MagicMock(return_value=None)

        result = invoke_tool(capture_feedback_rating, mock_context, rating="good")

        # Should still return success
        assert "positive" in result.lower()
        # But should not call capture_ai_metric without trace_id
        mock_capture_metric.assert_not_called()
        # Custom span should still be created
        mock_custom_span.assert_called_once()


class TestCaptureFeedbackText:
    """Tests for capture_feedback_text tool."""

    @patch("github_standup_agent.tools.feedback.get_current_trace")
    @patch("github_standup_agent.tools.feedback.capture_ai_feedback")
    @patch("github_standup_agent.tools.feedback.custom_span")
    def test_capture_feedback_text(
        self,
        mock_custom_span,
        mock_capture_feedback,
        mock_get_trace,
        mock_context,
    ):
        """Test capturing text feedback."""
        from github_standup_agent.tools.feedback import capture_feedback_text

        mock_trace = MagicMock()
        mock_trace.trace_id = "test-trace-id-789"
        mock_get_trace.return_value = mock_trace

        mock_custom_span.return_value.__enter__ = MagicMock(return_value=None)
        mock_custom_span.return_value.__exit__ = MagicMock(return_value=None)

        result = invoke_tool(
            capture_feedback_text,
            mock_context,
            feedback="The formatting is too verbose, I prefer bullet points only",
        )

        assert "captured" in result.lower()
        mock_capture_feedback.assert_called_once_with(
            "test-trace-id-789",
            "The formatting is too verbose, I prefer bullet points only",
        )
        mock_custom_span.assert_called_once()

    @patch("github_standup_agent.tools.feedback.get_current_trace")
    @patch("github_standup_agent.tools.feedback.capture_ai_feedback")
    @patch("github_standup_agent.tools.feedback.custom_span")
    def test_no_trace_id_still_creates_span(
        self,
        mock_custom_span,
        mock_capture_feedback,
        mock_get_trace,
        mock_context,
    ):
        """Test that custom span is created even without trace."""
        from github_standup_agent.tools.feedback import capture_feedback_text

        mock_get_trace.return_value = None

        mock_custom_span.return_value.__enter__ = MagicMock(return_value=None)
        mock_custom_span.return_value.__exit__ = MagicMock(return_value=None)

        result = invoke_tool(
            capture_feedback_text,
            mock_context,
            feedback="Some feedback text",
        )

        assert "captured" in result.lower()
        mock_capture_feedback.assert_not_called()
        mock_custom_span.assert_called_once()


class TestInstrumentationFunctions:
    """Tests for the instrumentation capture functions."""

    @patch("github_standup_agent.instrumentation._posthog_client")
    @patch("github_standup_agent.instrumentation._instrumentation_enabled", True)
    @patch("github_standup_agent.instrumentation._current_distinct_id", "test-user")
    def test_capture_ai_metric(self, mock_client):
        """Test capture_ai_metric sends correct event."""
        from github_standup_agent.instrumentation import capture_ai_metric

        mock_client.capture = MagicMock()
        mock_client.flush = MagicMock()

        result = capture_ai_metric(
            trace_id="trace-123",
            metric_name="quality",
            metric_value="good",
            comment="Great standup!",
        )

        assert result is True
        mock_client.capture.assert_called_once()
        call_kwargs = mock_client.capture.call_args[1]
        assert call_kwargs["event"] == "$ai_metric"
        assert call_kwargs["properties"]["$ai_trace_id"] == "trace-123"
        assert call_kwargs["properties"]["$ai_metric_name"] == "quality"
        assert call_kwargs["properties"]["$ai_metric_value"] == "good"
        assert call_kwargs["properties"]["$ai_metric_comment"] == "Great standup!"

    @patch("github_standup_agent.instrumentation._posthog_client")
    @patch("github_standup_agent.instrumentation._instrumentation_enabled", True)
    @patch("github_standup_agent.instrumentation._current_distinct_id", "test-user")
    def test_capture_ai_feedback(self, mock_client):
        """Test capture_ai_feedback sends correct event."""
        from github_standup_agent.instrumentation import capture_ai_feedback

        mock_client.capture = MagicMock()
        mock_client.flush = MagicMock()

        result = capture_ai_feedback(
            trace_id="trace-456",
            feedback_text="Too verbose, prefer bullet points",
        )

        assert result is True
        mock_client.capture.assert_called_once()
        call_kwargs = mock_client.capture.call_args[1]
        assert call_kwargs["event"] == "$ai_feedback"
        assert call_kwargs["properties"]["$ai_trace_id"] == "trace-456"
        assert (
            call_kwargs["properties"]["$ai_feedback_text"]
            == "Too verbose, prefer bullet points"
        )

    @patch("github_standup_agent.instrumentation._posthog_client", None)
    @patch("github_standup_agent.instrumentation._instrumentation_enabled", False)
    def test_capture_ai_metric_disabled(self):
        """Test capture_ai_metric returns False when PostHog disabled."""
        from github_standup_agent.instrumentation import capture_ai_metric

        result = capture_ai_metric(
            trace_id="trace-123",
            metric_name="quality",
            metric_value="good",
        )

        assert result is False

    @patch("github_standup_agent.instrumentation._posthog_client", None)
    @patch("github_standup_agent.instrumentation._instrumentation_enabled", False)
    def test_capture_ai_feedback_disabled(self):
        """Test capture_ai_feedback returns False when PostHog disabled."""
        from github_standup_agent.instrumentation import capture_ai_feedback

        result = capture_ai_feedback(
            trace_id="trace-123",
            feedback_text="Some feedback",
        )

        assert result is False
