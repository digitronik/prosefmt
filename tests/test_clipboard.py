"""Tests for clipboard platform detection, selection dispatch, and save/restore."""

from __future__ import annotations

from unittest.mock import call, patch

from prosefmt.clipboard import (
    _run_stdin,
    _run_stdout,
    check_clipboard_tools,
    clipboard_read,
    clipboard_write,
    install_hints,
    paste_to_active_window,
    preserve_clipboard,
)
from prosefmt.platform import Platform, PlatformInfo


class TestPlatformDetection:
    """Platform detection tests live in test_platform.py.

    These tests verify that clipboard functions correctly dispatch
    based on the detected platform.
    """

    def test_x11_dispatch(self, monkeypatch):
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        with patch("prosefmt.platform.platform.system", return_value="Linux"):
            from prosefmt.platform import detect_platform

            assert detect_platform() == Platform.LINUX_X11

    def test_wayland_dispatch(self, monkeypatch):
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        with patch("prosefmt.platform.platform.system", return_value="Linux"):
            from prosefmt.platform import detect_platform

            assert detect_platform() == Platform.LINUX_WAYLAND


class TestCheckTools:
    def test_reports_missing_xclip(self, monkeypatch):
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_X11),
            patch("prosefmt.clipboard.shutil.which", return_value=None),
        ):
            missing = check_clipboard_tools()
            assert "xclip" in missing
            assert "xdotool" in missing

    def test_no_missing_on_macos(self):
        with patch("prosefmt.clipboard.detect_platform", return_value=Platform.MACOS):
            assert check_clipboard_tools() == []


class TestClipboardReadSelection:
    """Tests for the ``selection`` parameter on ``clipboard_read``."""

    # -- X11 -------------------------------------------------------------------

    def test_x11_auto_prefers_primary(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_X11),
            patch(
                "prosefmt.clipboard._run_stdout",
                side_effect=lambda cmd: "highlighted" if "primary" in cmd else "copied",
            ),
        ):
            assert clipboard_read() == "highlighted"

    def test_x11_auto_falls_back_to_clipboard(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_X11),
            patch(
                "prosefmt.clipboard._run_stdout",
                side_effect=lambda cmd: "" if "primary" in cmd else "copied",
            ),
        ):
            assert clipboard_read() == "copied"

    def test_x11_explicit_primary(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_X11),
            patch("prosefmt.clipboard._run_stdout", return_value="selected") as mock,
        ):
            assert clipboard_read(selection="primary") == "selected"
            mock.assert_called_once_with(["xclip", "-o", "-selection", "primary"])

    def test_x11_explicit_clipboard(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_X11),
            patch("prosefmt.clipboard._run_stdout", return_value="copied") as mock,
        ):
            assert clipboard_read(selection="clipboard") == "copied"
            mock.assert_called_once_with(["xclip", "-o", "-selection", "clipboard"])

    # -- Wayland ---------------------------------------------------------------

    def test_wayland_primary_uses_flag(self):
        """The Wayland bug fix: --primary must be passed to wl-paste."""
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_WAYLAND),
            patch("prosefmt.clipboard._run_stdout", return_value="selected") as mock,
        ):
            assert clipboard_read(selection="primary") == "selected"
            mock.assert_called_once_with(["wl-paste", "--primary", "--no-newline"])

    def test_wayland_auto_prefers_primary(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_WAYLAND),
            patch(
                "prosefmt.clipboard._run_stdout",
                side_effect=lambda cmd: "highlighted" if "--primary" in cmd else "copied",
            ),
        ):
            assert clipboard_read() == "highlighted"

    def test_wayland_auto_falls_back_to_clipboard(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_WAYLAND),
            patch(
                "prosefmt.clipboard._run_stdout",
                side_effect=lambda cmd: "" if "--primary" in cmd else "copied",
            ),
        ):
            assert clipboard_read() == "copied"

    def test_wayland_explicit_clipboard(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_WAYLAND),
            patch("prosefmt.clipboard._run_stdout", return_value="text") as mock,
        ):
            assert clipboard_read(selection="clipboard") == "text"
            mock.assert_called_once_with(["wl-paste", "--no-newline"])

    # -- macOS / Windows -------------------------------------------------------

    def test_macos_ignores_selection(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.MACOS),
            patch("prosefmt.clipboard._run_stdout", return_value="text"),
        ):
            for sel in ("auto", "primary", "clipboard"):
                assert clipboard_read(selection=sel) == "text"

    def test_windows_ignores_selection(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.WINDOWS),
            patch("prosefmt.clipboard._run_stdout", return_value="text"),
        ):
            for sel in ("auto", "primary", "clipboard"):
                assert clipboard_read(selection=sel) == "text"


