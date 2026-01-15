"""Pytest fixtures for github-standup-agent tests."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from github_standup_agent.config import StandupConfig
from github_standup_agent.context import StandupContext


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory."""
    config_dir = tmp_path / ".config" / "standup-agent"
    config_dir.mkdir(parents=True)
    return config_dir


@pytest.fixture
def mock_config() -> StandupConfig:
    """Create a mock configuration."""
    return StandupConfig(
        github_username="testuser",
        default_days_back=1,
    )


@pytest.fixture
def mock_context(mock_config: StandupConfig) -> StandupContext:
    """Create a mock context."""
    return StandupContext(
        config=mock_config,
        days_back=1,
        github_username="testuser",
    )


@pytest.fixture
def sample_pr_response() -> str:
    """Sample JSON response for PR list."""
    return '''[
        {
            "number": 123,
            "title": "Add new feature",
            "url": "https://github.com/owner/repo/pull/123",
            "state": "MERGED",
            "createdAt": "2025-01-14T10:00:00Z",
            "updatedAt": "2025-01-15T10:00:00Z",
            "mergedAt": "2025-01-15T09:00:00Z",
            "additions": 100,
            "deletions": 50
        }
    ]'''


@pytest.fixture
def sample_issue_response() -> str:
    """Sample JSON response for issue list."""
    return '''[
        {
            "number": 456,
            "title": "Bug in login",
            "url": "https://github.com/owner/repo/issues/456",
            "state": "OPEN",
            "createdAt": "2025-01-14T10:00:00Z",
            "updatedAt": "2025-01-15T10:00:00Z",
            "labels": [{"name": "bug"}]
        }
    ]'''
