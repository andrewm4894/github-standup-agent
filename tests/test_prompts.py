"""Tests for the prompts module."""

import pytest

from github_standup_agent.prompts import PromptManager, compile_prompt, get_prompt


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Clear PromptManager cache before each test."""
    PromptManager().clear_cache()


class TestPromptManager:
    """Tests for the PromptManager class."""

    def test_singleton(self) -> None:
        """PromptManager returns the same instance."""
        a = PromptManager()
        b = PromptManager()
        assert a is b

    def test_get_existing_template(self) -> None:
        """Can load a known template file."""
        result = get_prompt("coordinator-instructions")
        assert "coordinate standup generation" in result

    def test_get_all_templates(self) -> None:
        """All expected templates load without error."""
        names = [
            "coordinator-instructions",
            "data-gatherer-instructions",
            "summarizer-instructions",
            "summarizer-custom-style",
            "summarizer-current-standup",
            "generate-standup",
            "chat-context",
        ]
        for name in names:
            result = get_prompt(name)
            assert len(result) > 0, f"Template '{name}' is empty"

    def test_get_missing_template_raises(self) -> None:
        """FileNotFoundError raised for missing template without fallback."""
        with pytest.raises(FileNotFoundError):
            get_prompt("nonexistent-template")

    def test_get_missing_template_with_fallback(self) -> None:
        """Fallback string returned when template is missing."""
        result = get_prompt("nonexistent-template", fallback="default text")
        assert result == "default text"

    def test_invalid_name_raises(self) -> None:
        """ValueError raised for names with invalid characters."""
        with pytest.raises(ValueError, match="Invalid prompt name"):
            get_prompt("invalid name with spaces")

    def test_invalid_name_special_chars(self) -> None:
        """ValueError raised for names with special characters."""
        with pytest.raises(ValueError, match="Invalid prompt name"):
            get_prompt("bad/name")

    def test_caching(self) -> None:
        """Second load uses cache."""
        manager = PromptManager()
        result1 = manager.get("coordinator-instructions")
        result2 = manager.get("coordinator-instructions")
        assert result1 is result2  # Same object, not just equal

    def test_clear_cache(self) -> None:
        """Cache can be cleared."""
        manager = PromptManager()
        result1 = manager.get("coordinator-instructions")
        manager.clear_cache()
        result2 = manager.get("coordinator-instructions")
        assert result1 == result2
        assert result1 is not result2  # Different objects after cache clear

    def test_compile_simple(self) -> None:
        """Compile substitutes variables."""
        manager = PromptManager()
        result = manager.compile("Hello {{name}}", {"name": "World"})
        assert result == "Hello World"

    def test_compile_multiple_vars(self) -> None:
        """Compile handles multiple variables."""
        manager = PromptManager()
        template = "{{a}} and {{b}}"
        result = manager.compile(template, {"a": "X", "b": "Y"})
        assert result == "X and Y"

    def test_compile_no_vars(self) -> None:
        """Compile with empty dict returns template unchanged."""
        manager = PromptManager()
        template = "No variables here"
        result = manager.compile(template, {})
        assert result == template

    def test_compile_missing_var_left_as_is(self) -> None:
        """Variables not in dict are left as {{var}} placeholders."""
        manager = PromptManager()
        result = manager.compile("Hello {{name}}", {})
        assert result == "Hello {{name}}"

    def test_get_compiled(self) -> None:
        """get_compiled loads and compiles in one step."""
        result = compile_prompt("generate-standup", {"days_back": "3"})
        assert "3 day(s)" in result

    def test_get_compiled_chat_context(self) -> None:
        """chat-context template compiles with all variables."""
        result = compile_prompt(
            "chat-context",
            {
                "github_username": "testuser",
                "days_back": "7",
                "user_input": "generate my standup",
            },
        )
        assert "testuser" in result
        assert "7" in result
        assert "generate my standup" in result

    def test_get_compiled_summarizer_custom_style(self) -> None:
        """summarizer-custom-style template compiles with custom_style."""
        result = compile_prompt(
            "summarizer-custom-style",
            {"custom_style": "Be very concise."},
        )
        assert "Be very concise." in result
        assert "CRITICAL FORMATTING REQUIREMENTS" in result

    def test_get_compiled_summarizer_current_standup(self) -> None:
        """summarizer-current-standup template compiles with current_standup."""
        result = compile_prompt(
            "summarizer-current-standup",
            {"current_standup": "Did:\n- Fixed a bug"},
        )
        assert "Did:\n- Fixed a bug" in result
        assert "CURRENT STANDUP" in result
