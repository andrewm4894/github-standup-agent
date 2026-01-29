"""Summarizer Agent - generates standup summaries from collected data."""

from agents import Agent, AgentHooks, ModelSettings

from github_standup_agent.config import DEFAULT_MODEL
from github_standup_agent.context import StandupContext
from github_standup_agent.tools.clipboard import copy_to_clipboard
from github_standup_agent.tools.history import save_standup_to_file

SUMMARIZER_INSTRUCTIONS = """You are a standup summary specialist.
Create daily standup summaries from GitHub activity data.

Core principles:
- Be concise - standups should be quick to read
- Focus on the most important/impactful work
- Write naturally, like a human would
- If examples are provided, MATCH their tone, format, and level of detail exactly
- Use proper markdown links: [pr](https://...) NOT bare (https://...) URLs

When refining a standup based on user feedback, adjust accordingly.
"""


def _build_instructions(custom_style: str | None = None) -> str:
    """Build the full instructions with optional custom style."""
    if not custom_style:
        return SUMMARIZER_INSTRUCTIONS

    # When examples/style are provided, they take priority
    return f"""{SUMMARIZER_INSTRUCTIONS}

---
IMPORTANT: The user has provided style preferences and/or examples below.
You MUST match the format, tone, headers, and level of detail from the examples.
Do NOT use generic standup formats. Copy the style from the examples precisely.

{custom_style}
"""


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
    instructions = _build_instructions(style_instructions)

    return Agent[StandupContext](
        name="Summarizer",
        handoff_description="Creates formatted standup summaries from GitHub data",
        instructions=instructions,
        tools=[
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
    instructions=SUMMARIZER_INSTRUCTIONS,
    tools=[
        save_standup_to_file,
        copy_to_clipboard,
    ],
    model=DEFAULT_MODEL,
    model_settings=ModelSettings(
        temperature=0.7,
    ),
)
