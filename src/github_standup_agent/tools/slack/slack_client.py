"""Slack client utility for standup agent."""

from functools import lru_cache
from typing import Any, cast

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackClientError(Exception):
    """Error communicating with Slack API."""

    pass


@lru_cache(maxsize=1)
def get_slack_client(token: str) -> WebClient:
    """Get or create a Slack WebClient."""
    return WebClient(token=token)


def resolve_channel_id(client: WebClient, channel_name: str) -> str:
    """Resolve a channel name to its ID.

    Args:
        client: Slack WebClient
        channel_name: Channel name (with or without #) or channel ID

    Returns:
        Channel ID

    Raises:
        SlackClientError: If channel not found or API error
    """
    # If already an ID (starts with C or G), return it
    if channel_name.startswith(("C", "G")):
        return channel_name

    # Strip leading # if present
    channel_name = channel_name.lstrip("#")

    try:
        # Paginate through channels to find the one we want
        cursor: str | None = None
        while True:
            result = client.conversations_list(
                types="public_channel,private_channel",
                cursor=cursor,
                limit=200,
            )

            channels = cast(list[dict[str, Any]], result.get("channels", []))
            for channel in channels:
                if channel["name"] == channel_name:
                    return str(channel["id"])

            metadata = cast(dict[str, Any], result.get("response_metadata", {}))
            cursor = metadata.get("next_cursor")
            if not cursor:
                break

        raise SlackClientError(f"Channel '{channel_name}' not found")

    except SlackApiError as e:
        raise SlackClientError(f"Slack API error: {e.response['error']}") from e


def get_channel_messages(
    client: WebClient,
    channel_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Get recent messages from a channel.

    Args:
        client: Slack WebClient
        channel_id: Channel ID
        limit: Maximum messages to fetch

    Returns:
        List of message dictionaries
    """
    try:
        result = client.conversations_history(
            channel=channel_id,
            limit=limit,
        )
        return cast(list[dict[str, Any]], result.get("messages", []))
    except SlackApiError as e:
        raise SlackClientError(f"Slack API error: {e.response['error']}") from e


def get_thread_replies(
    client: WebClient,
    channel_id: str,
    thread_ts: str,
) -> list[dict[str, Any]]:
    """Get replies in a thread.

    Args:
        client: Slack WebClient
        channel_id: Channel ID
        thread_ts: Thread parent timestamp

    Returns:
        List of reply messages (excluding parent)
    """
    try:
        result = client.conversations_replies(
            channel=channel_id,
            ts=thread_ts,
        )
        messages: list[dict[str, Any]] = cast(list[dict[str, Any]], result.get("messages", []))
        # First message is the parent, skip it
        return messages[1:] if len(messages) > 1 else []
    except SlackApiError as e:
        raise SlackClientError(f"Slack API error: {e.response['error']}") from e


# Cache for user display names (user_id -> display_name)
_user_name_cache: dict[str, str] = {}
_users_read_available: bool | None = None  # None = not checked yet


def get_user_display_name(client: WebClient, user_id: str) -> str:
    """Get display name for a Slack user ID.

    Args:
        client: Slack WebClient
        user_id: Slack user ID (e.g., U12345)

    Returns:
        Display name or real name, falls back to user ID if not found

    Note: Requires users:read scope. Falls back to user ID if scope not available.
    """
    global _users_read_available

    # Check cache first
    if user_id in _user_name_cache:
        return _user_name_cache[user_id]

    # If we already know users:read isn't available, skip API call
    if _users_read_available is False:
        return user_id

    try:
        result = client.users_info(user=user_id)
        _users_read_available = True
        user = result.get("user", {})
        profile = user.get("profile", {})
        # Prefer display_name, fall back to real_name, then user ID
        name = (
            profile.get("display_name")
            or profile.get("real_name")
            or user.get("name")
            or user_id
        )
        _user_name_cache[user_id] = name
        return name
    except SlackApiError as e:
        # Check if it's a scope issue
        if "missing_scope" in str(e) or "users:read" in str(e):
            _users_read_available = False
        _user_name_cache[user_id] = user_id
        return user_id


def post_to_thread(
    client: WebClient,
    channel_id: str,
    thread_ts: str,
    text: str,
    username: str | None = None,
) -> dict[str, Any]:
    """Post a message as a reply in a thread.

    Args:
        client: Slack WebClient
        channel_id: Channel ID
        thread_ts: Thread parent timestamp
        text: Message text
        username: Optional custom display name (requires chat:write.customize scope)

    Returns:
        API response
    """
    try:
        kwargs: dict[str, Any] = {
            "channel": channel_id,
            "thread_ts": thread_ts,
            "text": text,
            "unfurl_links": False,
            "unfurl_media": False,
        }
        if username:
            kwargs["username"] = username

        result = client.chat_postMessage(**kwargs)
        return {"ok": result["ok"], "ts": result["ts"], "channel": result["channel"]}
    except SlackApiError as e:
        raise SlackClientError(f"Slack API error: {e.response['error']}") from e
