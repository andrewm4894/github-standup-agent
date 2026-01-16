"""Coordinator Agent - orchestrates the standup generation workflow."""

from agents import Agent, AgentHooks, ModelSettings

from github_standup_agent.agents.summarizer import create_summarizer_agent
from github_standup_agent.context import StandupContext
from github_standup_agent.tools.clipboard import copy_to_clipboard
from github_standup_agent.tools.history import get_recent_standups, save_standup

COORDINATOR_INSTRUCTIONS = """You are a standup generation coordinator. You help users create
daily standup summaries from their GitHub activity.

Your workflow:
1. When asked to generate a standup, first hand off to the Data Gatherer to collect GitHub data
2. Once data is collected, hand off to the Summarizer to create the summary
3. Present the summary to the user and offer to refine, copy to clipboard, or save

For interactive chat sessions:
- Respond to refinement requests by working with the Summarizer
- Handle commands like "copy to clipboard" or "save" directly
- Be helpful and responsive to feedback

Available handoffs:
- Data Gatherer: For collecting GitHub activity (PRs, issues, commits, reviews)
- Summarizer: For creating and refining standup summaries

Important context values:
- context.days_back: Number of days to look back for activity
- context.with_history: Whether to include historical standup context
- context.github_username: The user's GitHub username
- context.current_standup: The current generated/refined standup

Be conversational but efficient. Help users get great standups quickly.
"""


def create_coordinator_agent(
    model: str = "gpt-4o",
    data_gatherer_model: str = "gpt-4o-mini",
    summarizer_model: str = "gpt-4o",
    hooks: AgentHooks[StandupContext] | None = None,
) -> Agent[StandupContext]:
    """Create the coordinator agent with configured sub-agents."""
    from github_standup_agent.agents.data_gatherer import create_data_gatherer_agent

    data_gatherer = create_data_gatherer_agent(model=data_gatherer_model, hooks=hooks)
    summarizer = create_summarizer_agent(model=summarizer_model, hooks=hooks)

    return Agent[StandupContext](
        name="Standup Coordinator",
        instructions=COORDINATOR_INSTRUCTIONS,
        handoffs=[data_gatherer, summarizer],
        tools=[
            copy_to_clipboard,
            get_recent_standups,
            save_standup,
        ],
        model=model,
        model_settings=ModelSettings(
            temperature=0.5,
        ),
        hooks=hooks,
    )


# Default instance (without hooks - use create_coordinator_agent for verbose mode)
coordinator_agent = create_coordinator_agent()
