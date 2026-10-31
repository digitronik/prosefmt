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
        assert "prosefmt" in result.output.lower()

    def test_help_shows_rewrite_options(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert "--mode" in result.output or "-m" in result.output

    def test_help_shows_available_modes(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert "fix" in result.output


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

    def test_list_empty_modes(self, runner):
        """list command should not crash when config has no modes."""
        with patch("prosefmt.config.Config.load") as mock_load:
            from prosefmt.config import Config

            cfg = Config()
            cfg.modes = {}
            mock_load.return_value = cfg
            result = runner.invoke(cli, ["list"])
            assert result.exit_code == 0
            assert "no modes" in result.output.lower()


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


class TestRewriteDefault:
    """Test the default rewrite command (no subcommand)."""

    def test_text_argument(self, runner):
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Fixed text."
            result = runner.invoke(cli, ["bad grammer"])
            assert result.exit_code == 0
            assert "Fixed text." in result.output

    def test_text_with_explicit_mode(self, runner):
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Pro text."
            result = runner.invoke(cli, ["-m", "professional", "text"])
            assert result.exit_code == 0
            assert "Pro text." in result.output

    def test_stdin_pipe(self, runner):
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Fixed text."
            result = runner.invoke(cli, [], input="bad grammer\n")
            assert result.exit_code == 0
            assert "Fixed text." in result.output

    def test_stdin_pipe_with_mode(self, runner):
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Casual text."
            result = runner.invoke(cli, ["-m", "casual"], input="text\n")
            assert result.exit_code == 0
            assert "Casual text." in result.output

    def test_unknown_mode(self, runner):
        result = runner.invoke(cli, ["-m", "nonexistent-mode", "text"])
        assert result.exit_code != 0

    def test_no_text_with_mode_shows_error(self, runner):
        with patch("prosefmt.clipboard.clipboard_read", return_value=""):
            result = runner.invoke(cli, ["-m", "fix", "-s"])
        assert result.exit_code != 0
        assert "no text" in result.output.lower()

    def test_provider_override(self, runner):
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Done."
            result = runner.invoke(cli, ["-p", "openai", "text"])
            assert result.exit_code == 0
            assert mock_gp.call_args[0][0] == "openai"

    def test_default_mode_is_fix(self, runner):
        """Without -m, the default mode 'fix' is used."""
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Fixed."
            result = runner.invoke(cli, ["text"])
            assert result.exit_code == 0
            # Verify the rewrite was called (mode resolution happens internally)
            mock_gp.return_value.complete.assert_called_once()

    def test_default_mode_from_config(self, runner, tmp_path, monkeypatch):
        """Config's default_mode is respected."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        cfg = tmp_path / "prosefmt" / "config.toml"
        cfg.parent.mkdir(parents=True)
        cfg.write_text('default_mode = "professional"\n')
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Pro."
            result = runner.invoke(cli, ["text"])
            assert result.exit_code == 0
            assert "Pro." in result.output


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
            runner.invoke(cli, ["original text"])

        result = runner.invoke(cli, ["undo"])
        assert result.exit_code == 0
        assert "original text" in result.output


class TestMenuCommand:
    def test_menu_selects_known_mode(self, runner):
        with (
            patch("prosefmt.picker.best_picker", return_value="rofi"),
            patch("prosefmt.picker.pick", return_value="fix"),
            patch("prosefmt.providers.get_provider") as mock_gp,
        ):
            mock_gp.return_value.complete.return_value = "Fixed text."
            result = runner.invoke(cli, ["menu", "bad grammer"])
            assert result.exit_code == 0
            assert "Fixed text." in result.output

    def test_menu_custom_prompt(self, runner):
        """User types a free-form prompt not in the mode list."""
        with (
            patch("prosefmt.picker.best_picker", return_value="rofi"),
            patch(
                "prosefmt.picker.pick",
                return_value="make it sound excited",
            ),
            patch("prosefmt.providers.get_provider") as mock_gp,
        ):
            mock_gp.return_value.complete.return_value = "Excited text!"
            result = runner.invoke(cli, ["menu", "some text"])
            assert result.exit_code == 0
            assert "Excited text!" in result.output

    def test_menu_cancelled_exits_cleanly(self, runner):
        with (
            patch("prosefmt.picker.best_picker", return_value="rofi"),
            patch("prosefmt.picker.pick", return_value=None),
        ):
            result = runner.invoke(cli, ["menu", "some text"])
            assert result.exit_code == 0

    def test_menu_no_picker_installed(self, runner):
        with patch("prosefmt.picker.best_picker", return_value=None):
            result = runner.invoke(cli, ["menu", "text"])
            assert result.exit_code != 0
            assert "picker" in result.output.lower() or "picker" in (result.stderr or "").lower()

    def test_menu_no_text_selected(self, runner):
        with patch("prosefmt.picker.best_picker", return_value="rofi"):
            result = runner.invoke(cli, ["menu"])
            assert result.exit_code != 0

    def test_menu_per_mode_provider_used(self, runner):
        with (
            patch("prosefmt.picker.best_picker", return_value="rofi"),
            patch("prosefmt.picker.pick", return_value="fix"),
            patch("prosefmt.providers.get_provider") as mock_gp,
        ):
            mock_gp.return_value.complete.return_value = "Done."
            runner.invoke(cli, ["menu", "text"])
            assert mock_gp.call_args[0][0] == "ollama"

    def test_menu_with_popup_flag(self, runner):
        with (
            patch("prosefmt.picker.best_picker", return_value="rofi"),
            patch("prosefmt.picker.pick", return_value="fix"),
            patch("prosefmt.providers.get_provider") as mock_gp,
            patch("prosefmt.popup.show_popup", return_value=True) as mock_popup,
        ):
            mock_gp.return_value.complete.return_value = "Fixed text."
            result = runner.invoke(cli, ["menu", "--popup", "text"])
            assert result.exit_code == 0
            mock_popup.assert_called_once()

    def test_menu_with_diff_flag(self, runner):
        with (
            patch("prosefmt.picker.best_picker", return_value="rofi"),
            patch("prosefmt.picker.pick", return_value="fix"),
            patch("prosefmt.providers.get_provider") as mock_gp,
        ):
            mock_gp.return_value.complete.return_value = "Fixed text."
            result = runner.invoke(cli, ["menu", "--diff", "bad text"])
            assert result.exit_code == 0


class TestPopupOutput:
    """Test --popup flag and default_output='popup' routing."""

    def test_popup_flag_shows_in_popup(self, runner):
        with (
            patch("prosefmt.providers.get_provider") as mock_gp,
            patch("prosefmt.popup.show_popup", return_value=True) as mock_popup,
        ):
            mock_gp.return_value.complete.return_value = "Fixed text."
            result = runner.invoke(cli, ["--popup", "bad grammer"])
            assert result.exit_code == 0
            mock_popup.assert_called_once()
            assert "Fixed text." in mock_popup.call_args[0][0]

    def test_popup_flag_falls_back_to_stdout_when_no_tool(self, runner):
        with (
            patch("prosefmt.providers.get_provider") as mock_gp,
            patch("prosefmt.popup.show_popup", return_value=False),
        ):
            mock_gp.return_value.complete.return_value = "Fixed text."
            result = runner.invoke(cli, ["--popup", "bad grammer"])
            assert result.exit_code == 0
            assert "Fixed text." in result.output

    def test_popup_with_diff(self, runner):
        with (
            patch("prosefmt.providers.get_provider") as mock_gp,
            patch("prosefmt.popup.show_popup", return_value=True) as mock_popup,
        ):
            mock_gp.return_value.complete.return_value = "Fixed text."
            result = runner.invoke(cli, ["--popup", "--diff", "bad grammer"])
            assert result.exit_code == 0
            mock_popup.assert_called_once()
            # Diff output should contain diff markers
            popup_text = mock_popup.call_args[0][0]
            assert "---" in popup_text or "(no changes)" in popup_text

    def test_default_output_popup_via_system_flag(self, runner, tmp_path, monkeypatch):
        """When --system is set and mode.default_output='popup', result goes to popup."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        cfg = tmp_path / "prosefmt" / "config.toml"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("""\
[modes.summarize]
prompt = "Summarize."
default_output = "popup"
""")
        with (
            patch("prosefmt.providers.get_provider") as mock_gp,
            patch("prosefmt.clipboard.clipboard_read", return_value="some long text"),
            patch("prosefmt.popup.show_popup", return_value=True) as mock_popup,
        ):
            mock_gp.return_value.complete.return_value = "Summary."
            result = runner.invoke(cli, ["-m", "summarize", "-s"])
            assert result.exit_code == 0
            mock_popup.assert_called_once()

    def test_popup_flag_overrides_default_output(self, runner):
        """--popup flag forces popup even if mode's default_output is 'replace'."""
        with (
            patch("prosefmt.providers.get_provider") as mock_gp,
            patch("prosefmt.popup.show_popup", return_value=True) as mock_popup,
        ):
            mock_gp.return_value.complete.return_value = "Fixed."
            result = runner.invoke(cli, ["-m", "fix", "--popup", "text"])
            assert result.exit_code == 0
            mock_popup.assert_called_once()


class TestDiffOutput:
    """Test --diff flag."""

    def test_diff_shows_changes(self, runner):
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Fixed text here."
            result = runner.invoke(cli, ["--diff", "bad text here"])
            assert result.exit_code == 0
            # Should contain diff markers
            assert "-" in result.output or "+" in result.output

    def test_diff_no_changes_message(self, runner):
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "same text"
            result = runner.invoke(cli, ["--diff", "same text"])
            assert result.exit_code == 0
            assert "(no changes)" in result.output

    def test_diff_with_mode(self, runner):
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Professional version."
            result = runner.invoke(cli, ["-m", "professional", "--diff", "casual version"])
            assert result.exit_code == 0
            assert result.output.strip() != ""

    def test_diff_via_stdin(self, runner):
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Fixed text."
            result = runner.invoke(cli, ["--diff"], input="bad text\n")
            assert result.exit_code == 0

    def test_diff_with_system_shows_diff_on_stdout(self, runner):
        """--diff + --system should show diff on stdout, NOT silently replace in-place."""
        with (
            patch("prosefmt.providers.get_provider") as mock_gp,
            patch("prosefmt.clipboard.clipboard_read", return_value="bad grammer"),
        ):
            mock_gp.return_value.complete.return_value = "bad grammar"
            result = runner.invoke(cli, ["--diff", "-s"])
            assert result.exit_code == 0
            # Diff should be visible in stdout (not silently pasted)
            assert "---" in result.output or "(no changes)" in result.output

    def test_diff_with_popup_disables_color(self, runner):
        """--diff + --popup should NOT include ANSI color codes in popup text."""
        with (
            patch("prosefmt.providers.get_provider") as mock_gp,
            patch("prosefmt.popup.show_popup", return_value=True) as mock_popup,
        ):
            mock_gp.return_value.complete.return_value = "Fixed text."
            result = runner.invoke(cli, ["--diff", "--popup", "bad text"])
            assert result.exit_code == 0
            popup_text = mock_popup.call_args[0][0]
            # ANSI escape codes must NOT appear in popup text
            assert "\033[" not in popup_text


class TestPerModeProviderOverride:
    def test_mode_provider_used_when_no_cli_flag(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        cfg = tmp_path / "prosefmt" / "config.toml"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("""\
[modes.review]
prompt = "Review this."
provider = "openai"
""")
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Review done."
            result = runner.invoke(cli, ["-m", "review", "some text"])
            assert result.exit_code == 0
            assert mock_gp.call_args[0][0] == "openai"

    def test_cli_flag_overrides_mode_provider(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        cfg = tmp_path / "prosefmt" / "config.toml"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("""\
[modes.review]
prompt = "Review this."
provider = "openai"
""")
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Done."
            runner.invoke(cli, ["-m", "review", "-p", "anthropic", "text"])
            assert mock_gp.call_args[0][0] == "anthropic"


class TestProviderTypeDispatch:
    """Test that custom provider names with a type field dispatch correctly."""

    def test_groq_with_openai_compat_type(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        cfg = tmp_path / "prosefmt" / "config.toml"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("""\
default_provider = "groq"

[providers.groq]
type = "openai-compat"
url = "https://api.groq.com/openai/v1"
model = "llama-3.3-70b-versatile"
""")
        with patch("prosefmt.providers.get_provider") as mock_gp:
            mock_gp.return_value.complete.return_value = "Done."
            result = runner.invoke(cli, ["text"])
            assert result.exit_code == 0
            # Provider name is "groq" but type-based dispatch should work
            assert mock_gp.call_args[0][0] == "groq"


class TestResolveOutput:
    """Test the output resolution logic as a pure function."""

    def test_popup_flag_wins(self):
        from prosefmt.cli import _resolve_output

        assert (
            _resolve_output(
                popup=True, show_diff=False, system=True, clipboard=False, default_output="replace"
            )
            == "popup"
        )

    def test_diff_with_system_forces_stdout(self):
        from prosefmt.cli import _resolve_output

        assert (
            _resolve_output(
                popup=False, show_diff=True, system=True, clipboard=False, default_output="replace"
            )
            == "stdout"
        )

    def test_system_uses_default_output(self):
        from prosefmt.cli import _resolve_output

        assert (
            _resolve_output(
                popup=False, show_diff=False, system=True, clipboard=False, default_output="popup"
            )
            == "popup"
        )

    def test_clipboard_flag(self):
        from prosefmt.cli import _resolve_output

        assert (
            _resolve_output(
                popup=False, show_diff=False, system=False, clipboard=True, default_output="replace"
            )
            == "clipboard"
        )

    def test_default_is_stdout(self):
        from prosefmt.cli import _resolve_output

        assert (
            _resolve_output(
                popup=False,
                show_diff=False,
                system=False,
                clipboard=False,
                default_output="replace",
            )
            == "stdout"
        )


class TestClipboardOutput:
    """Test --clipboard flag output routing."""

    def test_clipboard_output_writes_and_echoes(self, runner):
        with (
            patch("prosefmt.providers.get_provider") as mock_gp,
            patch("prosefmt.clipboard.clipboard_write") as mock_write,
        ):
            mock_gp.return_value.complete.return_value = "Fixed text."
            result = runner.invoke(cli, ["-c", "text"])
            assert result.exit_code == 0
            mock_write.assert_called_once_with("Fixed text.")
            assert "Fixed text." in result.output

    def test_clipboard_input_and_output(self, runner):
        with (
            patch("prosefmt.providers.get_provider") as mock_gp,
            patch("prosefmt.clipboard.clipboard_read", return_value="original"),
            patch("prosefmt.clipboard.clipboard_write") as mock_write,
        ):
            mock_gp.return_value.complete.return_value = "Fixed."
            result = runner.invoke(cli, ["-c"])
            assert result.exit_code == 0
            mock_write.assert_called_once_with("Fixed.")


class TestSystemOutput:
    """Test --system flag output routing (replace flow)."""

    def test_system_replace_pastes_back(self, runner):
        with (
            patch("prosefmt.providers.get_provider") as mock_gp,
            patch("prosefmt.clipboard.clipboard_read", return_value="original text"),
            patch("prosefmt.clipboard.clipboard_write"),
            patch("prosefmt.clipboard.paste_to_active_window", return_value=True),
            patch("prosefmt.clipboard.preserve_clipboard") as mock_ctx,
        ):
            mock_ctx.return_value.__enter__ = lambda s: None
            mock_ctx.return_value.__exit__ = lambda s, *a: False
            mock_gp.return_value.complete.return_value = "Fixed text."
            result = runner.invoke(cli, ["-s", "-m", "fix"])
            assert result.exit_code == 0

    def test_system_replace_fallback_no_paste_tool(self, runner):
        with (
            patch("prosefmt.providers.get_provider") as mock_gp,
            patch("prosefmt.clipboard.clipboard_read", return_value="original text"),
            patch("prosefmt.clipboard.clipboard_write"),
            patch("prosefmt.clipboard.paste_to_active_window", return_value=False),
            patch("prosefmt.clipboard.preserve_clipboard") as mock_ctx,
        ):
            mock_ctx.return_value.__enter__ = lambda s: None
            mock_ctx.return_value.__exit__ = lambda s, *a: False
            mock_gp.return_value.complete.return_value = "Fixed text."
            result = runner.invoke(cli, ["-s", "-m", "fix"])
            assert result.exit_code == 0
            assert "Fixed text." in result.output
            assert "paste" in result.output.lower()


class TestNotifyFlag:
    """Test --notify flag across different flows."""

    def test_notify_on_success(self, runner):
        with (
            patch("prosefmt.providers.get_provider") as mock_gp,
            patch("prosefmt.notify.notify") as mock_notify,
        ):
            mock_gp.return_value.complete.return_value = "Fixed."
            result = runner.invoke(cli, ["-n", "text"])
            assert result.exit_code == 0
            # At least one notification call should include the mode label
            assert mock_notify.call_count >= 1

    def test_notify_on_provider_error(self, runner):
        from prosefmt.providers.base import ProviderError

        with (
            patch("prosefmt.providers.get_provider") as mock_gp,
            patch("prosefmt.notify.notify") as mock_notify,
        ):
            mock_gp.return_value.complete.side_effect = ProviderError("model error")
            result = runner.invoke(cli, ["-n", "text"])
            assert result.exit_code != 0
            assert mock_notify.call_count >= 1


class TestConfigInitOverwrite:
    """Test config init overwrite flow."""

    def test_config_init_already_exists(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        # First init
        runner.invoke(cli, ["config", "init"])
        # Second init — should say "already exists"
        result = runner.invoke(cli, ["config", "init"], input="n\n")
        assert result.exit_code == 0
        assert "already exists" in result.output.lower() or "keeping" in result.output.lower()

    def test_config_init_overwrite_confirmed(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        runner.invoke(cli, ["config", "init"])
        result = runner.invoke(cli, ["config", "init"], input="y\n")
        assert result.exit_code == 0
        assert "restored" in result.output.lower() or "defaults" in result.output.lower()


class TestCheckCommand:
    def test_check_command(self, runner):
        result = runner.invoke(cli, ["check"])
        assert "clipboard" in result.output.lower() or "provider" in result.output.lower()

    def test_check_reports_picker(self, runner):
        with patch("prosefmt.picker.shutil.which", return_value="/usr/bin/rofi"):
            result = runner.invoke(cli, ["check"])
        assert "picker" in result.output.lower() or "rofi" in result.output.lower()

    def test_check_warns_no_picker(self, runner):
        with patch("prosefmt.picker.shutil.which", return_value=None):
            result = runner.invoke(cli, ["check"])
        assert "picker" in result.output.lower() or "menu" in result.output.lower()

    def test_check_reports_popup(self, runner):
        with (
            patch("prosefmt.popup.shutil.which", return_value="/usr/bin/zenity"),
            patch("prosefmt.picker.shutil.which", return_value="/usr/bin/rofi"),
        ):
            result = runner.invoke(cli, ["check"])
        assert "popup" in result.output.lower() or "zenity" in result.output.lower()

    def test_check_warns_no_popup(self, runner):
        with (
            patch("prosefmt.popup.shutil.which", return_value=None),
            patch("prosefmt.picker.shutil.which", return_value=None),
        ):
            result = runner.invoke(cli, ["check"])
        assert "popup" in result.output.lower()

    def test_check_provider_not_configured(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        cfg = tmp_path / "prosefmt" / "config.toml"
        cfg.parent.mkdir(parents=True)
        cfg.write_text('default_provider = "nonexistent"\n')
        result = runner.invoke(cli, ["check"])
        assert result.exit_code != 0
        assert "not configured" in result.output.lower() or "config init" in result.output.lower()
