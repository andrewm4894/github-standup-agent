"""Runner module for executing the standup agent workflow."""

import os
import sqlite3
from datetime import date
from typing import Any

from agents import RunConfig, Runner, SQLiteSession
from rich.console import Console
from rich.prompt import Prompt

from github_standup_agent.agents.coordinator import create_coordinator_agent
from github_standup_agent.config import (
    DATA_DIR,
    SESSIONS_DB_FILE,
    StandupConfig,
    get_combined_style_instructions,
)
from github_standup_agent.context import StandupContext
from github_standup_agent.hooks import StandupAgentHooks, StandupRunHooks
from github_standup_agent.instrumentation import capture_event, setup_posthog, shutdown_posthog

console = Console()


def _ensure_sessions_db() -> None:
    """Ensure the sessions database directory exists."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_session_id(name: str | None = None, github_username: str | None = None) -> str:
    """Generate a session ID.

    Args:
        name: Optional custom session name
        github_username: GitHub username for default session naming

    Returns:
        A session ID string
    """
    if name:
        return f"chat_{name}"
    # Default: use date-based session ID
    return f"chat_{github_username or 'user'}_{date.today().isoformat()}"


def get_last_session_id() -> str | None:
    """Get the most recently used session ID.

    Returns:
        The last session ID or None if no sessions exist
    """
    if not SESSIONS_DB_FILE.exists():
        return None

    try:
        conn = sqlite3.connect(str(SESSIONS_DB_FILE))
        cursor = conn.execute(
            """
            SELECT session_id FROM agent_sessions
            ORDER BY updated_at DESC
            LIMIT 1
            """
        )
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except sqlite3.Error:
        return None


def list_sessions(limit: int = 10) -> list[dict[str, str]]:
    """List recent chat sessions.

    Args:
        limit: Maximum number of sessions to return

    Returns:
        List of session info dicts with 'session_id', 'created_at', 'updated_at'
    """
    if not SESSIONS_DB_FILE.exists():
        return []

    try:
        conn = sqlite3.connect(str(SESSIONS_DB_FILE))
        cursor = conn.execute(
            """
            SELECT session_id, created_at, updated_at
            FROM agent_sessions
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        results = cursor.fetchall()
        conn.close()
        return [{"session_id": r[0], "created_at": r[1], "updated_at": r[2]} for r in results]
    except sqlite3.Error:
        return []


def _emit_standup_event(standup: str, context: StandupContext, mode: str = "generate") -> None:
    """Emit a PostHog event for a generated standup.

    Args:
        standup: The generated standup text
        context: The standup context
        mode: The mode of generation ("generate" or "chat")
    """
    from datetime import date

    capture_event(
        event_name="standup_generated",
        properties={
            "summary": standup,
            "github_username": context.github_username,
            "days_back": context.days_back,
            "date": date.today().isoformat(),
            "summary_length": len(standup),
            "has_prs": bool(context.collected_prs),
            "has_issues": bool(context.collected_issues),
            "has_commits": bool(context.collected_commits),
            "has_reviews": bool(context.collected_reviews),
            "mode": mode,
        },
    )


def _emit_chat_session_event(
    event_name: str,
    session_id: str,
    context: StandupContext,
    extra_properties: dict[str, Any] | None = None,
) -> None:
    """Emit a PostHog event for chat session lifecycle.

    Args:
        event_name: The event name (e.g., "chat_session_started", "chat_session_ended")
        session_id: The chat session ID
        context: The standup context
        extra_properties: Additional properties to include
    """
    from datetime import date

    properties = {
        "session_id": session_id,
        "github_username": context.github_username,
        "days_back": context.days_back,
        "date": date.today().isoformat(),
    }
    if extra_properties:
        properties.update(extra_properties)

    capture_event(event_name=event_name, properties=properties)


async def run_standup_generation(
    config: StandupConfig,
    days_back: int = 1,
    github_username: str | None = None,
    stream: bool = False,
    verbose: bool = False,
) -> str:
    """
    Run the standup generation workflow.

    Args:
        config: The standup configuration
        days_back: Number of days to look back for activity
        github_username: GitHub username
        stream: Whether to stream output
        verbose: Whether to show verbose output

    Returns:
        The generated standup summary
    """
    # Set up OpenAI API key
    api_key = config.get_api_key()
    os.environ["OPENAI_API_KEY"] = api_key

    # Load custom style instructions
    style_instructions = get_combined_style_instructions(config)

    # Create context
    context = StandupContext(
        config=config,
        days_back=days_back,
        github_username=github_username,
        style_instructions=style_instructions,
    )

    # Initialize PostHog instrumentation (if configured)
    setup_posthog(distinct_id=github_username)

    # Create agent hooks for verbose mode
    agent_hooks = StandupAgentHooks(verbose=verbose) if verbose else None

    # Create the coordinator agent with configured models and style
    agent = create_coordinator_agent(
        model=config.coordinator_model,
        data_gatherer_model=config.data_gatherer_model,
        summarizer_model=config.summarizer_model,
        hooks=agent_hooks,
        style_instructions=style_instructions,
    )

    # Build the prompt
    prompt = f"Generate a standup for the last {days_back} day(s)."

    # Create hooks
    run_hooks = StandupRunHooks(verbose=verbose)

    # Run configuration
    run_config = RunConfig(
        workflow_name="standup_generation",
        trace_include_sensitive_data=True,
    )

    try:
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
            final_standup = context.current_standup or result_text

            # Emit PostHog event for the generated standup
            _emit_standup_event(final_standup, context)

            return final_standup
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
            final_standup = str(result.final_output)

            # Store in context
            context.current_standup = final_standup

            # Emit PostHog event for the generated standup
            _emit_standup_event(final_standup, context)

            return final_standup
    finally:
        # Ensure PostHog events are flushed
        shutdown_posthog()


