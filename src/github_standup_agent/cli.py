"""CLI interface for GitHub Standup Agent."""

import asyncio
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Load .env file early before any other imports that might use env vars
load_dotenv()

from github_standup_agent import __version__
from github_standup_agent.config import StandupConfig, get_github_username

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
        typer.Option("--output", "-o", help="Output destination: stdout or clipboard."),
    ] = "stdout",
    with_history: Annotated[
        bool,
        typer.Option("--with-history", help="Include context from recent standups."),
    ] = False,
    stream: Annotated[
        bool,
        typer.Option("--stream", "-s", help="Stream output in real-time."),
    ] = False,
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
                with_history=with_history,
                github_username=github_user,
                stream=stream,
            )
        )

        if output == "clipboard":
            import pyperclip

            pyperclip.copy(result)
            console.print("[green]Standup copied to clipboard![/green]")
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
            '  • "exit" or "quit" - End session',
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
            )
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye![/dim]")


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

    if show or not any([set_openai_key, set_github_user, set_model]):
        detected_user = get_github_username()
        api_key_status = "Set" if cfg.openai_api_key else "Not set (check env)"
        console.print(Panel(
            f"[bold]GitHub Username:[/bold] {cfg.github_username or detected_user or 'Not set'}\n"
            f"[bold]OpenAI API Key:[/bold] {api_key_status}\n"
            f"[bold]Default Days:[/bold] {cfg.default_days_back}\n"
            f"[bold]Coordinator Model:[/bold] {cfg.coordinator_model}\n"
            f"[bold]Data Gatherer Model:[/bold] {cfg.data_gatherer_model}\n"
            f"[bold]Summarizer Model:[/bold] {cfg.summarizer_model}\n"
            f"[bold]Temperature:[/bold] {cfg.temperature}",
            title="Configuration",
            border_style="cyan",
        ))


@app.command()
def history(
    list_all: Annotated[
        bool,
        typer.Option("--list", "-l", help="List past standups."),
    ] = False,
    date: Annotated[
        str | None,
        typer.Option("--date", help="Show standup for a specific date (YYYY-MM-DD)."),
    ] = None,
    clear: Annotated[
        bool,
        typer.Option("--clear", help="Clear standup history."),
    ] = False,
) -> None:
    """View and manage standup history."""
    from github_standup_agent.db import StandupDatabase

    db = StandupDatabase()

    if clear:
        if typer.confirm("Are you sure you want to clear all standup history?"):
            db.clear_all()
            console.print("[green]History cleared.[/green]")
        return

    if date:
        standup = db.get_by_date(date)
        if standup:
            console.print(
                Panel(standup["summary"], title=f"Standup for {date}", border_style="green")
            )
        else:
            console.print(f"[yellow]No standup found for {date}[/yellow]")
        return

    if list_all or not any([date, clear]):
        standups = db.get_recent(limit=10)
        if not standups:
            console.print("[dim]No standups in history yet.[/dim]")
            return

        console.print("[bold]Recent Standups:[/bold]\n")
        for s in standups:
            preview = s["summary"][:100] + "..." if len(s["summary"]) > 100 else s["summary"]
            console.print(f"  [cyan]{s['date']}[/cyan]: {preview}\n")


if __name__ == "__main__":
    app()
