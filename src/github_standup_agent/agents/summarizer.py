"""Summarizer Agent - generates standup summaries from collected data."""

from agents import Agent, AgentHooks, ModelSettings

from github_standup_agent.config import DEFAULT_MODEL
from github_standup_agent.context import StandupContext
from github_standup_agent.tools.clipboard import copy_to_clipboard
from github_standup_agent.tools.history import save_standup_to_file
from github_standup_agent.tools.slack import get_team_slack_standups

SUMMARIZER_INSTRUCTIONS = """You are a standup summary specialist.
Create daily standup summaries from GitHub activity data.

CRITICAL FIRST STEP:
Before writing ANY standup, call get_team_slack_standups to fetch recent team standups.
Study the EXACT format your teammates use - headers, link style, sections, tone.
Your output MUST match their format precisely.

Core principles:
- Be concise - standups should be quick to read
- Focus on the most important/impactful work
- Write naturally, like a human would
- Copy the EXACT format from team Slack standups (headers like "Did:" not "## Did")
- Use Slack mrkdwn links: <https://github.com/org/repo/pull/123|pr> NOT markdown links
- Only include sections that teammates use (usually just "Did:" and "Will Do:")

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

STEP 1: Call get_team_slack_standups first to see how teammates format their standups.
STEP 2: Copy their EXACT format - same headers, same link style, same sections.

The user has also provided style preferences and/or examples below.
You MUST:
1. Use the EXACT section headers (e.g., "Did:" and "Will Do:" NOT "## Did" or "### Did" or "**Did:**")
2. Use Slack mrkdwn links: <https://github.com/org/repo/pull/123|pr> NOT markdown `[text](url)`
3. Match the tone, bullet style, and level of detail from examples and team standups
4. Skip sections that examples don't include (e.g., no "Blockers" section)

Do NOT use markdown headers (##, ###) or bold (**text**).
Do NOT use repo#number format - use short labels like "pr" or "issue" in links.

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
    instructions=SUMMARIZER_INSTRUCTIONS,
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
