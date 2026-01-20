"""Tool for publishing standup to Slack."""

from typing import Annotated

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext
from github_standup_agent.tools.slack.slack_client import (
    SlackClientError,
    get_slack_client,
    post_to_thread,
    resolve_channel_id,
)


@function_tool
def publish_standup_to_slack(
    ctx: RunContextWrapper[StandupContext],
    standup_text: Annotated[
        str | None, "Standup text to publish. Defaults to current standup."
    ] = None,
    confirmed: Annotated[bool, "User has confirmed they want to publish"] = False,
) -> str:
    """
    Publish the standup to Slack as a reply in today's standup thread.

    IMPORTANT: This requires explicit user confirmation before posting.
    If confirmed=False, this will show a preview and ask for confirmation.
    """
    config = ctx.context.config

    # Check if Slack is configured
    token = config.get_slack_token()
    if not token:
        return "Slack integration not configured. Set STANDUP_SLACK_BOT_TOKEN to enable."

    if not config.slack_channel:
        return "Slack channel not configured. Set slack_channel in config."

    # Get the standup content
    content = standup_text or ctx.context.current_standup
    if not content:
        return "No standup to publish. Generate one first."

    # Check for thread to reply to
    thread_ts = ctx.context.slack_thread_ts
    if not thread_ts:
        return (
            "No standup thread found to reply to. "
            "Make sure there's a recent standup thread in the channel, "
            "or run get_team_slack_standups first to find it."
        )

    # SAFETY CHECK: Require explicit confirmation
    if not confirmed and not ctx.context.slack_publish_confirmed:
        # Stage the content for publishing (preserves it during confirmation flow)
        ctx.context.slack_standup_to_publish = content

        # Return a preview for confirmation
        preview_lines = [
            "**Ready to publish to Slack:**\n",
            f"Channel: #{config.slack_channel}",
            f"Thread: {thread_ts}",
            "\n**Content preview:**\n",
            content[:500] + ("..." if len(content) > 500 else ""),
            "\n\n**To confirm, say 'yes, publish to slack' or 'confirm publish'**",
        ]
        return "\n".join(preview_lines)

    # Use staged content if available (from preview step), otherwise fall back to current
    content = ctx.context.slack_standup_to_publish or content

    try:
        client = get_slack_client(token)

        # Ensure we have channel ID
        channel_id = ctx.context.slack_channel_id
        if not channel_id:
            channel_id = resolve_channel_id(client, config.slack_channel)
            ctx.context.slack_channel_id = channel_id

        # Build display name from github username (requires chat:write.customize scope)
        display_name = None
        if ctx.context.github_username:
            display_name = f"{ctx.context.github_username}'s standup"

        # Post to thread
        post_to_thread(client, channel_id, thread_ts, content, username=display_name)

        # Reset confirmation flag and staged content
        ctx.context.slack_publish_confirmed = False
        ctx.context.slack_standup_to_publish = None

        return f"Posted standup to Slack in #{config.slack_channel} (thread: {thread_ts})"

    except SlackClientError as e:
        return f"Error publishing to Slack: {e}"


@function_tool
def confirm_slack_publish(
    ctx: RunContextWrapper[StandupContext],
) -> str:
    """
    Confirm that the user wants to publish their standup to Slack.

    Call this when the user explicitly confirms they want to publish.
    """
    ctx.context.slack_publish_confirmed = True
    return "Confirmation received. You can now publish to Slack."
