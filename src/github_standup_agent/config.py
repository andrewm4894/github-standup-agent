"""Configuration management for GitHub Standup Agent."""

import os
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir, user_data_dir
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default model for all agents
DEFAULT_MODEL = "gpt-5.2"

# Config directory - for config.json, style.md, examples.md
# Defaults to platform-specific user config directory, can be overridden with STANDUP_CONFIG_DIR
# Examples: ~/.config/github-standup-agent (Linux),
#           ~/Library/Application Support/github-standup-agent (macOS)
CONFIG_DIR = Path(
    os.environ.get("STANDUP_CONFIG_DIR", user_config_dir("github-standup-agent", appauthor=False))
)
CONFIG_FILE = CONFIG_DIR / "config.json"
STYLE_FILE = CONFIG_DIR / "style.md"
EXAMPLES_FILE = CONFIG_DIR / "examples.md"

# Data directory - for databases and runtime data
# Defaults to platform-specific user data directory, can be overridden with STANDUP_DATA_DIR
# Examples: ~/.local/share/github-standup-agent (Linux),
#           ~/Library/Application Support/github-standup-agent (macOS)
DATA_DIR = Path(
    os.environ.get("STANDUP_DATA_DIR", user_data_dir("github-standup-agent", appauthor=False))
)
DB_FILE = DATA_DIR / "standup_history.db"
SESSIONS_DB_FILE = DATA_DIR / "chat_sessions.db"


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
        """Load configuration from file and environment.

        Priority (highest to lowest):
        1. Environment variables / .env file
        2. Config file (CONFIG_DIR/config.json, defaults to user config directory)
        3. Default values
        """
        import json

        from dotenv import dotenv_values

        file_settings: dict[str, Any] = {}
        if CONFIG_FILE.exists():
            file_settings = json.loads(CONFIG_FILE.read_text())

        # Load env vars from .env file and environment
        # These take priority over file settings
        env_vars = {**dotenv_values(".env"), **os.environ}

        # Map of config field names to their env var names
        env_var_map = {
            "github_username": "STANDUP_GITHUB_USERNAME",
            "slack_channel": "STANDUP_SLACK_CHANNEL",
            "default_days_back": "STANDUP_DEFAULT_DAYS_BACK",
            "default_output": "STANDUP_DEFAULT_OUTPUT",
            "coordinator_model": "STANDUP_COORDINATOR_MODEL",
            "data_gatherer_model": "STANDUP_DATA_GATHERER_MODEL",
            "summarizer_model": "STANDUP_SUMMARIZER_MODEL",
            "temperature": "STANDUP_TEMPERATURE",
            "history_days_to_keep": "STANDUP_HISTORY_DAYS_TO_KEEP",
            "style_instructions": "STANDUP_STYLE_INSTRUCTIONS",
        }

        # Remove file settings for fields that have env vars set
        # This ensures env vars take priority
        for field_name, env_var_name in env_var_map.items():
            if env_var_name in env_vars and field_name in file_settings:
                del file_settings[field_name]

        return cls(**file_settings)

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
    """Find a config file in CONFIG_DIR."""
    config_file = CONFIG_DIR / filename
    if config_file.exists():
        return config_file
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
    """Create style.md by copying from style.example.md template."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Copy from example template if it exists
    example_file = CONFIG_DIR / "style.example.md"
    if example_file.exists():
        STYLE_FILE.write_text(example_file.read_text())
    else:
        # Fallback if no template
        STYLE_FILE.write_text("# Standup Style\n\nAdd your style instructions here.\n")

    return STYLE_FILE


def create_default_examples_file() -> Path:
    """Create examples.md by copying from examples.example.md template."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Copy from example template if it exists
    example_file = CONFIG_DIR / "examples.example.md"
    if example_file.exists():
        EXAMPLES_FILE.write_text(example_file.read_text())
    else:
        # Fallback if no template
        EXAMPLES_FILE.write_text("# Example Standups\n\nAdd example standups here.\n")

    return EXAMPLES_FILE
