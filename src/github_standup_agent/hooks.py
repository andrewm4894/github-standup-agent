"""Hooks for logging and observability."""

import time
from typing import Any

from agents import Agent, AgentHooks, RunContextWrapper, RunHooks, Tool
from rich.console import Console

from github_standup_agent.context import StandupContext

console = Console()


class StandupRunHooks(RunHooks[StandupContext]):
    """Hooks for the entire run lifecycle."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.start_time: float | None = None

    async def on_run_start(
        self,
        context: RunContextWrapper[StandupContext],
        agent: Agent[StandupContext],
    ) -> None:
        """Called when a run starts."""
        self.start_time = time.time()
        if self.verbose:
            console.print(f"[dim]Starting run with agent: {agent.name}[/dim]")

    async def on_run_end(
        self,
        context: RunContextWrapper[StandupContext],
        agent: Agent[StandupContext],
        output: Any,
    ) -> None:
        """Called when a run completes."""
        if self.start_time and self.verbose:
            elapsed = time.time() - self.start_time
            console.print(f"[dim]Run completed in {elapsed:.2f}s[/dim]")


class StandupAgentHooks(AgentHooks[StandupContext]):
    """Hooks for individual agent operations."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    async def on_start(
        self,
        context: RunContextWrapper[StandupContext],
        agent: Agent[StandupContext],
    ) -> None:
        """Called when an agent starts processing."""
        if self.verbose:
            console.print(f"[cyan]Agent [{agent.name}] starting...[/cyan]")

    async def on_end(
        self,
        context: RunContextWrapper[StandupContext],
        agent: Agent[StandupContext],
        output: Any,
    ) -> None:
        """Called when an agent finishes processing."""
        if self.verbose:
            console.print(f"[cyan]Agent [{agent.name}] finished[/cyan]")

    async def on_handoff(
        self,
        context: RunContextWrapper[StandupContext],
        from_agent: Agent[StandupContext],
        to_agent: Agent[StandupContext],
    ) -> None:
        """Called when one agent hands off to another."""
        if self.verbose:
            console.print(f"[yellow]Handoff: {from_agent.name} → {to_agent.name}[/yellow]")

    async def on_tool_start(
        self,
        context: RunContextWrapper[StandupContext],
        agent: Agent[StandupContext],
        tool: Tool,
    ) -> None:
        """Called when a tool is about to be invoked."""
        if self.verbose:
            console.print(f"[dim]  Tool: {tool.name}...[/dim]")

    async def on_tool_end(
        self,
        context: RunContextWrapper[StandupContext],
        agent: Agent[StandupContext],
        tool: Tool,
        result: str,
    ) -> None:
        """Called when a tool completes."""
        if self.verbose:
            preview = result[:100] + "..." if len(result) > 100 else result
            console.print(f"[dim]  Tool {tool.name} returned: {preview}[/dim]")
