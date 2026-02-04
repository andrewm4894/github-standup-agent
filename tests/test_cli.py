"""Tests for the CLI interface."""

import re

from typer.testing import CliRunner

from github_standup_agent.cli import app
from github_standup_agent import __version__

runner = CliRunner()

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def test_version():
    """Test that --version shows the version."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help():
    """Test that --help shows usage information."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "standup" in result.stdout.lower()


def test_config_show():
    """Test config --show command."""
    result = runner.invoke(app, ["config", "--show"])
    assert result.exit_code == 0
    assert "Configuration" in result.stdout


def test_generate_help():
    """Test that generate --help shows output options."""
    result = runner.invoke(app, ["generate", "--help"])
    assert result.exit_code == 0
    output = _strip_ansi(result.stdout)
    assert "stdout" in output
    assert "clipboard" in output
    assert "file" in output
    assert "--output-file" in output
