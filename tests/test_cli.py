"""Tests for the CLI interface."""

from typer.testing import CliRunner

from github_standup_agent.cli import app
from github_standup_agent import __version__

runner = CliRunner()


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
    assert "stdout" in result.stdout
    assert "clipboard" in result.stdout
    assert "file" in result.stdout
    assert "--output-file" in result.stdout
