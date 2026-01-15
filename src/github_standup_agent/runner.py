"""Runner module for executing the standup agent workflow."""

import os
from typing import Any

from agents import RunConfig, Runner
from rich.console import Console
from rich.prompt import Prompt

from github_standup_agent.agents.coordinator import create_coordinator_agent
from github_standup_agent.config import StandupConfig
from github_standup_agent.context import StandupContext
from github_standup_agent.hooks import StandupRunHooks

console = Console()


async def run_standup_generation(
    config: StandupConfig,
    days_back: int = 1,
    with_history: bool = False,
    github_username: str | None = None,
    stream: bool = False,
    verbose: bool = False,
) -> str:
    """
    Run the standup generation workflow.

    Args:
        config: The standup configuration
        days_back: Number of days to look back for activity
        with_history: Whether to include context from recent standups
        github_username: GitHub username
        stream: Whether to stream output
        verbose: Whether to show verbose output

    Returns:
        The generated standup summary
    """
    # Set up OpenAI API key
    api_key = config.get_api_key()
    os.environ["OPENAI_API_KEY"] = api_key

    # Create context
    context = StandupContext(
        config=config,
        days_back=days_back,
        with_history=with_history,
        github_username=github_username,
    )

    # Create the coordinator agent with configured models
    agent = create_coordinator_agent(
        model=config.coordinator_model,
        data_gatherer_model=config.data_gatherer_model,
        summarizer_model=config.summarizer_model,
    )

    # Build the prompt
    prompt = f"""Generate a standup summary for the last {days_back} day(s).

First, gather all my GitHub activity data, then create a concise standup summary.

{"Check my recent standups to maintain continuity." if with_history else ""}

After generating the summary, save it to history.
"""

    # Create hooks
    run_hooks = StandupRunHooks(verbose=verbose)

    # Run configuration
    run_config = RunConfig(
        workflow_name="standup_generation",
        trace_include_sensitive_data=False,
    )

    if stream:
        # Streaming mode
        result_text = ""
        stream_result = Runner.run_streamed(
            agent,
            input=prompt,
            context=context,
            run_config=run_config,
            hooks=run_hooks,
        )
        async for event in stream_result.stream_events():
            if hasattr(event, "data") and hasattr(event.data, "delta"):
                console.print(event.data.delta, end="")
                result_text += event.data.delta

        # Get final output
        return context.current_standup or result_text
    else:
        # Non-streaming mode
        result = await Runner.run(
            agent,
            input=prompt,
            context=context,
            run_config=run_config,
            hooks=run_hooks,
        )

        # Extract the summary from the result
        output = result.final_output

        # If structured output, extract the formatted summary
        if hasattr(output, "formatted_summary"):
            return str(output.formatted_summary)

        # Store in context and return
        output_str = str(output)
        context.current_standup = output_str
        return output_str


async def run_interactive_chat(
    config: StandupConfig,
    days_back: int = 1,
    github_username: str | None = None,
) -> None:
    """
    Run an interactive chat session for refining standups.

    Args:
        config: The standup configuration
        days_back: Number of days to look back for activity
        github_username: GitHub username
    """
    # Set up OpenAI API key
    api_key = config.get_api_key()
    os.environ["OPENAI_API_KEY"] = api_key

    # Create context
    context = StandupContext(
        config=config,
        days_back=days_back,
        with_history=True,  # Always use history in chat mode
        github_username=github_username,
    )

    # Create the coordinator agent
    agent = create_coordinator_agent(
        model=config.coordinator_model,
        data_gatherer_model=config.data_gatherer_model,
        summarizer_model=config.summarizer_model,
    )

    run_config = RunConfig(
        workflow_name="standup_chat",
        trace_include_sensitive_data=False,
    )

    console.print(
        f"\n[dim]GitHub user: {github_username} | Looking back: {days_back} day(s)[/dim]\n"
    )

    # Chat loop
    conversation_history: list[dict[str, Any]] = []

    while True:
        try:
            user_input = Prompt.ask("[bold blue]You[/bold blue]")
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input.strip():
            continue

        # Check for exit commands
        if user_input.lower() in ("exit", "quit", "bye", "q"):
            console.print("[dim]Goodbye! Your standup was saved.[/dim]")
            break

        # Add user message to history
        conversation_history.append({"role": "user", "content": user_input})

        # Build context-aware prompt
        if not conversation_history[:-1]:
            # First message - include setup context
            prompt = f"""The user wants to generate a standup. Context:
- GitHub username: {github_username}
- Days to look back: {days_back}
- History context is enabled

User request: {user_input}
"""
        else:
            prompt = user_input

        try:
            # Run the agent
            console.print()
            result = await Runner.run(
                agent,
                input=prompt,
                context=context,
                run_config=run_config,
            )

            output = str(result.final_output)

            # Update context with current standup if it looks like one
            if "Yesterday" in output or "Today" in output or "worked on" in output.lower():
                context.current_standup = output

            # Display the response
            console.print(f"[bold green]Assistant[/bold green]: {output}\n")

            # Add to history
            conversation_history.append({"role": "assistant", "content": output})

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]\n")
            continue
