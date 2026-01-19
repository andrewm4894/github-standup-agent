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
        messages: list[dict[str, Any]] = cast(
            list[dict[str, Any]], result.get("messages", [])
        )
        # First message is the parent, skip it
        return messages[1:] if len(messages) > 1 else []
    except SlackApiError as e:
        raise SlackClientError(f"Slack API error: {e.response['error']}") from e


def post_to_thread(
    client: WebClient,
    channel_id: str,
    thread_ts: str,
    text: str,
) -> dict[str, Any]:
    """Post a message as a reply in a thread.

    Args:
        client: Slack WebClient
        channel_id: Channel ID
        thread_ts: Thread parent timestamp
        text: Message text

    Returns:
        API response
    """
    try:
        result = client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=text,
        )
        return {"ok": result["ok"], "ts": result["ts"], "channel": result["channel"]}
    except SlackApiError as e:
        raise SlackClientError(f"Slack API error: {e.response['error']}") from e
