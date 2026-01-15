"""Input guardrails for validating user input."""

from typing import Any

from agents import (
    Agent,
    GuardrailFunctionOutput,
    InputGuardrail,
    RunContextWrapper,
)

from github_standup_agent.context import StandupContext


async def validate_days_range(
    ctx: RunContextWrapper[StandupContext],
    agent: Agent[Any],
    input_data: Any,
) -> GuardrailFunctionOutput:
    """
    Validate that the days_back value is within a reasonable range.

    This prevents excessive API calls and ensures sensible date ranges.
    """
    days_back = ctx.context.days_back

    if days_back < 1:
        return GuardrailFunctionOutput(
            output_info={"error": "days_back must be at least 1"},
            tripwire_triggered=True,
        )

    if days_back > 30:
        return GuardrailFunctionOutput(
            output_info={"warning": "Looking back more than 30 days may be slow"},
            tripwire_triggered=False,
        )

    return GuardrailFunctionOutput(
        output_info={"days_back": days_back},
        tripwire_triggered=False,
    )


# Create the guardrail
validate_days_guardrail = InputGuardrail(
    guardrail_function=validate_days_range,
    name="validate_days_range",
)
