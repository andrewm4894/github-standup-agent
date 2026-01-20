"""Tools for capturing user feedback on standup quality."""

from typing import Annotated, Any, Literal

from agents import RunContextWrapper, function_tool
from agents.tracing import custom_span, get_current_trace

from github_standup_agent.context import StandupContext
from github_standup_agent.instrumentation import capture_ai_feedback, capture_ai_metric


@function_tool
def capture_feedback_rating(
    ctx: RunContextWrapper[StandupContext],
    rating: Annotated[
        Literal["good", "bad"], "Rating: 'good' for thumbs up, 'bad' for thumbs down"
    ],
    comment: Annotated[str | None, "Optional comment explaining the rating"] = None,
) -> str:
    """
    Capture user feedback rating (thumbs up/down) for the current standup.

    Use when the user indicates satisfaction or dissatisfaction with the generated standup.
    Examples: "good job", "thanks", "not great", "you missed something"
    """
    trace = get_current_trace()
    trace_id = trace.trace_id if trace else None

    # 1. Create SDK custom span (shows in trace view)
    span_data: dict[str, Any] = {"rating": rating, "type": "quality"}
    if comment:
        span_data["comment"] = comment
    with custom_span("feedback_rating", data=span_data):
        pass

    # 2. Emit PostHog $ai_metric event (for dashboards)
    if trace_id:
        capture_ai_metric(trace_id, "quality", rating, comment=comment)

    rating_text = "positive" if rating == "good" else "negative"
    if comment:
        return f"Captured {rating_text} feedback: {comment}"
    return f"Captured {rating_text} feedback"


@function_tool
def capture_feedback_text(
    ctx: RunContextWrapper[StandupContext],
    feedback: Annotated[str, "The feedback text from the user"],
) -> str:
    """
    Capture detailed text feedback about the current standup.

    Use when the user provides specific feedback, suggestions, or comments about
    the standup quality or formatting. Example: "the formatting is too verbose"
    """
    trace = get_current_trace()
    trace_id = trace.trace_id if trace else None

    # 1. Create SDK custom span (shows in trace view)
    with custom_span("feedback_text", data={"feedback": feedback}):
        pass

    # 2. Emit PostHog $ai_feedback event (for dashboards)
    if trace_id:
        capture_ai_feedback(trace_id, feedback)

    return "Feedback captured"