class TestPasteToActiveWindow:
    """Tests for paste_to_active_window return value."""

    def test_returns_true_on_x11(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_X11),
            patch("prosefmt.clipboard.subprocess.run"),
        ):
            assert paste_to_active_window() is True

    def test_returns_true_on_macos(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.MACOS),
            patch("prosefmt.clipboard.subprocess.run"),
        ):
            assert paste_to_active_window() is True

    def test_returns_true_on_windows(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.WINDOWS),
            patch("prosefmt.clipboard.subprocess.run"),
        ):
            assert paste_to_active_window() is True

    def test_wayland_returns_true_with_wtype(self):
        def _which(c: str) -> str | None:
            return "/usr/bin/wtype" if c == "wtype" else None

        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_WAYLAND),
            patch("prosefmt.clipboard.shutil.which", side_effect=_which),
            patch("prosefmt.clipboard.subprocess.run"),
        ):
            assert paste_to_active_window() is True

    def test_wayland_returns_true_with_ydotool(self):
        def _which(c: str) -> str | None:
            return "/usr/bin/ydotool" if c == "ydotool" else None

        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_WAYLAND),
            patch("prosefmt.clipboard.shutil.which", side_effect=_which),
            patch("prosefmt.clipboard.subprocess.run"),
        ):
            assert paste_to_active_window() is True

    def test_wayland_returns_false_no_paste_tool(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_WAYLAND),
            patch("prosefmt.clipboard.shutil.which", return_value=None),
        ):
            assert paste_to_active_window() is False

    def test_unknown_returns_false(self):
        with patch("prosefmt.clipboard.detect_platform", return_value=Platform.UNKNOWN):
            assert paste_to_active_window() is False


class TestPreserveClipboard:
    """Tests for the save/restore context manager."""

    def test_restores_old_clipboard(self):
        with (
            patch("prosefmt.clipboard.clipboard_read", return_value="old content"),
            patch("prosefmt.clipboard.clipboard_write") as mock_write,
            patch("prosefmt.clipboard.time.sleep"),
        ):
            with preserve_clipboard():
                mock_write("new content")

            assert mock_write.call_args_list == [call("new content"), call("old content")]

    def test_skips_restore_when_clipboard_was_empty(self):
        with (
            patch("prosefmt.clipboard.clipboard_read", return_value=""),
            patch("prosefmt.clipboard.clipboard_write") as mock_write,
            patch("prosefmt.clipboard.time.sleep"),
        ):
            with preserve_clipboard():
                mock_write("new content")

            mock_write.assert_called_once_with("new content")

    def test_restores_even_on_exception(self):
        with (
            patch("prosefmt.clipboard.clipboard_read", return_value="saved"),
            patch("prosefmt.clipboard.clipboard_write") as mock_write,
            patch("prosefmt.clipboard.time.sleep"),
        ):
            try:
                with preserve_clipboard():
                    raise RuntimeError("boom")
            except RuntimeError:
                pass

            mock_write.assert_called_once_with("saved")

    def test_reads_clipboard_selection_not_primary(self):
        with (
            patch("prosefmt.clipboard.clipboard_read") as mock_read,
            patch("prosefmt.clipboard.clipboard_write"),
            patch("prosefmt.clipboard.time.sleep"),
        ):
            mock_read.return_value = ""
            with preserve_clipboard():
                pass

            mock_read.assert_called_once_with(selection="clipboard")


class TestClipboardWrite:
    """Tests for clipboard_write on each platform."""

    def test_x11_write(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_X11),
            patch("prosefmt.clipboard._run_stdin") as mock,
        ):
            clipboard_write("hello")
            mock.assert_called_once_with(["xclip", "-selection", "clipboard"], "hello")

    def test_wayland_write(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_WAYLAND),
            patch("prosefmt.clipboard._run_stdin") as mock,
        ):
            clipboard_write("hello")
            mock.assert_called_once_with(["wl-copy"], "hello")

    def test_macos_write(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.MACOS),
            patch("prosefmt.clipboard._run_stdin") as mock,
        ):
            clipboard_write("hello")
            mock.assert_called_once_with(["pbcopy"], "hello")

    def test_windows_write(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.WINDOWS),
            patch("prosefmt.clipboard._run_stdin") as mock,
        ):
            clipboard_write("hello")
            mock.assert_called_once_with(["clip.exe"], "hello")

    def test_unknown_platform_prints_to_stderr(self, capsys):
        with patch("prosefmt.clipboard.detect_platform", return_value=Platform.UNKNOWN):
            clipboard_write("hello")
        captured = capsys.readouterr()
        assert "hello" in captured.err


