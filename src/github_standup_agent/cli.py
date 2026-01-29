"""CLI interface for GitHub Standup Agent."""

import asyncio
import os
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Load .env file early before any other imports that might use env vars
load_dotenv()

from github_standup_agent import __version__  # noqa: E402
from github_standup_agent.config import (  # noqa: E402
    EXAMPLES_FILE,
    STYLE_FILE,
    StandupConfig,
    create_default_examples_file,
    create_default_style_file,
    get_github_username,
    load_examples_from_file,
    load_style_from_file,
)

app = typer.Typer(
    name="standup",
    help="AI-powered daily standup summaries from GitHub activity.",
    no_args_is_help=True,
)

console = Console()


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        console.print(f"github-standup-agent v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """GitHub Standup Agent - AI-powered standup summaries."""
    pass


@app.command()
def generate(
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Number of days to look back."),
    ] = 1,
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output destination: stdout, clipboard, or file."),
    ] = "stdout",
    output_file: Annotated[
        str | None,
        typer.Option(
            "--output-file", "-f", help="Filename when output is 'file' (default: standup.txt)."
        ),
    ] = None,
    stream: Annotated[
        bool,
        typer.Option("--stream", "-s", help="Stream output in real-time."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose/--quiet", "-V/-q", help="Show agent activity (tool calls, handoffs)."
        ),
    ] = True,
) -> None:
    """Generate a standup summary from your GitHub activity."""
    from github_standup_agent.runner import run_standup_generation

    config = StandupConfig.load()

    # Auto-detect GitHub username if not set
    github_user = config.github_username or get_github_username()
    if not github_user:
        console.print(
            "[red]Could not detect GitHub username. "
            "Make sure you're logged in with `gh auth login`.[/red]"
        )
        raise typer.Exit(1)

    console.print(
        f"[dim]Generating standup for [bold]{github_user}[/bold] ({days} day(s))...[/dim]"
    )

    try:
        result = asyncio.run(
            run_standup_generation(
                config=config,
                days_back=days,
                github_username=github_user,
                stream=stream,
                verbose=verbose,
            )
        )

        if output == "clipboard":
            import pyperclip

            pyperclip.copy(result)
            console.print("[green]Standup copied to clipboard![/green]")
        elif output == "file":
            from pathlib import Path

            filename = output_file or "standup.txt"
            filepath = Path(filename)
            filepath.write_text(result)
            console.print(f"[green]Standup saved to {filepath.absolute()}[/green]")
        else:
            console.print()
            console.print(Panel(result, title="Your Standup", border_style="green"))

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def chat(
    days: Annotated[
        int,
        typer.Option("--days", "-d", help="Number of days to look back."),
    ] = 1,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose/--quiet", "-V/-q", help="Show agent activity (tool calls, handoffs)."
        ),
    ] = True,
    resume: Annotated[
        bool,
        typer.Option("--resume", "-r", help="Resume the last chat session."),
    ] = False,
    session: Annotated[
        str | None,
        typer.Option("--session", "-s", help="Use a named session for persistence."),
    ] = None,
) -> None:
    """Start an interactive chat session to refine your standup."""
    from github_standup_agent.runner import run_interactive_chat

    config = StandupConfig.load()

    github_user = config.github_username or get_github_username()
    if not github_user:
        console.print(
            "[red]Could not detect GitHub username. "
            "Make sure you're logged in with `gh auth login`.[/red]"
        )
        raise typer.Exit(1)

    console.print(
        Panel(
            "[bold]Interactive Standup Chat[/bold]\n\n"
            "Commands:\n"
            '  • "generate my standup" - Create initial standup\n'
            '  • "make it shorter" - Refine the summary\n'
            '  • "ignore the docs PR" - Exclude specific items\n'
            '  • "copy to clipboard" - Copy final version\n'
            '  • "exit" or "quit" - End session\n\n'
            "[dim]Session is automatically saved for later resumption.[/dim]",
            title="Welcome",
            border_style="blue",
        )
    )

    try:
        asyncio.run(
            run_interactive_chat(
                config=config,
                days_back=days,
                github_username=github_user,
                verbose=verbose,
                session_name=session,
                resume=resume,
            )
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye![/dim]")


@app.command()
def sessions(
    list_all: Annotated[
        bool,
        typer.Option("--list", "-l", help="List recent chat sessions."),
    ] = False,
    clear: Annotated[
        bool,
        typer.Option("--clear", help="Clear all chat sessions."),
    ] = False,
) -> None:
    """Manage chat sessions."""
    from github_standup_agent.config import SESSIONS_DB_FILE
    from github_standup_agent.runner import list_sessions

    if clear:
        if SESSIONS_DB_FILE.exists():
            if typer.confirm("Are you sure you want to clear all chat sessions?"):
                SESSIONS_DB_FILE.unlink()
                console.print("[green]All chat sessions cleared.[/green]")
        else:
            console.print("[dim]No sessions to clear.[/dim]")
        return

    # Default to listing sessions
    if list_all or not clear:
        session_list = list_sessions(limit=10)
        if not session_list:
            console.print("[dim]No chat sessions yet.[/dim]")
            console.print("[dim]Start one with: standup chat[/dim]")
            return

        console.print("[bold]Recent Chat Sessions:[/bold]\n")
        for s in session_list:
            session_id = s["session_id"]
            updated = s["updated_at"]
            # Remove the 'chat_' prefix for display
            display_name = session_id[5:] if session_id.startswith("chat_") else session_id
            console.print(f"  [cyan]{display_name}[/cyan]  [dim](updated: {updated})[/dim]")

        console.print("\n[dim]Resume with: standup chat --resume[/dim]")
        console.print("[dim]Or use a named session: standup chat --session <name>[/dim]")


@app.command()
def config(
    show: Annotated[
        bool,
        typer.Option("--show", help="Show current configuration."),
    ] = False,
    set_openai_key: Annotated[
        str | None,
        typer.Option("--set-openai-key", help="Set OpenAI API key."),
    ] = None,
    set_github_user: Annotated[
        str | None,
        typer.Option("--set-github-user", help="Set GitHub username."),
    ] = None,
    set_model: Annotated[
        str | None,
        typer.Option("--set-model", help="Set the summarizer model."),
    ] = None,
    set_style: Annotated[
        str | None,
        typer.Option(
            "--set-style", help="Set quick style instructions (use style.md for detailed)."
        ),
    ] = None,
    init_style: Annotated[
        bool,
        typer.Option("--init-style", help="Create a style.md template file to customize."),
    ] = False,
    edit_style: Annotated[
        bool,
        typer.Option("--edit-style", help="Open style.md in your default editor."),
    ] = False,
    init_examples: Annotated[
        bool,
        typer.Option("--init-examples", help="Create an examples.md template file."),
    ] = False,
    edit_examples: Annotated[
        bool,
        typer.Option("--edit-examples", help="Open examples.md in your default editor."),
    ] = False,
    set_slack_channel: Annotated[
        str | None,
        typer.Option("--set-slack-channel", help="Set Slack channel for standups."),
    ] = None,
) -> None:
    """Manage standup-agent configuration."""
    cfg = StandupConfig.load()

    if set_openai_key:
        # For security, we only set this in environment, not in file
        console.print(
            "[yellow]For security, API keys should be set via environment variable.[/yellow]\n"
            f"Add to your shell profile: export OPENAI_API_KEY='{set_openai_key}'"
        )
        return

    if set_github_user:
        cfg.github_username = set_github_user
        cfg.save()
        console.print(f"[green]GitHub username set to: {set_github_user}[/green]")
        return

    if set_model:
        cfg.summarizer_model = set_model
        cfg.save()
        console.print(f"[green]Summarizer model set to: {set_model}[/green]")
        return

    if set_style:
        cfg.style_instructions = set_style
        cfg.save()
        console.print("[green]Style instructions set.[/green]")
        console.print("[dim]For detailed customization, use --init-style to create style.md[/dim]")
        return

    if set_slack_channel:
        cfg.slack_channel = set_slack_channel
        cfg.save()
        console.print(f"[green]Slack channel set to: {set_slack_channel}[/green]")
        console.print("[dim]Don't forget to set STANDUP_SLACK_BOT_TOKEN env var.[/dim]")
        return

    if init_style:
        if STYLE_FILE.exists():
            if not typer.confirm(f"Style file already exists at {STYLE_FILE}. Overwrite?"):
                console.print("[yellow]Cancelled.[/yellow]")
                return
        style_path = create_default_style_file()
        console.print(f"[green]Created style template at:[/green] {style_path}")
        console.print("[dim]Edit this file to customize your standup format.[/dim]")
        return

    if edit_style:
        import shutil
        import subprocess

        if not STYLE_FILE.exists():
            create_default_style_file()
            console.print(f"[dim]Created new style.md at {STYLE_FILE}[/dim]")

        # Try to open in editor
        editor = os.environ.get("EDITOR", "")
        if not editor:
            # Try common editors
            for ed in ["code", "vim", "nano", "vi"]:
                if shutil.which(ed):
                    editor = ed
                    break

        if editor:
            subprocess.run([editor, str(STYLE_FILE)])
        else:
            console.print(f"[yellow]Could not find editor. Edit manually:[/yellow] {STYLE_FILE}")
        return

    if init_examples:
        if EXAMPLES_FILE.exists():
            if not typer.confirm(f"Examples file already exists at {EXAMPLES_FILE}. Overwrite?"):
                console.print("[yellow]Cancelled.[/yellow]")
                return
        examples_path = create_default_examples_file()
        console.print(f"[green]Created examples template at:[/green] {examples_path}")
        console.print("[dim]Add real standup examples to help the AI match your style.[/dim]")
        return

    if edit_examples:
        import shutil
        import subprocess

        if not EXAMPLES_FILE.exists():
            create_default_examples_file()
            console.print(f"[dim]Created new examples.md at {EXAMPLES_FILE}[/dim]")

        # Try to open in editor
        editor = os.environ.get("EDITOR", "")
        if not editor:
            # Try common editors
            for ed in ["code", "vim", "nano", "vi"]:
                if shutil.which(ed):
                    editor = ed
                    break

        if editor:
            subprocess.run([editor, str(EXAMPLES_FILE)])
        else:
            console.print(f"[yellow]Could not find editor. Edit manually:[/yellow] {EXAMPLES_FILE}")
        return

    if show or not any(
        [
            set_openai_key,
            set_github_user,
            set_model,
            set_style,
            init_style,
            edit_style,
            init_examples,
            edit_examples,
            set_slack_channel,
        ]
    ):
        detected_user = get_github_username()
        api_key_status = "Set" if cfg.openai_api_key else "Not set (check env)"

        # Style status
        loaded_style, loaded_style_path = load_style_from_file()
        if loaded_style and loaded_style_path:
            style_status = f"[green]Loaded from {loaded_style_path}[/green]"
        elif cfg.style_instructions:
            style_status = (
                f"[green]Config: {cfg.style_instructions[:50]}...[/green]"
                if len(cfg.style_instructions or "") > 50
                else f"[green]Config: {cfg.style_instructions}[/green]"
            )
        else:
            style_status = "[dim]Default (use --init-style to customize)[/dim]"

        # Examples status
        loaded_examples, loaded_examples_path = load_examples_from_file()
        if loaded_examples and loaded_examples_path:
            examples_status = f"[green]Loaded from {loaded_examples_path}[/green]"
        else:
            examples_status = "[dim]None (use --init-examples to add)[/dim]"

        # Slack status
        slack_token_status = "[green]Set[/green]" if cfg.get_slack_token() else "[dim]Not set[/dim]"
        slack_channel_status = (
            f"[green]{cfg.slack_channel}[/green]"
            if cfg.slack_channel
            else "[dim]Not configured[/dim]"
        )

        username = cfg.github_username or detected_user or "Not set"
        console.print(
            Panel(
                f"[bold]GitHub Username:[/bold] {username}\n"
                f"[bold]OpenAI API Key:[/bold] {api_key_status}\n"
                f"[bold]Default Days:[/bold] {cfg.default_days_back}\n"
                f"[bold]Coordinator Model:[/bold] {cfg.coordinator_model}\n"
                f"[bold]Data Gatherer Model:[/bold] {cfg.data_gatherer_model}\n"
                f"[bold]Summarizer Model:[/bold] {cfg.summarizer_model}\n"
                f"[bold]Temperature:[/bold] {cfg.temperature}\n"
                f"[bold]Style:[/bold] {style_status}\n"
                f"[bold]Examples:[/bold] {examples_status}\n"
                f"[bold]Slack Token:[/bold] {slack_token_status}\n"
                f"[bold]Slack Channel:[/bold] {slack_channel_status}",
                title="Configuration",
                border_style="cyan",
            )
        )


if __name__ == "__main__":
    app()
