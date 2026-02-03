"""Centralized prompt management for standup agents.

Loads prompt templates from .md files and compiles them with {{variable}} substitution.
Designed for future integration with PostHog LLM Analytics prompt management.
"""

import re
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"

# PostHog-compatible name pattern
_VALID_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


class PromptManager:
    """Manages loading and compiling prompt templates.

    Templates are .md files in the templates/ directory with {{variable}} placeholders.
    """

    _instance: "PromptManager | None" = None
    _cache: dict[str, str]

    def __new__(cls) -> "PromptManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache = {}
        return cls._instance

    def get(self, name: str, fallback: str | None = None) -> str:
        """Load a prompt template by name.

        Args:
            name: Template name (e.g., "coordinator-instructions"). Must match ^[a-zA-Z0-9_-]+$.
            fallback: Optional fallback string if template file is not found.

        Returns:
            The template content as a string.

        Raises:
            FileNotFoundError: If template doesn't exist and no fallback provided.
            ValueError: If name doesn't match the required pattern.
        """
        if not _VALID_NAME_RE.match(name):
            raise ValueError(f"Invalid prompt name '{name}': must match ^[a-zA-Z0-9_-]+$")

        if name in self._cache:
            return self._cache[name]

        path = TEMPLATES_DIR / f"{name}.md"
        if not path.exists():
            if fallback is not None:
                return fallback
            raise FileNotFoundError(f"Prompt template not found: {path}")

        content = path.read_text(encoding="utf-8")
        self._cache[name] = content
        return content

    def compile(self, template: str, variables: dict[str, str]) -> str:
        """Substitute {{var}} placeholders in a template string.

        Args:
            template: The template string with {{variable}} placeholders.
            variables: A dict mapping variable names to their values.

        Returns:
            The compiled string with all placeholders replaced.
        """
        result = template
        for key, value in variables.items():
            result = result.replace("{{" + key + "}}", value)
        return result

    def get_compiled(
        self,
        name: str,
        variables: dict[str, str],
        fallback: str | None = None,
    ) -> str:
        """Load a template and compile it with variables in one step.

        Args:
            name: Template name.
            variables: A dict mapping variable names to their values.
            fallback: Optional fallback string if template file is not found.

        Returns:
            The compiled prompt string.
        """
        template = self.get(name, fallback=fallback)
        return self.compile(template, variables)

    def clear_cache(self) -> None:
        """Clear the template cache."""
        self._cache.clear()


# Module-level convenience functions


def get_prompt(name: str, fallback: str | None = None) -> str:
    """Load a prompt template by name.

    Convenience wrapper around PromptManager().get().
    """
    return PromptManager().get(name, fallback=fallback)


def compile_prompt(name: str, variables: dict[str, str], fallback: str | None = None) -> str:
    """Load and compile a prompt template with variables.

    Convenience wrapper around PromptManager().get_compiled().
    """
    return PromptManager().get_compiled(name, variables, fallback=fallback)
