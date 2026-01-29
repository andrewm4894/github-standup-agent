"""Tool for copying content to clipboard."""

from typing import Annotated

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext


@function_tool
def copy_to_clipboard(
    ctx: RunContextWrapper[StandupContext],
    text: Annotated[str | None, "Text to copy. Defaults to current standup."] = None,
) -> str:
    """
    Copy text to the system clipboard.

    If no text is provided, copies the current standup summary.
    """
    import pyperclip

    content = text or ctx.context.current_standup

    if not content:
        return "No content to copy. Generate a standup first."

    try:
        pyperclip.copy(content)
        return "Copied to clipboard."
    except pyperclip.PyperclipException as e:
        return f"Failed to copy to clipboard: {e}"
