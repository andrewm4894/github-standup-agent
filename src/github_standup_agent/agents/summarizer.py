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
- If examples or style instructions are provided, you MUST follow them EXACTLY
- Match headers, link formats, sections, and tone precisely from examples
- If team Slack standups are included in the data, study their FORMAT too - match how teammates write their standups

When refining a standup based on user feedback, adjust accordingly.
"""


def _build_instructions(custom_style: str | None = None) -> str:
    """Build the full instructions with optional custom style."""
    if not custom_style:
        return SUMMARIZER_INSTRUCTIONS

    # When examples/style are provided, they take priority
    return f"""{SUMMARIZER_INSTRUCTIONS}

---
CRITICAL FORMATTING REQUIREMENTS - YOU MUST FOLLOW THESE EXACTLY:

The user has provided style preferences and/or examples below. These OVERRIDE any defaults.
You MUST:
1. Use the EXACT section headers from examples (e.g., "Did:" and "Will Do:" NOT "### Did" or "**Did:**")
2. Use the EXACT link format from examples (e.g., Slack mrkdwn `<url|pr>` NOT markdown `[text](url)`)
3. Match the tone, bullet style, and level of detail precisely
4. Skip sections that examples don't include (e.g., no "Blockers" unless examples show it)
5. If team Slack standups are in the data, ALSO study their format - match how teammates format their standups

Do NOT use generic standup formats. Copy the structure from the examples character-for-character.
Do NOT use markdown headers (###) or bold (**text**) unless the examples specifically use them.

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
