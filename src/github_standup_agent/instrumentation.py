"""Optional PostHog instrumentation for agent tracing."""

import os
from typing import Any

_posthog_client: Any = None
_instrumentation_enabled = False
_current_distinct_id: str | None = None

# Check for debug mode
POSTHOG_DEBUG = os.getenv("POSTHOG_DEBUG", "false").lower() in ("true", "1", "yes")


def setup_posthog(distinct_id: str | None = None) -> bool:
    """
    Initialize PostHog instrumentation if configured via environment.

    Environment variables:
        POSTHOG_API_KEY: PostHog project API key (required to enable)
        POSTHOG_HOST: PostHog host (default: https://us.posthog.com)
        POSTHOG_DISTINCT_ID: User identifier for traces

    Args:
        distinct_id: Override distinct_id (e.g., from github_username)

    Returns:
        True if instrumentation was enabled, False otherwise.
    """
    global _posthog_client, _instrumentation_enabled, _current_distinct_id

    api_key = os.getenv("POSTHOG_API_KEY")
    if not api_key:
        return False

    host = os.getenv("POSTHOG_HOST", "https://us.posthog.com")
    user_id = distinct_id or os.getenv("POSTHOG_DISTINCT_ID", "standup-agent-user")

    try:
        from posthog import Posthog
        from posthog.ai.openai_agents import instrument

        if POSTHOG_DEBUG:
            print(f"[PostHog] Initializing with host={host}, distinct_id={user_id}")

        _posthog_client = Posthog(api_key, host=host, debug=POSTHOG_DEBUG)

        processor = instrument(
            client=_posthog_client,
            distinct_id=user_id,
            privacy_mode=False,
            properties={"app": "github-standup-agent"},
        )

        if POSTHOG_DEBUG:
            print(f"[PostHog] Instrumentation enabled, processor={processor}")

        _instrumentation_enabled = True
        _current_distinct_id = user_id
        return True

    except ImportError:
        # PostHog not installed - silently skip
        return False
    except Exception as e:
        print(f"[PostHog] Warning: Failed to initialize instrumentation: {e}")
        return False


def shutdown_posthog() -> None:
    """Flush and shutdown PostHog client."""
    global _posthog_client
    if _posthog_client:
        try:
            _posthog_client.flush()
            _posthog_client.shutdown()
        except Exception:
            pass
        _posthog_client = None


def is_enabled() -> bool:
    """Check if PostHog instrumentation is active."""
    return _instrumentation_enabled


def get_client() -> Any:
    """Get the PostHog client instance (if initialized)."""
    return _posthog_client


def get_distinct_id() -> str | None:
    """Get the current distinct_id used for PostHog."""
    return _current_distinct_id


def capture_event(
    event_name: str,
    properties: dict[str, Any] | None = None,
    distinct_id: str | None = None,
) -> bool:
    """
    Capture a custom event to PostHog.

    Args:
        event_name: Name of the event (e.g., "standup_saved")
        properties: Event properties/metadata
        distinct_id: Override distinct_id (defaults to configured user)

    Returns:
        True if event was captured, False if PostHog not enabled.
    """
    if not _posthog_client or not _instrumentation_enabled:
        return False

    user_id = distinct_id or _current_distinct_id or "standup-agent-user"

    try:
        _posthog_client.capture(
            distinct_id=user_id,
            event=event_name,
            properties=properties or {},
        )

        # Flush immediately to ensure event is sent
        _posthog_client.flush()

        if POSTHOG_DEBUG:
            print(f"[PostHog] Captured event: {event_name}")

        return True
    except Exception as e:
        if POSTHOG_DEBUG:
            print(f"[PostHog] Failed to capture event: {e}")
        return False


def capture_ai_metric(
    trace_id: str,
    metric_name: str,
    metric_value: str,
    comment: str | None = None,
    distinct_id: str | None = None,
) -> bool:
    """
    Capture an AI metric event (e.g., thumbs up/down quality rating).

    Args:
        trace_id: The trace ID to link this metric to
        metric_name: Name of the metric (e.g., "quality")
        metric_value: Value of the metric (e.g., "good", "bad")
        comment: Optional comment explaining the rating
        distinct_id: Override distinct_id (defaults to configured user)

    Returns:
        True if event was captured, False if PostHog not enabled.
    """
    properties: dict[str, Any] = {
        "$ai_trace_id": trace_id,
        "$ai_metric_name": metric_name,
        "$ai_metric_value": metric_value,
    }
    if comment:
        properties["$ai_metric_comment"] = comment

    return capture_event(
        event_name="$ai_metric",
        properties=properties,
        distinct_id=distinct_id,
    )


def capture_ai_feedback(
    trace_id: str,
    feedback_text: str,
    distinct_id: str | None = None,
) -> bool:
    """
    Capture AI feedback text linked to a trace.

    Args:
        trace_id: The trace ID to link this feedback to
        feedback_text: The feedback text from the user
        distinct_id: Override distinct_id (defaults to configured user)

    Returns:
        True if event was captured, False if PostHog not enabled.
    """
    return capture_event(
        event_name="$ai_feedback",
        properties={
            "$ai_trace_id": trace_id,
            "$ai_feedback_text": feedback_text,
        },
        distinct_id=distinct_id,
    )
