"""Tools for saving standups to files."""

from pathlib import Path
from typing import Annotated

from agents import RunContextWrapper, function_tool

from github_standup_agent.context import StandupContext


@function_tool
def save_standup_to_file(
    ctx: RunContextWrapper[StandupContext],
    summary: Annotated[str | None, "Summary to save. Defaults to current standup."] = None,
    filename: Annotated[str, "Filename to save to"] = "standup.md",
) -> str:
    """
    Save the current standup to a markdown file in the current directory.

    This creates a standup.md file that's easy to copy/paste from.
    """
    content = summary or ctx.context.current_standup

    if not content:
        return "No standup to save. Generate one first."

    try:
        filepath = Path(filename)
        filepath.write_text(content)
        return f"Standup saved to {filepath.absolute()}"
    except Exception as e:
        return f"Failed to save standup to file: {e}"
