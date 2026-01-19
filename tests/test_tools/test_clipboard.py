"""Tests for the clipboard tool."""

from unittest.mock import patch, MagicMock

import pytest

from github_standup_agent.context import StandupContext
from github_standup_agent.config import StandupConfig

from .conftest import invoke_tool


class TestCopyToClipboard:
    """Tests for copy_to_clipboard tool."""

    @patch("pyperclip.copy")
    def test_copy_explicit_text(self, mock_copy, mock_context):
        """Test copying explicit text to clipboard."""
        from github_standup_agent.tools.clipboard import copy_to_clipboard

        result = invoke_tool(copy_to_clipboard, mock_context, text="Hello, world!")

        assert "Copied to clipboard" in result
        mock_copy.assert_called_once_with("Hello, world!")

    @patch("pyperclip.copy")
    def test_copy_current_standup(self, mock_copy, mock_context):
        """Test copying current standup when no text provided."""
        from github_standup_agent.tools.clipboard import copy_to_clipboard

        mock_context.current_standup = "My standup summary"
        result = invoke_tool(copy_to_clipboard, mock_context, text=None)

        assert "Copied to clipboard" in result
        mock_copy.assert_called_once_with("My standup summary")

    def test_copy_no_content(self, mock_context):
        """Test copy with no content available."""
        from github_standup_agent.tools.clipboard import copy_to_clipboard

        mock_context.current_standup = None
        result = invoke_tool(copy_to_clipboard, mock_context, text=None)

        assert "No content to copy" in result

    @patch("pyperclip.copy")
    def test_copy_pyperclip_error(self, mock_copy, mock_context):
        """Test handling pyperclip errors."""
        import pyperclip
        from github_standup_agent.tools.clipboard import copy_to_clipboard

        mock_copy.side_effect = pyperclip.PyperclipException("No clipboard")

        result = invoke_tool(copy_to_clipboard, mock_context, text="test")

        assert "Failed to copy" in result