class TestCheckToolsWayland:
    """Test check_clipboard_tools on Wayland."""

    def test_wayland_missing_wl_clipboard(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_WAYLAND),
            patch("prosefmt.clipboard.shutil.which", return_value=None),
        ):
            missing = check_clipboard_tools()
            assert "wl-copy" in missing
            assert "wl-paste" in missing
            assert "wtype (or ydotool)" in missing

    def test_wayland_wtype_found(self):
        def _which(c):
            return f"/usr/bin/{c}" if c in ("wl-copy", "wl-paste", "wtype") else None

        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_WAYLAND),
            patch("prosefmt.clipboard.shutil.which", side_effect=_which),
        ):
            missing = check_clipboard_tools()
            assert missing == []

    def test_wayland_ydotool_found(self):
        def _which(c):
            return f"/usr/bin/{c}" if c in ("wl-copy", "wl-paste", "ydotool") else None

        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_WAYLAND),
            patch("prosefmt.clipboard.shutil.which", side_effect=_which),
        ):
            missing = check_clipboard_tools()
            assert missing == []


class TestInstallHints:
    """Test install_hints with various platform configurations."""

    def test_empty_when_no_tools_missing(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.MACOS),
        ):
            assert install_hints() == []

    def test_x11_with_platform_info(self):
        pi = PlatformInfo(os="linux", display="x11", distro="fedora", pkg_manager="dnf")
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_X11),
            patch("prosefmt.clipboard.shutil.which", return_value=None),
        ):
            hints = install_hints(pi)
            assert any("dnf" in h for h in hints)

    def test_wayland_with_platform_info(self):
        pi = PlatformInfo(os="linux", display="wayland", distro="ubuntu", pkg_manager="apt")
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_WAYLAND),
            patch("prosefmt.clipboard.shutil.which", return_value=None),
        ):
            hints = install_hints(pi)
            assert any("apt" in h for h in hints)

    def test_fallback_without_platform_info(self):
        with (
            patch("prosefmt.clipboard.detect_platform", return_value=Platform.LINUX_X11),
            patch("prosefmt.clipboard.shutil.which", return_value=None),
        ):
            hints = install_hints()
            assert len(hints) > 0
            assert any("Fedora" in h or "dnf" in h for h in hints)
            assert any("Ubuntu" in h or "apt" in h for h in hints)


class TestRunHelpers:
    """Test internal _run_stdout / _run_stdin helpers."""

    def test_run_stdout_returns_output(self):
        with patch("prosefmt.clipboard.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "some text\n"
            assert _run_stdout(["echo", "test"]) == "some text"

    def test_run_stdout_returns_empty_on_error(self):
        with patch("prosefmt.clipboard.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            assert _run_stdout(["false"]) == ""

    def test_run_stdout_returns_empty_on_missing_binary(self):
        with patch(
            "prosefmt.clipboard.subprocess.run", side_effect=FileNotFoundError("no such file")
        ):
            assert _run_stdout(["nonexistent"]) == ""

    def test_run_stdout_returns_empty_on_timeout(self):
        import subprocess

        with patch(
            "prosefmt.clipboard.subprocess.run",
            side_effect=subprocess.TimeoutExpired("cmd", 5),
        ):
            assert _run_stdout(["slow"]) == ""

    def test_run_stdin_suppresses_file_not_found(self):
        with patch(
            "prosefmt.clipboard.subprocess.run", side_effect=FileNotFoundError("no such file")
        ):
            _run_stdin(["nonexistent"], "text")

    def test_run_stdin_suppresses_timeout(self):
        import subprocess

        with patch(
            "prosefmt.clipboard.subprocess.run",
            side_effect=subprocess.TimeoutExpired("cmd", 5),
        ):
            _run_stdin(["slow"], "text")
