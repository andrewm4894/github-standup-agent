"""Tool for fetching team standups from Slack."""

from datetime import datetime, timedelta
from typing import Annotated, Any

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext
from github_standup_agent.tools.slack.slack_client import (
    SlackClientError,
    get_channel_messages,
    get_slack_client,
    get_thread_replies,
    get_user_display_name,
    resolve_channel_id,
)


@function_tool
def get_team_slack_standups(
    ctx: RunContextWrapper[StandupContext],
    days_back: Annotated[int, "Number of days to look back for standups"] = 1,
) -> str:
    """
    Fetch recent team standup messages from the configured Slack channel.

    Looks for threads that start with "Standup" and collects replies from team members.
    This provides context about what the team is working on.
    """
    config = ctx.context.config

    # Check if Slack is configured
    token = config.get_slack_token()
    if not token:
        return "Slack integration not configured. Set STANDUP_SLACK_BOT_TOKEN to enable."

    if not config.slack_channel:
        return (
            "Slack channel not configured. "
            "Set slack_channel in config or STANDUP_SLACK_CHANNEL env var."
        )

    try:
        client = get_slack_client(token)

        # Resolve channel name to ID
        channel_id = resolve_channel_id(client, config.slack_channel)
        ctx.context.slack_channel_id = channel_id

        # Get recent messages
        messages = get_channel_messages(client, channel_id, limit=100)

        # Calculate cutoff timestamp
        cutoff = datetime.now() - timedelta(days=days_back)
        cutoff_ts = cutoff.timestamp()

        # Find standup threads
        standup_threads: list[dict[str, Any]] = []
        thread_prefix = ":robot_face: Standup :thread:"

        for msg in messages:
            msg_ts = float(msg.get("ts", 0))

            # Skip messages older than cutoff
            if msg_ts < cutoff_ts:
                continue

            # Check if this is a standup thread starter
            # Thread starters have thread_ts == ts (they are the parent)
            text = msg.get("text", "")
            is_thread_parent = msg.get("thread_ts") == msg.get("ts") or "thread_ts" not in msg

            if text.startswith(thread_prefix) and is_thread_parent:
                # This is a standup thread parent
                thread_ts = msg["ts"]

                # Store the most recent thread for potential publishing
                if not ctx.context.slack_thread_ts:
                    ctx.context.slack_thread_ts = thread_ts

                # Get replies in this thread
                replies = get_thread_replies(client, channel_id, thread_ts)

                thread_date = datetime.fromtimestamp(msg_ts).strftime("%Y-%m-%d")
                thread_data: dict[str, Any] = {
                    "date": thread_date,
                    "thread_ts": thread_ts,
                    "parent_text": text,
                    "replies": [],
                }

                for reply in replies:
                    user_id = reply.get("user", "unknown")
                    # Resolve user ID to display name
                    user_name = (
                        get_user_display_name(client, user_id)
                        if user_id != "unknown"
                        else "unknown"
                    )
                    thread_data["replies"].append(
                        {
                            "user_id": user_id,
                            "user_name": user_name,
                            "text": reply.get("text", ""),
                            "timestamp": reply.get("ts"),
                        }
                    )

                standup_threads.append(thread_data)

        # Store in context
        ctx.context.collected_slack_standups = standup_threads

        if not standup_threads:
            return (
                f"No standup threads found in #{config.slack_channel} "
                f"in the last {days_back} day(s)."
            )

        # Check if we got real names or just IDs
        has_real_names = any(
            reply.get("user_name", "").startswith("U") is False
            for thread in standup_threads
            for reply in thread.get("replies", [])
            if reply.get("user_name")
        )

        # Format output for the agent
        lines = [f"Found {len(standup_threads)} standup thread(s) from Slack:"]
        if not has_real_names and standup_threads:
            lines.append("(Note: Add users:read scope to Slack bot to show display names)")

        for thread in standup_threads:
            lines.append(f"\n--- {thread['date']} ---")
            parent_preview = thread["parent_text"][:100]
            if len(thread["parent_text"]) > 100:
                parent_preview += "..."
            lines.append(f"Thread: {parent_preview}")

            if thread["replies"]:
                lines.append(f"  {len(thread['replies'])} team member standup(s):")
                for reply in thread["replies"][:10]:  # Limit to avoid huge output
                    user_name = reply.get("user_name", "unknown")
                    text = reply["text"]
                    # Truncate long standups
                    if len(text) > 500:
                        text = text[:500] + "..."
                    lines.append(f"\n  [@{user_name}]")
                    lines.append(f"  {text}")
            else:
                lines.append("  (No replies yet)")

        return "\n".join(lines)

    except SlackClientError as e:
        return f"Error fetching Slack standups: {e}"
