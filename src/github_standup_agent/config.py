"""Configuration management for GitHub Standup Agent."""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Config directory
CONFIG_DIR = Path.home() / ".config" / "standup-agent"
CONFIG_FILE = CONFIG_DIR / "config.json"
DB_FILE = CONFIG_DIR / "standup_history.db"


class StandupConfig(BaseSettings):
    """Configuration for the standup agent."""

    model_config = SettingsConfigDict(
        env_prefix="STANDUP_",
        env_file=".env",
        extra="ignore",
    )

    # API Key (required)
    openai_api_key: Optional[SecretStr] = Field(
        default=None,
        validation_alias="OPENAI_API_KEY",
    )

    # GitHub settings
    github_username: Optional[str] = None  # Auto-detected from `gh auth status` if not set

    # Agent settings
    default_days_back: int = 1
    default_output: str = "stdout"  # stdout, clipboard
    coordinator_model: str = "gpt-4o"
    data_gatherer_model: str = "gpt-4o-mini"
    summarizer_model: str = "gpt-4o"
    temperature: float = 0.7

    # Repos to include/exclude (empty = all)
    include_repos: list[str] = Field(default_factory=list)
    exclude_repos: list[str] = Field(default_factory=list)

    # History settings
    history_days_to_keep: int = 30

    def save(self) -> None:
        """Save configuration to file."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        # Don't save the API key to file for security
        data = self.model_dump(exclude={"openai_api_key"})
        CONFIG_FILE.write_text(
            self.model_dump_json(indent=2, exclude={"openai_api_key"})
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


def get_github_username() -> Optional[str]:
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
