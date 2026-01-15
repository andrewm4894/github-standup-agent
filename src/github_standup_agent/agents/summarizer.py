"""Summarizer Agent - generates standup summaries from collected data."""

from agents import Agent, ModelSettings
from pydantic import BaseModel, Field

from github_standup_agent.context import StandupContext
from github_standup_agent.tools.clipboard import copy_to_clipboard
from github_standup_agent.tools.history import get_recent_standups, save_standup


class StandupSummary(BaseModel):
    """Structured output for a standup summary."""

    yesterday: str = Field(description="What was worked on (completed work, merged PRs)")
    today: str = Field(description="What will be worked on (open PRs, assigned issues)")
    blockers: str = Field(description="Any blockers or challenges (empty string if none)")
    formatted_summary: str = Field(description="Full formatted standup ready for sharing")


SUMMARIZER_INSTRUCTIONS = """You are a standup summary specialist. Your job is to create concise,
well-formatted daily standup summaries from GitHub activity data.

Format standups in this structure:

**Yesterday/Recently:**
- [Completed work, merged PRs, closed issues]

**Today/Next:**
- [Open PRs that need attention, assigned issues, planned work]

**Blockers:** (only if there are any)
- [Any challenges or blockers]

Guidelines:
1. Be CONCISE - standups should be quick to read
2. Focus on the most important/impactful work
3. Group related items together
4. Use action verbs (Completed, Merged, Fixed, Working on, etc.)
5. Include PR/issue numbers for reference
6. If the user has provided recent standups for context, maintain continuity
   - Avoid repeating the same descriptions for ongoing work
   - Reference progress on items mentioned previously
   - Track blockers across days

When refining a standup based on user feedback:
- "make it shorter/less wordy" -> Remove details, keep only essential points
- "ignore X" -> Remove that item from the summary
- "focus on Y" -> Emphasize that area, minimize others
- "add Z" -> Include the new information

Always store the generated summary in context.current_standup for later use.
"""


def create_summarizer_agent(model: str = "gpt-4o") -> Agent[StandupContext]:
    """Create the summarizer agent."""
    return Agent[StandupContext](
        name="Summarizer",
        handoff_description="Creates formatted standup summaries from GitHub data",
        instructions=SUMMARIZER_INSTRUCTIONS,
        tools=[
            get_recent_standups,
            save_standup,
            copy_to_clipboard,
        ],
        model=model,
        model_settings=ModelSettings(
            temperature=0.7,  # Some creativity for natural-sounding summaries
        ),
        # Use structured output for consistent formatting
        output_type=StandupSummary,
    )


# Default instance (without structured output for more flexibility in chat mode)
summarizer_agent = Agent[StandupContext](
    name="Summarizer",
    handoff_description="Creates formatted standup summaries from GitHub data",
    instructions=SUMMARIZER_INSTRUCTIONS,
    tools=[
        get_recent_standups,
        save_standup,
        copy_to_clipboard,
    ],
    model="gpt-4o",
    model_settings=ModelSettings(
        temperature=0.7,
    ),
)
