"""Standup Agent - single agent that gathers GitHub data and generates standup summaries."""

from collections.abc import Callable

from agents import Agent, AgentHooks, ModelSettings, RunContextWrapper

from github_standup_agent.config import DEFAULT_MODEL
from github_standup_agent.context import StandupContext
from github_standup_agent.prompts import compile_prompt, get_prompt
from github_standup_agent.tools.clipboard import copy_to_clipboard
from github_standup_agent.tools.feedback import (
    capture_feedback_rating,
    capture_feedback_text,
)
from github_standup_agent.tools.github import (
    get_activity_feed,
    get_activity_summary,
    get_issue_details,
    get_pr_details,
    list_assigned_items,
    list_comments,
    list_commits,
    list_issues,
    list_prs,
    list_reviews,
)
from github_standup_agent.tools.history import save_standup_to_file
from github_standup_agent.tools.slack import (
    confirm_slack_publish,
    get_team_slack_standups,
    publish_standup_to_slack,
    set_slack_thread,
)


def _build_base_instructions(custom_style: str | None = None) -> str:
    """Build the base instructions with optional custom style (static string)."""
    base = get_prompt("standup-agent-instructions")
    if not custom_style:
        return base

    custom_block = compile_prompt("custom-style", {"custom_style": custom_style})
    return base + custom_block


def _make_dynamic_instructions(
    custom_style: str | None = None,
) -> Callable[[RunContextWrapper[StandupContext], Agent[StandupContext]], str]:
    """Return a callable that builds instructions with current standup context.

    The OpenAI Agents SDK calls this each time the agent runs, so the
    agent always sees the latest standup text for refinement.
    """
    base = _build_base_instructions(custom_style)
    standup_template = get_prompt("current-standup")

    def _dynamic_instructions(
        ctx: RunContextWrapper[StandupContext], agent: Agent[StandupContext]
    ) -> str:
        result = base

        # Inject current standup for refinement iterations
        current = ctx.context.current_standup
        if current:
            from github_standup_agent.prompts import PromptManager

            standup_suffix = PromptManager().compile(standup_template, {"current_standup": current})
            result += standup_suffix

        return result

    return _dynamic_instructions


def create_standup_agent(
    model: str = DEFAULT_MODEL,
    hooks: AgentHooks[StandupContext] | None = None,
    style_instructions: str | None = None,
) -> Agent[StandupContext]:
    """Create the standup agent with all tools.

    Args:
        model: The model to use
        hooks: Optional agent hooks for logging/observability
        style_instructions: Optional custom style instructions from user config/file
    """
    instructions = _make_dynamic_instructions(style_instructions)

    return Agent[StandupContext](
        name="Standup Agent",
        instructions=instructions,
        tools=[
            # GitHub overview tools
            get_activity_feed,
            get_activity_summary,
            # GitHub list tools (with date filters)
            list_prs,
            list_issues,
            list_commits,
            list_reviews,
            list_comments,
            # GitHub assigned items (no date filter)
            list_assigned_items,
            # GitHub detail tools
            get_pr_details,
            get_issue_details,
            # Slack tools
            get_team_slack_standups,
            publish_standup_to_slack,
            confirm_slack_publish,
            set_slack_thread,
            # Utility tools
            copy_to_clipboard,
            save_standup_to_file,
            # Feedback tools
            capture_feedback_rating,
            capture_feedback_text,
        ],
        model=model,
        model_settings=ModelSettings(
            temperature=0.5,
        ),
        hooks=hooks,
    )


# Default instance (without hooks - use create_standup_agent for verbose mode)
standup_agent = create_standup_agent()
