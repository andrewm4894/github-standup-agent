"""Summarizer Agent - generates standup summaries from collected data."""

from collections.abc import Callable
from typing import Any

from agents import Agent, AgentHooks, ModelSettings, RunContextWrapper

from github_standup_agent.config import DEFAULT_MODEL
from github_standup_agent.context import StandupContext
from github_standup_agent.prompts import compile_prompt, get_prompt
from github_standup_agent.tools.clipboard import copy_to_clipboard
from github_standup_agent.tools.history import save_standup_to_file
from github_standup_agent.tools.slack import get_team_slack_standups


def _format_collected_data(ctx: StandupContext) -> str | None:
    """Format collected GitHub data from context into text for the Summarizer.

    Returns None if no data has been collected yet.
    """
    sections: list[str] = []

    def _format_pr(pr: dict[str, Any]) -> str:
        repo = pr.get("repository", {}).get("nameWithOwner", "unknown")
        number = pr.get("number", "?")
        title = pr.get("title", "untitled")
        state = pr.get("state", "unknown").upper()
        draft = " DRAFT" if pr.get("isDraft") else ""
        url = pr.get("url", "")
        labels = pr.get("labels", [])
        label_str = ""
        if labels:
            label_names = [lb.get("name", "") for lb in labels if lb.get("name")]
            if label_names:
                label_str = f" (labels: {', '.join(label_names)})"
        return f"- {repo}#{number} [{state}{draft}] {title}{label_str} {url}"

    def _format_issue(issue: dict[str, Any]) -> str:
        repo = issue.get("repository", {}).get("nameWithOwner", "unknown")
        number = issue.get("number", "?")
        title = issue.get("title", "untitled")
        state = issue.get("state", "unknown").upper()
        url = issue.get("url", "")
        return f"- {repo}#{number} [{state}] {title} {url}"

    def _format_commit(commit: dict[str, Any]) -> str:
        repo = commit.get("repository", {}).get("nameWithOwner", "unknown")
        sha = commit.get("oid", commit.get("sha", "?"))[:7]
        msg = commit.get("messageHeadline", commit.get("message", "").split("\n")[0])
        url = commit.get("url", "")
        return f"- {repo} {sha} {msg} {url}"

    def _format_review(review: dict[str, Any]) -> str:
        repo = review.get("repo", review.get("repository", "unknown"))
        number = review.get("pr_number", review.get("number", "?"))
        title = review.get("pr_title", review.get("title", ""))
        state = review.get("state", "unknown")
        url = review.get("url", "")
        return f"- {repo}#{number} {title} [{state}] {url}"

    if ctx.collected_prs:
        sections.append("PULL REQUESTS:")
        for pr in ctx.collected_prs:
            sections.append(_format_pr(pr))

    if ctx.collected_reviews:
        sections.append("\nREVIEWS:")
        for review in ctx.collected_reviews:
            sections.append(_format_review(review))

    if ctx.collected_issues:
        sections.append("\nISSUES:")
        for issue in ctx.collected_issues:
            sections.append(_format_issue(issue))

    if ctx.collected_commits:
        sections.append("\nCOMMITS:")
        for commit in ctx.collected_commits:
            sections.append(_format_commit(commit))

    if ctx.collected_activity_feed:
        # Include a compact activity summary (not full feed, to avoid bloat)
        sections.append(f"\nACTIVITY FEED: {len(ctx.collected_activity_feed)} events collected")

    if not sections:
        return None

    return "\n".join(sections)


def _build_base_instructions(custom_style: str | None = None) -> str:
    """Build the base instructions with optional custom style (static string)."""
    base = get_prompt("summarizer-instructions")
    if not custom_style:
        return base

    # When examples/style are provided, they take priority
    custom_block = compile_prompt("summarizer-custom-style", {"custom_style": custom_style})
    return base + custom_block


def _make_dynamic_instructions(
    custom_style: str | None = None,
) -> Callable[[RunContextWrapper[StandupContext], Agent[StandupContext]], str]:
    """Return a callable that builds instructions with current standup context.

    The OpenAI Agents SDK calls this each time the agent runs, so the
    Summarizer always sees the latest collected data and standup text.
    """
    base = _build_base_instructions(custom_style)
    # Pre-load the templates once at creation time
    standup_template = get_prompt("summarizer-current-standup")
    collected_data_template = get_prompt("summarizer-collected-data")

    def _dynamic_instructions(
        ctx: RunContextWrapper[StandupContext], agent: Agent[StandupContext]
    ) -> str:
        result = base

        # Inject collected GitHub data so the Summarizer can actually see it
        collected_data = _format_collected_data(ctx.context)
        if collected_data:
            from github_standup_agent.prompts import PromptManager

            data_suffix = PromptManager().compile(
                collected_data_template, {"collected_data": collected_data}
            )
            result += data_suffix

        # Inject current standup for refinement iterations
        current = ctx.context.current_standup
        if current:
            from github_standup_agent.prompts import PromptManager

            standup_suffix = PromptManager().compile(standup_template, {"current_standup": current})
            result += standup_suffix

        return result

    return _dynamic_instructions


def create_summarizer_agent(
    model: str = DEFAULT_MODEL,
    hooks: AgentHooks[StandupContext] | None = None,
    style_instructions: str | None = None,
) -> Agent[StandupContext]:
    """Create the summarizer agent.

    Args:
        model: The model to use for the summarizer
        hooks: Optional agent hooks for logging/observability
        style_instructions: Optional custom style instructions from user config/file
    """
    instructions = _make_dynamic_instructions(style_instructions)

    return Agent[StandupContext](
        name="Summarizer",
        handoff_description="Creates formatted standup summaries from GitHub data",
        instructions=instructions,
        tools=[
            get_team_slack_standups,  # Fetch recent standups to copy format
            save_standup_to_file,
            copy_to_clipboard,
        ],
        model=model,
        model_settings=ModelSettings(
            temperature=0.7,  # Some creativity for natural-sounding summaries
        ),
        hooks=hooks,
    )


# Default instance (without structured output for more flexibility in chat mode)
summarizer_agent = Agent[StandupContext](
    name="Summarizer",
    handoff_description="Creates formatted standup summaries from GitHub data",
    instructions=_make_dynamic_instructions(),
    tools=[
        get_team_slack_standups,
        save_standup_to_file,
        copy_to_clipboard,
    ],
    model=DEFAULT_MODEL,
    model_settings=ModelSettings(
        temperature=0.7,
    ),
)
