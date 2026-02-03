"""Summarizer Agent - generates standup summaries from collected data."""

from collections.abc import Callable

from agents import Agent, AgentHooks, ModelSettings, RunContextWrapper

from github_standup_agent.config import DEFAULT_MODEL
from github_standup_agent.context import StandupContext
from github_standup_agent.prompts import compile_prompt, get_prompt
from github_standup_agent.tools.clipboard import copy_to_clipboard
from github_standup_agent.tools.history import save_standup_to_file
from github_standup_agent.tools.slack import get_team_slack_standups


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
    Summarizer always sees the latest standup text for refinement.
    """
    base = _build_base_instructions(custom_style)
    # Pre-load the template once at creation time
    standup_template = get_prompt("summarizer-current-standup")

    def _dynamic_instructions(
        ctx: RunContextWrapper[StandupContext], agent: Agent[StandupContext]
    ) -> str:
        current = ctx.context.current_standup
        if not current:
            return base
        from github_standup_agent.prompts import PromptManager

        suffix = PromptManager().compile(standup_template, {"current_standup": current})
        return base + suffix

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
