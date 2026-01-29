#!/usr/bin/env python3
"""
Manually run any standup tool and see exactly what the agent sees.

Usage:
    uv run scripts/run_tool.py list_prs
    uv run scripts/run_tool.py list_prs --filter_by=reviewed --days_back=7
    uv run scripts/run_tool.py get_pr_details --repo=PostHog/posthog --number=123
    uv run scripts/run_tool.py list_reviews --username=my-user
    uv run scripts/run_tool.py --list  # List all available tools

This creates a mock RunContextWrapper and calls the tool directly,
printing both the string output (what the agent sees) and optionally
the raw data stored in context.
"""

import argparse
import asyncio
import json
import sys
from dataclasses import fields
from typing import Any

from agents import RunContextWrapper, Usage
from agents.tool import ToolContext

from github_standup_agent.config import StandupConfig, get_github_username
from github_standup_agent.context import StandupContext

# Import all tools
from github_standup_agent.tools.github.github_prs import list_prs, get_pr_details
from github_standup_agent.tools.github.github_issues import list_issues, get_issue_details
from github_standup_agent.tools.github.github_reviews import list_reviews
from github_standup_agent.tools.github.github_commits import list_commits
from github_standup_agent.tools.github.github_comments import list_comments
from github_standup_agent.tools.github.github_activity import get_activity_summary
from github_standup_agent.tools.github.github_events import get_activity_feed
from github_standup_agent.tools.github.github_assigned import list_assigned_items
from github_standup_agent.tools.history import save_standup_to_file
from github_standup_agent.tools.slack import get_team_slack_standups


# Registry of all tools
TOOLS = {
    "list_prs": list_prs,
    "get_pr_details": get_pr_details,
    "list_issues": list_issues,
    "get_issue_details": get_issue_details,
    "list_reviews": list_reviews,
    "list_commits": list_commits,
    "list_comments": list_comments,
    "get_activity_summary": get_activity_summary,
    "get_activity_feed": get_activity_feed,
    "list_assigned_items": list_assigned_items,
    "save_standup_to_file": save_standup_to_file,
    "get_team_slack_standups": get_team_slack_standups,
}


def list_tools():
    """Print all available tools with their signatures."""
    print("Available tools:\n")
    for name, tool in TOOLS.items():
        # FunctionTool has .name, .description, .params_json_schema
        print(f"  {tool.name}")
        # Print description (first line only for brevity)
        desc_lines = tool.description.strip().split("\n")
        print(f"    {desc_lines[0]}")

        # Print parameters from JSON schema
        schema = tool.params_json_schema
        props = schema.get("properties", {})
        if props:
            print("    Parameters:")
            for pname, pinfo in props.items():
                desc = pinfo.get("description", "")[:50]
                default = pinfo.get("default", "")
                default_str = f" (default: {default})" if default != "" else ""
                print(f"      --{pname}: {desc}{default_str}")
        print()


def create_context() -> RunContextWrapper[StandupContext]:
    """Create a context wrapper for running tools."""
    config = StandupConfig.load()
    username = config.github_username or get_github_username()

    context = StandupContext(
        config=config,
        github_username=username,
        days_back=config.default_days_back,
    )

    # Create the wrapper - RunContextWrapper expects the context directly
    wrapper = RunContextWrapper(context=context)
    return wrapper


def parse_value(value: str) -> Any:
    """Parse a string value to appropriate Python type."""
    # Try int
    try:
        return int(value)
    except ValueError:
        pass

    # Try bool
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False

    # Try JSON (for lists/dicts)
    if value.startswith("[") or value.startswith("{"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass

    # Return as string
    return value


def run_tool(tool_name: str, kwargs: dict[str, Any], show_context: bool = False):
    """Run a tool and display results."""
    if tool_name not in TOOLS:
        print(f"Error: Unknown tool '{tool_name}'")
        print(f"Available tools: {', '.join(TOOLS.keys())}")
        sys.exit(1)

    tool = TOOLS[tool_name]
    run_ctx = create_context()

    print(f"Running: {tool_name}")
    print(f"Username: {run_ctx.context.github_username}")
    if kwargs:
        print(f"Args: {kwargs}")
    print("-" * 60)
    print()

    # Create a ToolContext for invoking the tool
    # The tool expects JSON-serialized arguments via on_invoke_tool
    tool_ctx = ToolContext(
        context=run_ctx.context,
        usage=Usage(),
        tool_name=tool_name,
        tool_call_id="manual-test",
        tool_arguments=json.dumps(kwargs),
    )

    # Call the tool via on_invoke_tool
    result = tool.on_invoke_tool(tool_ctx, json.dumps(kwargs))

    # Handle async tools
    if asyncio.iscoroutine(result):
        result = asyncio.run(result)

    # Update run_ctx with any changes to context
    run_ctx = RunContextWrapper(context=tool_ctx.context)

    print("=== AGENT SEES (string output) ===")
    print(result)
    print()

    if show_context:
        print("=== RAW CONTEXT DATA ===")
        # Show what got stored in context
        context_data = {}
        for field in fields(run_ctx.context):
            name = field.name
            if name == "config":
                continue
            value = getattr(run_ctx.context, name)
            if value and value != field.default:
                # For lists/dicts, show count and sample
                if isinstance(value, list) and len(value) > 0:
                    context_data[name] = {
                        "count": len(value),
                        "sample": value[0] if value else None,
                    }
                elif isinstance(value, dict) and len(value) > 0:
                    context_data[name] = {
                        "count": len(value),
                        "keys": list(value.keys())[:5],
                    }
                elif value is not None:
                    context_data[name] = value

        if context_data:
            print(json.dumps(context_data, indent=2, default=str))
        else:
            print("(no data stored in context)")


def main():
    parser = argparse.ArgumentParser(
        description="Run standup tools manually and see agent output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("tool", nargs="?", help="Tool name to run")
    parser.add_argument("--list", "-l", action="store_true", help="List available tools")
    parser.add_argument(
        "--show-context", "-c", action="store_true",
        help="Show raw data stored in context"
    )

    # Parse known args to allow arbitrary --key=value pairs
    args, remaining = parser.parse_known_args()

    if args.list:
        list_tools()
        return

    if not args.tool:
        parser.print_help()
        return

    # Parse remaining args as tool kwargs
    kwargs = {}
    for arg in remaining:
        if arg.startswith("--"):
            if "=" in arg:
                key, value = arg[2:].split("=", 1)
                kwargs[key] = parse_value(value)
            else:
                # Boolean flag
                kwargs[arg[2:]] = True

    run_tool(args.tool, kwargs, show_context=args.show_context)


if __name__ == "__main__":
    main()
