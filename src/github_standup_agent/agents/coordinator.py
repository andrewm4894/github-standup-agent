"""Coordinator Agent - orchestrates the standup generation workflow."""

from agents import Agent, AgentHooks, ModelSettings

from github_standup_agent.agents.summarizer import create_summarizer_agent
from github_standup_agent.config import DEFAULT_MODEL
from github_standup_agent.context import StandupContext
from github_standup_agent.prompts import get_prompt
from github_standup_agent.tools.clipboard import copy_to_clipboard
from github_standup_agent.tools.feedback import (
    capture_feedback_rating,
    capture_feedback_text,
)
from github_standup_agent.tools.history import save_standup_to_file
from github_standup_agent.tools.slack import (
    confirm_slack_publish,
    publish_standup_to_slack,
    set_slack_thread,
)


def create_coordinator_agent(
    model: str = DEFAULT_MODEL,
    data_gatherer_model: str = DEFAULT_MODEL,
    summarizer_model: str = DEFAULT_MODEL,
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
        instructions=get_prompt("coordinator-instructions"),
        tools=[
            # Sub-agents as tools for reliable execution
            data_gatherer.as_tool(
                tool_name="gather_data",
                tool_description="Gather GitHub activity and Slack standups from the team",
            ),
            summarizer.as_tool(
                tool_name="create_standup_summary",
                tool_description="Create a standup summary from GitHub data with style prefs.",
            ),
            # Direct tools
            copy_to_clipboard,
            save_standup_to_file,
            # Slack tools
            publish_standup_to_slack,
            confirm_slack_publish,
            set_slack_thread,
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


# Default instance (without hooks - use create_coordinator_agent for verbose mode)
coordinator_agent = create_coordinator_agent()
