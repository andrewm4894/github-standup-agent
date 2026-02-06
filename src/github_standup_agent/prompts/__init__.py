"""Centralized prompt management for standup agents.

Loads prompt templates from .md files and compiles them with {{variable}} substitution.
When POSTHOG_PERSONAL_API_KEY is set, fetches prompts from PostHog prompt management
with local .md files as fallbacks.
"""

import os
import re
import sys
from pathlib import Path
from typing import Any

TEMPLATES_DIR = Path(__file__).parent / "templates"

# PostHog-compatible name pattern
_VALID_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


class PromptManager:
    """Manages loading and compiling prompt templates.

    Templates are .md files in the templates/ directory with {{variable}} placeholders.
    When PostHog prompt management is configured (POSTHOG_PERSONAL_API_KEY),
    prompts are fetched from PostHog with local files as fallbacks.
    """

    _instance: "PromptManager | None" = None
    _cache: dict[str, str]
    _posthog_prompts: Any
    _posthog_init_attempted: bool

    def __new__(cls) -> "PromptManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cache = {}
            cls._instance._posthog_prompts = None
            cls._instance._posthog_init_attempted = False
        return cls._instance

    def _get_posthog_prompts(self) -> Any:
        """Lazily initialize PostHog Prompts client if configured.

        Returns the Prompts instance or None if not configured / not installed.
        """
        if self._posthog_init_attempted:
            return self._posthog_prompts

        self._posthog_init_attempted = True

        personal_api_key = os.getenv("POSTHOG_PERSONAL_API_KEY")
        if not personal_api_key:
            return None

        try:
            from posthog.ai.prompts import Prompts

            host = os.getenv("POSTHOG_HOST", "https://us.posthog.com")
            self._posthog_prompts = Prompts(
                personal_api_key=personal_api_key,
                host=host,
            )
            return self._posthog_prompts
        except ImportError:
            return None
        except Exception as e:
            print(f"[PostHog Prompts] Warning: Failed to initialize: {e}", file=sys.stderr)
            return None

    def _get_local(self, name: str, fallback: str | None = None) -> str:
        """Load a prompt template from local .md file.

        Args:
            name: Template name (already validated).
            fallback: Optional fallback string if template file is not found.

        Returns:
            The template content as a string.

        Raises:
            FileNotFoundError: If template doesn't exist and no fallback provided.
        """
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

    def get(self, name: str, fallback: str | None = None) -> str:
        """Load a prompt template by name.

        When PostHog prompt management is configured, fetches from PostHog API
        with local .md file content as fallback. Otherwise uses local files directly.

        Args:
            name: Template name (e.g., "standup-agent-instructions"). Must match ^[a-zA-Z0-9_-]+$.
            fallback: Optional fallback string if template file is not found.

        Returns:
            The template content as a string.

        Raises:
            FileNotFoundError: If template doesn't exist and no fallback provided.
            ValueError: If name doesn't match the required pattern.
        """
        if not _VALID_NAME_RE.match(name):
            raise ValueError(f"Invalid prompt name '{name}': must match ^[a-zA-Z0-9_-]+$")

        ph = self._get_posthog_prompts()
        if ph is not None:
            local_content = self._get_local(name, fallback=fallback)
            try:
                # Don't pass fallback to SDK so it raises on failure,
                # allowing us to log a visible warning before falling back.
                result: str = ph.get(name)
                return result
            except Exception as e:
                msg = f"[PostHog Prompts] Failed to fetch '{name}', using local fallback: {e}"
                print(msg, file=sys.stderr)
                return local_content

        # No PostHog configured - use local files (existing behavior)
        return self._get_local(name, fallback=fallback)

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
        """Clear the template cache and reset PostHog client."""
        self._cache.clear()
        self._posthog_prompts = None
        self._posthog_init_attempted = False


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
