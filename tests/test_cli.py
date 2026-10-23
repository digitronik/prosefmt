"""Tests for the CLI interface."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from prosefmt.cli import cli


@pytest.fixture()
def runner():
    return CliRunner()


class TestCLIBasics:
    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "prosefmt" in result.output.lower()

    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "prosefmt" in result.output.lower() or result.output.strip()

    def test_no_args_shows_help(self, runner):
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "Usage" in result.output


class TestListCommand:
    def test_list_modes(self, runner):
        result = runner.invoke(cli, ["list"])
        assert result.exit_code == 0
        assert "fix" in result.output
        assert "professional" in result.output
        assert "summarize" in result.output

    def test_list_names(self, runner):
        result = runner.invoke(cli, ["list", "--names"])
        assert result.exit_code == 0
        lines = result.output.strip().splitlines()
        assert lines
        assert all(" " not in line and ":" not in line for line in lines)
        assert lines[0] == "fix"
        assert "summarize" in lines


class TestConfigCommand:
    def test_config_show(self, runner):
        result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        assert "ollama" in result.output

    def test_config_init(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        result = runner.invoke(cli, ["config", "init"])
        assert result.exit_code == 0
        assert "config" in result.output.lower()


class TestModeCommands:
    def test_fix_with_text(self, runner):
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Fixed text."
            result = runner.invoke(cli, ["fix", "bad grammer"])
            assert result.exit_code == 0
            assert "Fixed text." in result.output

    def test_fix_from_stdin(self, runner):
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Fixed text."
            result = runner.invoke(cli, ["fix"], input="bad grammer\n")
            assert result.exit_code == 0
            assert "Fixed text." in result.output

    def test_unknown_mode(self, runner):
        result = runner.invoke(cli, ["nonexistent-mode", "text"])
        assert result.exit_code != 0

    def test_no_text_shows_error(self, runner):
        result = runner.invoke(cli, ["fix"])
        assert result.exit_code != 0
        assert "no text" in result.output.lower()

    def test_provider_override(self, runner):
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Done."
            result = runner.invoke(cli, ["fix", "--provider", "openai", "text"])
            assert result.exit_code == 0
            call_args = mock_gp.call_args
            assert call_args[0][0] == "openai"


class TestUndoCommand:
    def test_undo_nothing(self, runner):
        with patch("prosefmt.core.load_undo", return_value=None):
            result = runner.invoke(cli, ["undo"])
            assert result.exit_code != 0
            assert "nothing" in result.output.lower()

    def test_undo_after_rewrite(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Fixed."
            runner.invoke(cli, ["fix", "original text"])

        result = runner.invoke(cli, ["undo"])
        assert result.exit_code == 0
        assert "original text" in result.output


class TestCheckCommand:
    def test_check_command(self, runner):
        result = runner.invoke(cli, ["check"])
        assert "clipboard" in result.output.lower() or "provider" in result.output.lower()
