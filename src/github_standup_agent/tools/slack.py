"""Tool for posting standups to Slack."""

import os
from datetime import date
from typing import Annotated, Any

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext
from github_standup_agent.instrumentation import capture_event


def _get_slack_client() -> Any:
    """Get Slack WebClient, importing lazily to avoid requiring slack-sdk when not used."""
    try:
        from slack_sdk import WebClient

        return WebClient
    except ImportError:
        return None


def _find_latest_standup_thread(
    client: Any, channel: str, days_back: int = 7
) -> str | None:
    """Find the latest standup thread in the channel.

    Searches for recent messages that look like standup thread starters
    (e.g., messages containing "standup" in the first 7 days).

    Returns the thread_ts if found, None otherwise.
    """
    import time

    # Calculate timestamp for days_back
    oldest = str(int(time.time()) - (days_back * 24 * 60 * 60))

    try:
        response = client.conversations_history(
            channel=channel,
            oldest=oldest,
            limit=100,
        )

        if not response["ok"]:
            return None

        messages = response.get("messages", [])

        # Look for messages that look like standup threads
        # (containing "standup" in the text, case-insensitive)
        for msg in messages:
            text = msg.get("text", "").lower()
            if "standup" in text:
                # Return the thread_ts (or ts if it's not a thread)
                thread_ts: str | None = msg.get("thread_ts") or msg.get("ts")
                return thread_ts

    except Exception:
        # If we can't find a thread, that's okay - we'll post as a new message
        pass

    return None


@function_tool
def post_standup_to_slack(
    ctx: RunContextWrapper[StandupContext],
    summary: Annotated[str | None, "Summary to post. Defaults to current standup."] = None,
    channel: Annotated[str | None, "Slack channel ID. Defaults to configured channel."] = None,
    thread_ts: Annotated[
        str | None, "Thread timestamp to reply to. If 'auto', finds latest standup thread."
    ] = "auto",
    find_thread_days: Annotated[
        int, "Days to search back for standup thread when thread_ts='auto'"
    ] = 7,
) -> str:
    """
    Post the current standup to Slack.

    Posts to a Slack channel, optionally as a reply to an existing standup thread.
    Requires STANDUP_SLACK_BOT_TOKEN and STANDUP_SLACK_CHANNEL to be configured.
    """
    content = summary or ctx.context.current_standup

    if not content:
        return "No standup to post. Generate one first."

    # Get Slack configuration
    bot_token = os.getenv("STANDUP_SLACK_BOT_TOKEN")
    default_channel = os.getenv("STANDUP_SLACK_CHANNEL")

    if not bot_token:
        return (
            "Slack not configured. Set STANDUP_SLACK_BOT_TOKEN environment variable. "
            "Create a Slack app at https://api.slack.com/apps with chat:write and "
            "channels:history scopes."
        )

    target_channel = channel or default_channel
    if not target_channel:
        return (
            "No Slack channel specified. Set STANDUP_SLACK_CHANNEL environment variable "
            "or pass channel parameter."
        )

    # Import Slack SDK
    WebClient = _get_slack_client()
    if WebClient is None:
        return (
            "Slack SDK not installed. Install with: uv pip install slack-sdk\n"
            "Or add 'slack' extra: uv pip install github-standup-agent[slack]"
        )

    try:
        client = WebClient(token=bot_token)

        # Determine thread_ts
        actual_thread_ts = None
        if thread_ts == "auto":
            # Try to find the latest standup thread
            actual_thread_ts = _find_latest_standup_thread(
                client, target_channel, days_back=find_thread_days
            )
        elif thread_ts:
            actual_thread_ts = thread_ts

        # Format the message with a header
        username = ctx.context.github_username or "unknown"
        today = date.today().strftime("%Y-%m-%d")
        formatted_message = f"*Standup from {username} - {today}*\n\n{content}"

        # Post the message
        response = client.chat_postMessage(
            channel=target_channel,
            text=formatted_message,
            thread_ts=actual_thread_ts,
            unfurl_links=False,
            unfurl_media=False,
        )

        if not response["ok"]:
            return f"Failed to post to Slack: {response.get('error', 'Unknown error')}"

        # Build success message
        thread_info = ""
        if actual_thread_ts:
            thread_info = " (in thread)"
        elif thread_ts == "auto":
            thread_info = " (no existing thread found, posted as new message)"

        # Emit PostHog event
        capture_event(
            event_name="standup_posted_to_slack",
            properties={
                "github_username": ctx.context.github_username,
                "channel": target_channel,
                "in_thread": bool(actual_thread_ts),
                "date": today,
                "summary_length": len(content),
            },
        )

        return f"✅ Standup posted to Slack channel {target_channel}{thread_info}"

    except Exception as e:
        error_msg = str(e)
        if "not_in_channel" in error_msg:
            return (
                f"Bot is not in channel {target_channel}. "
                "Invite the bot to the channel first with /invite @your-bot-name"
            )
        if "channel_not_found" in error_msg:
            return (
                f"Channel {target_channel} not found. "
                "Make sure you're using the channel ID (e.g., C01234567), not the name."
            )
        if "invalid_auth" in error_msg:
            return "Invalid Slack token. Check your STANDUP_SLACK_BOT_TOKEN."
        return f"Failed to post to Slack: {error_msg}"