async def run_interactive_chat(
    config: StandupConfig,
    days_back: int = 1,
    github_username: str | None = None,
    verbose: bool = False,
    session_name: str | None = None,
    resume: bool = False,
) -> None:
    """
    Run an interactive chat session for refining standups.

    Args:
        config: The standup configuration
        days_back: Number of days to look back for activity
        github_username: GitHub username
        verbose: Whether to show verbose output (agent activity, tool calls)
        session_name: Optional custom session name for persistence
        resume: If True, resume the last session instead of starting new
    """
    # Set up OpenAI API key
    api_key = config.get_api_key()
    os.environ["OPENAI_API_KEY"] = api_key

    # Load custom style instructions
    style_instructions = get_combined_style_instructions(config)

    # Create context
    context = StandupContext(
        config=config,
        days_back=days_back,
        github_username=github_username,
        style_instructions=style_instructions,
    )

    # Initialize PostHog instrumentation (if configured)
    setup_posthog(distinct_id=github_username)

    # Create agent hooks for verbose mode
    agent_hooks = StandupAgentHooks(verbose=verbose) if verbose else None

    # Create the coordinator agent with style
    agent = create_coordinator_agent(
        model=config.coordinator_model,
        data_gatherer_model=config.data_gatherer_model,
        summarizer_model=config.summarizer_model,
        hooks=agent_hooks,
        style_instructions=style_instructions,
    )

    # Create run hooks for verbose mode
    run_hooks = StandupRunHooks(verbose=verbose)

    run_config = RunConfig(
        workflow_name="standup_chat",
        trace_include_sensitive_data=True,
    )

    # Set up session for conversation persistence
    _ensure_sessions_db()

    if resume:
        # Try to resume the last session
        session_id = get_last_session_id()
        if session_id:
            console.print(f"[dim]Resuming session: {session_id}[/dim]")
        else:
            console.print("[yellow]No previous session found, starting new session.[/yellow]")
            session_id = get_session_id(session_name, github_username)
    else:
        session_id = get_session_id(session_name, github_username)

    session = SQLiteSession(session_id=session_id, db_path=str(SESSIONS_DB_FILE))

    # Check if resuming an existing session with history
    existing_items = await session.get_items()
    is_new_session = len(existing_items) == 0

    console.print(
        f"\n[dim]GitHub user: {github_username} | Looking back: {days_back} day(s) | "
        f"Session: {session_id}[/dim]\n"
    )

    if not is_new_session:
        console.print(f"[dim]Resumed session with {len(existing_items)} previous messages.[/dim]\n")

    # Track if this is the first message in this run (for context injection)
    first_message_in_run = is_new_session

    # Track chat turns for analytics
    chat_turns = 0

    # Emit chat session started event
    _emit_chat_session_event(
        event_name="chat_session_started",
        session_id=session_id,
        context=context,
        extra_properties={
            "is_new_session": is_new_session,
            "resumed_message_count": len(existing_items),
        },
    )

    try:
        while True:
            try:
                user_input = Prompt.ask("[bold blue]You[/bold blue]")
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input.strip():
                continue

            # Check for exit commands
            if user_input.lower() in ("exit", "quit", "bye", "q"):
                console.print(f"[dim]Goodbye! Session saved as '{session_id}'.[/dim]")
                break

            # Build context-aware prompt for first message
            if first_message_in_run:
                # First message - include setup context
                prompt = f"""The user wants to generate a standup. Context:
- GitHub username: {github_username}
- Days to look back: {days_back}
- History context is enabled

User request: {user_input}
"""
                first_message_in_run = False
            else:
                prompt = user_input

            try:
                # Run the agent with session for automatic history management
                console.print()
                result = await Runner.run(
                    agent,
                    input=prompt,
                    context=context,
                    run_config=run_config,
                    hooks=run_hooks,
                    session=session,
                )

                output = str(result.final_output)

                # Always update context - let the agent decide what's a standup
                context.current_standup = output

                # Track turn and emit event
                chat_turns += 1
                _emit_standup_event(output, context, mode="chat")

                # Display the response
                console.print(f"[bold green]Assistant[/bold green]: {output}\n")

            except Exception as e:
                console.print(f"[red]Error: {e}[/red]\n")
                continue
    finally:
        # Emit chat session ended event
        final_length = len(context.current_standup) if context.current_standup else 0
        _emit_chat_session_event(
            event_name="chat_session_ended",
            session_id=session_id,
            context=context,
            extra_properties={
                "chat_turns": chat_turns,
                "final_standup_length": final_length,
            },
        )
        # Clean up session connection
        session.close()
        # Ensure PostHog events are flushed
        shutdown_posthog()
