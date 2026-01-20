"""Coordinator Agent - orchestrates the standup generation workflow."""

from agents import Agent, AgentHooks, ModelSettings

from github_standup_agent.agents.summarizer import create_summarizer_agent
from github_standup_agent.config import DEFAULT_MODEL
from github_standup_agent.context import StandupContext
from github_standup_agent.tools.clipboard import copy_to_clipboard
from github_standup_agent.tools.feedback import (
    capture_feedback_rating,
    capture_feedback_text,
)
from github_standup_agent.tools.history import (
    get_recent_standups,
    save_standup,
    save_standup_to_file,
)
from github_standup_agent.tools.slack import (
    confirm_slack_publish,
    publish_standup_to_slack,
)

COORDINATOR_INSTRUCTIONS = """You coordinate standup generation.

IMPORTANT: You NEVER write standup summaries yourself. You MUST use the tools:
- Use gather_github_data tool to collect GitHub activity (also fetches Slack standups if configured)
- Use create_standup_summary tool to generate the standup (it has the user's style)

Workflow:
1. Call gather_github_data to collect GitHub activity
2. Call create_standup_summary with the collected data to create the standup
3. Return the summary to the user

For "copy to clipboard" or "save" requests: use those tools directly.
For refinement requests: call create_standup_summary again with the feedback.

For "publish to slack" requests:
1. First call publish_standup_to_slack WITHOUT confirmed=True - this shows a preview
2. Wait for user to confirm with words like "yes", "confirm", "publish it"
3. Call confirm_slack_publish, then call publish_standup_to_slack with confirmed=True

FEEDBACK DETECTION:
When the user expresses satisfaction or dissatisfaction with the standup, capture feedback:
- Positive signals: "good job", "thanks", "perfect", "great", "looks good", thumbs up, etc.
  → Call capture_feedback_rating with rating="good"
- Negative signals: "not great", "bad", "wrong", "missed something", thumbs down, etc.
  → Call capture_feedback_rating with rating="bad" and include reason as comment
- Detailed feedback: specific suggestions, corrections, or comments about formatting/style
  → Call capture_feedback_text with the user's feedback

Always acknowledge feedback briefly after capturing it.
Continue helping with any follow-up requests.
"""


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
        instructions=COORDINATOR_INSTRUCTIONS,
        tools=[
            # Sub-agents as tools for reliable execution
            data_gatherer.as_tool(
                tool_name="gather_github_data",
                tool_description="Gather GitHub activity data (PRs, issues, commits, reviews)",
            ),
            summarizer.as_tool(
                tool_name="create_standup_summary",
                tool_description="Create a standup summary from GitHub data with style prefs.",
            ),
            # Direct tools
            copy_to_clipboard,
            get_recent_standups,
            save_standup,
            save_standup_to_file,
            # Slack tools
            publish_standup_to_slack,
            confirm_slack_publish,
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
