"""Output guardrails for validating generated content."""

import re
from typing import Any

from agents import (
    Agent,
    GuardrailFunctionOutput,
    OutputGuardrail,
    RunContextWrapper,
)

from github_standup_agent.context import StandupContext

# Patterns that might indicate sensitive information
PII_PATTERNS = [
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
    r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # Phone number
    r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b",  # GitHub tokens
    r"\bsk-[A-Za-z0-9]{32,}\b",  # OpenAI API keys
    r'\b(?:api[_-]?key|secret|password|token)\s*[=:]\s*["\']?[A-Za-z0-9]{16,}["\']?\b',
]


async def check_for_pii(
    ctx: RunContextWrapper[StandupContext],
    agent: Agent[Any],
    output: Any,
) -> GuardrailFunctionOutput:
    """
    Check the output for potential PII or sensitive information.

    This helps prevent accidentally sharing secrets or personal data.
    """
    warnings = []
    output_text = str(output)

    for pattern in PII_PATTERNS:
        matches = re.findall(pattern, output_text, re.IGNORECASE)
        if matches:
            # Don't include the actual matches in the warning
            warnings.append(f"Potential sensitive data detected (pattern: {pattern[:20]}...)")

    if warnings:
        return GuardrailFunctionOutput(
            output_info={"warnings": warnings},
            tripwire_triggered=False,  # Warn but don't block
        )

    return GuardrailFunctionOutput(
        output_info={"status": "clean"},
        tripwire_triggered=False,
    )


# Create the guardrail
pii_check_guardrail = OutputGuardrail(
    guardrail_function=check_for_pii,
    name="pii_check",
)
