"""Shared fixtures and helpers for tool tests."""

import asyncio
import json
from typing import Any

from agents.tool_context import ToolContext
from agents.usage import Usage

from github_standup_agent.context import StandupContext


def invoke_tool(tool, context: StandupContext, **kwargs) -> str:
    """Helper to invoke a FunctionTool synchronously for testing.

    Args:
        tool: The FunctionTool to invoke
        context: The StandupContext
        **kwargs: Arguments to pass to the tool

    Returns:
        The tool's string output
    """
    tool_ctx = ToolContext(
        context=context,
        usage=Usage(),
        tool_name=tool.name,
        tool_call_id="test-call-id",
        tool_arguments=json.dumps(kwargs),
    )

    return asyncio.run(tool.on_invoke_tool(tool_ctx, json.dumps(kwargs)))
