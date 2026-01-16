"""Coordinator Agent - orchestrates the standup generation workflow."""

from agents import Agent, AgentHooks, ModelSettings

from github_standup_agent.agents.summarizer import create_summarizer_agent
from github_standup_agent.context import StandupContext
from github_standup_agent.tools.clipboard import copy_to_clipboard
from github_standup_agent.tools.history import (
    get_recent_standups,
    save_standup,
    save_standup_to_file,
)

COORDINATOR_INSTRUCTIONS = """You coordinate standup generation.

IMPORTANT: You NEVER write standup summaries yourself. You MUST use the tools:
- Use gather_github_data tool to collect GitHub activity
- Use create_standup_summary tool to generate the standup (it has the user's style)

Workflow:
1. Call gather_github_data to collect GitHub activity
2. Call create_standup_summary with the collected data to create the standup
3. Return the summary to the user

For "copy to clipboard" or "save" requests: use those tools directly.
For refinement requests: call create_standup_summary again with the feedback.
"""


def create_coordinator_agent(
    model: str = "gpt-4o",
    data_gatherer_model: str = "gpt-4o-mini",
    summarizer_model: str = "gpt-4o",
    hooks: AgentHooks[StandupContext] | None = None,
    style_instructions: str | None = None,
) -> Agent[StandupContext]:
    """Create the coordinator agent with sub-agents wrapped as tools.

    Uses the agents-as-tools pattern for reliable execution flow.

    Args:
        model: The model to use for the coordinator
        data_gatherer_model: The model to use for the data gatherer
        summarizer_model: The model to use for the summarizer
        hooks: Optional agent hooks for logging/observability
        style_instructions: Optional custom style instructions for the summarizer
    """
    from github_standup_agent.agents.data_gatherer import create_data_gatherer_agent

    data_gatherer = create_data_gatherer_agent(model=data_gatherer_model, hooks=hooks)
    summarizer = create_summarizer_agent(
        model=summarizer_model, hooks=hooks, style_instructions=style_instructions
    )

    return Agent[StandupContext](
        name="Standup Coordinator",
        instructions=COORDINATOR_INSTRUCTIONS,
        tools=[
            # Sub-agents as tools for reliable execution
            data_gatherer.as_tool(
                tool_name="gather_github_data",
                tool_description="Gather GitHub activity data (PRs, issues, commits, reviews)",
            ),
            summarizer.as_tool(
                tool_name="create_standup_summary",
                tool_description="Create a standup summary from GitHub data. Has user's style preferences.",
            ),
            # Direct tools
            copy_to_clipboard,
            get_recent_standups,
            save_standup,
            save_standup_to_file,
        ],
        model=model,
        model_settings=ModelSettings(
            temperature=0.5,
        ),
        hooks=hooks,
    )


# Default instance (without hooks - use create_coordinator_agent for verbose mode)
coordinator_agent = create_coordinator_agent()
