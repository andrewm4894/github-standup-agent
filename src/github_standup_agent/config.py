"""Configuration management for GitHub Standup Agent."""

import os
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Config directory
CONFIG_DIR = Path.home() / ".config" / "standup-agent"

# Default model for all agents
DEFAULT_MODEL = "gpt-5.2"
CONFIG_FILE = CONFIG_DIR / "config.json"
DB_FILE = CONFIG_DIR / "standup_history.db"
STYLE_FILE = CONFIG_DIR / "style.md"
EXAMPLES_FILE = CONFIG_DIR / "examples.md"
SESSIONS_DB_FILE = CONFIG_DIR / "chat_sessions.db"


class StandupConfig(BaseSettings):
    """Configuration for the standup agent."""

    model_config = SettingsConfigDict(
        env_prefix="STANDUP_",
        env_file=".env",
        extra="ignore",
    )

    # API Key (required)
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
    )

    # GitHub settings
    github_username: str | None = None  # Auto-detected from `gh auth status` if not set

    # Slack settings
    slack_bot_token: SecretStr | None = Field(
        default=None,
        validation_alias="STANDUP_SLACK_BOT_TOKEN",
    )
    slack_channel: str | None = None  # Channel name (without #) or channel ID

    # Agent settings
    default_days_back: int = 1
    default_output: str = "stdout"  # stdout, clipboard
    coordinator_model: str = DEFAULT_MODEL
    data_gatherer_model: str = DEFAULT_MODEL
    summarizer_model: str = DEFAULT_MODEL
    temperature: float = 0.7

    # Repos to include/exclude (empty = all)
    include_repos: list[str] = Field(default_factory=list)
    exclude_repos: list[str] = Field(default_factory=list)

    # History settings
    history_days_to_keep: int = 30

    # Style customization (short instructions, use style.md file for detailed customization)
    style_instructions: str | None = None

    def save(self) -> None:
        """Save configuration to file."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        # Don't save secrets to file for security
        CONFIG_FILE.write_text(
            self.model_dump_json(indent=2, exclude={"openai_api_key", "slack_bot_token"})
        )

    @classmethod
    def load(cls) -> "StandupConfig":
        """Load configuration from file and environment."""
        if CONFIG_FILE.exists():
            file_config = CONFIG_FILE.read_text()
            return cls.model_validate_json(file_config)
        return cls()

    def get_api_key(self) -> str:
        """Get the OpenAI API key, raising an error if not set."""
        if self.openai_api_key is None:
            # Check environment directly as fallback
            env_key = os.getenv("OPENAI_API_KEY")
            if env_key:
                return env_key
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable "
                "or use `standup config --set-openai-key`"
            )
        return self.openai_api_key.get_secret_value()

    def get_slack_token(self) -> str | None:
        """Get the Slack bot token, returning None if not set."""
        if self.slack_bot_token is None:
            # Check environment directly as fallback
            return os.getenv("STANDUP_SLACK_BOT_TOKEN")
        return self.slack_bot_token.get_secret_value()

    def is_slack_enabled(self) -> bool:
        """Check if Slack integration is properly configured."""
        return bool(self.get_slack_token() and self.slack_channel)


def get_github_username() -> str | None:
    """Get the GitHub username from gh CLI."""
    import subprocess

    try:
        result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _find_file(filename: str) -> Path | None:
    """Find a config file, checking local directory first, then global config."""
    # Check current working directory first (for repo-local config)
    local_file = Path.cwd() / filename
    if local_file.exists():
        return local_file

    # Fall back to global config directory
    global_file = CONFIG_DIR / filename
    if global_file.exists():
        return global_file

    return None


def load_style_from_file() -> tuple[str | None, Path | None]:
    """Load custom style instructions from style.md file.

    Returns:
        Tuple of (content, path) where path indicates where the file was found.
    """
    style_path = _find_file("style.md")
    if style_path:
        content = style_path.read_text().strip()
        if content:
            return content, style_path
    return None, None


def load_examples_from_file() -> tuple[str | None, Path | None]:
    """Load example standups from examples.md file.

    Returns:
        Tuple of (content, path) where path indicates where the file was found.
    """
    examples_path = _find_file("examples.md")
    if examples_path:
        content = examples_path.read_text().strip()
        if content:
            return content, examples_path
    return None, None


def get_combined_style_instructions(config: StandupConfig) -> str | None:
    """
    Get combined style instructions from config and style file.

    Priority: style.md file content + config.style_instructions + examples.md
    All are combined if present.
    """
    parts = []

    # Load from file first (primary source for detailed instructions)
    file_style, _ = load_style_from_file()
    if file_style:
        parts.append(file_style)

    # Add config style instructions (good for quick overrides)
    if config.style_instructions:
        parts.append(config.style_instructions)

    # Add examples if present (few-shot prompting)
    examples, _ = load_examples_from_file()
    if examples:
        examples_section = (
            f"## Example Standups\n\nUse these as reference for tone and format:\n\n{examples}"
        )
        parts.append(examples_section)

    if parts:
        return "\n\n".join(parts)
    return None


def create_default_style_file() -> Path:
    """Create a default style.md file with example content."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    default_content = """# Standup Style Customization

Customize how your standup summaries are generated by editing this file.
The instructions here will be passed to the AI summarizer.

## Example Instructions (uncomment and modify as needed):

# - Keep summaries very concise (3-5 bullet points max)
# - Use emoji for status: ✅ merged, 🔄 in progress, 🚧 blocked
# - Group items by project/repo instead of activity type
# - Skip the blockers section unless there's something critical
# - Focus on outcomes and impact, not just what was done
# - Include PR/issue numbers as links
# - Use past tense for completed work, present for ongoing

## Your Custom Instructions:

"""
    STYLE_FILE.write_text(default_content)
    return STYLE_FILE


def create_default_examples_file() -> Path:
    """Create a default examples.md file with placeholder content."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    default_content = """# Example Standups

Add real examples of standups you like here. The AI will use these as reference
for tone, format, and level of detail. This is essentially "few-shot prompting".

## Example 1

```
Did:
- merged js sdk for llma / error tracking - pr
- added prom metrics for nodejs ai processing stuff - pr
- deep dive on why my code not deployed - learned some stuff - thread in dev
- refactored eval pr to add NA option following Carlos suggestion - pr

Will Do:
- if get clustering pr3 merged then will manually register both temporal workflows in prod
- docs and next steps for errors tab out of alpha work
- try get this bugfix merged to js - pr
```

## Example 2

```
Did:
- PR reviews
- Session with Steven to explain all things LLMA related
- GA plans (context)
- Working on a way to not always re-run the queries for traces/generations

Will do:
- Richard onboarding session
- Prompt management SDK work
- Review docs examples for wizard (context)
- Add access control to LLMA (context)
```

---
Add your own examples below, or replace the examples above:

"""
    EXAMPLES_FILE.write_text(default_content)
    return EXAMPLES_FILE
