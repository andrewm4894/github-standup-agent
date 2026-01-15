"""Optional PostHog instrumentation for agent tracing."""

import os
from typing import Any

_posthog_client: Any = None
_instrumentation_enabled = False

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
    global _posthog_client, _instrumentation_enabled

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
