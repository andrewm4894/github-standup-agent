"""Tests for the GitHub PRs tool."""

import json
from unittest.mock import patch, MagicMock

import pytest

from github_standup_agent.context import StandupContext
from github_standup_agent.config import StandupConfig


def test_context_stores_prs(mock_context: StandupContext):
    """Test that PRs are stored in context."""
    # Initially empty
    assert mock_context.collected_prs == []

    # After adding data
    mock_context.collected_prs = [{"number": 1, "title": "Test PR"}]
    assert len(mock_context.collected_prs) == 1
    assert mock_context.collected_prs[0]["number"] == 1
