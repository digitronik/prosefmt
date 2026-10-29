"""Tests for clipboard platform detection, selection dispatch, and save/restore."""

from __future__ import annotations

from unittest.mock import call, patch

from prosefmt.clipboard import (
    Platform,
    check_clipboard_tools,
    clipboard_read,
    detect_platform,
    preserve_clipboard,
)


class TestPlatformDetection:
    def test_macos(self):
        with patch("prosefmt.clipboard.platform.system", return_value="Darwin"):
            assert detect_platform() == Platform.MACOS

    def test_windows(self):
        with patch("prosefmt.clipboard.platform.system", return_value="Windows"):
            assert detect_platform() == Platform.WINDOWS

    def test_linux_x11(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        with patch("prosefmt.clipboard.platform.system", return_value="Linux"):
            assert detect_platform() == Platform.LINUX_X11

    def test_linux_wayland(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        with patch("prosefmt.clipboard.platform.system", return_value="Linux"):
            assert detect_platform() == Platform.LINUX_WAYLAND

    def test_linux_default_x11(self, monkeypatch):
        monkeypatch.delenv("XDG_SESSION_TYPE", raising=False)
        with patch("prosefmt.clipboard.platform.system", return_value="Linux"):
            assert detect_platform() == Platform.LINUX_X11

    def test_unknown_platform(self):
        with patch("prosefmt.clipboard.platform.system", return_value="FreeBSD"):
            assert detect_platform() == Platform.UNKNOWN


class TestCheckTools:
    def test_reports_missing_xclip(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        with (
            patch("prosefmt.clipboard.platform.system", return_value="Linux"),
            patch("prosefmt.clipboard.shutil.which", return_value=None),
        ):
            missing = check_clipboard_tools()
            assert "xclip" in missing
            assert "xdotool" in missing

    def test_no_missing_on_macos(self):
        with patch("prosefmt.clipboard.platform.system", return_value="Darwin"):
            assert check_clipboard_tools() == []


class TestClipboardReadSelection:
    """Tests for the ``selection`` parameter on ``clipboard_read``."""

    # -- X11 -------------------------------------------------------------------

    def test_x11_auto_prefers_primary(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        with (
            patch("prosefmt.clipboard.platform.system", return_value="Linux"),
            patch(
                "prosefmt.clipboard._run_stdout",
                side_effect=lambda cmd: "highlighted" if "primary" in cmd else "copied",
            ),
        ):
            assert clipboard_read() == "highlighted"

    def test_x11_auto_falls_back_to_clipboard(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        with (
            patch("prosefmt.clipboard.platform.system", return_value="Linux"),
            patch(
                "prosefmt.clipboard._run_stdout",
                side_effect=lambda cmd: "" if "primary" in cmd else "copied",
            ),
        ):
            assert clipboard_read() == "copied"

    def test_x11_explicit_primary(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        with (
            patch("prosefmt.clipboard.platform.system", return_value="Linux"),
            patch("prosefmt.clipboard._run_stdout", return_value="selected") as mock,
        ):
            assert clipboard_read(selection="primary") == "selected"
            mock.assert_called_once_with(["xclip", "-o", "-selection", "primary"])

    def test_x11_explicit_clipboard(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        with (
            patch("prosefmt.clipboard.platform.system", return_value="Linux"),
            patch("prosefmt.clipboard._run_stdout", return_value="copied") as mock,
        ):
            assert clipboard_read(selection="clipboard") == "copied"
            mock.assert_called_once_with(["xclip", "-o", "-selection", "clipboard"])

    # -- Wayland ---------------------------------------------------------------

    def test_wayland_primary_uses_flag(self, monkeypatch):
        """The Wayland bug fix: --primary must be passed to wl-paste."""
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        with (
            patch("prosefmt.clipboard.platform.system", return_value="Linux"),
            patch("prosefmt.clipboard._run_stdout", return_value="selected") as mock,
        ):
            assert clipboard_read(selection="primary") == "selected"
            mock.assert_called_once_with(["wl-paste", "--primary", "--no-newline"])

    def test_wayland_auto_prefers_primary(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        with (
            patch("prosefmt.clipboard.platform.system", return_value="Linux"),
            patch(
                "prosefmt.clipboard._run_stdout",
                side_effect=lambda cmd: "highlighted" if "--primary" in cmd else "copied",
            ),
        ):
            assert clipboard_read() == "highlighted"

    def test_wayland_auto_falls_back_to_clipboard(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        with (
            patch("prosefmt.clipboard.platform.system", return_value="Linux"),
            patch(
                "prosefmt.clipboard._run_stdout",
                side_effect=lambda cmd: "" if "--primary" in cmd else "copied",
            ),
        ):
            assert clipboard_read() == "copied"

    def test_wayland_explicit_clipboard(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        with (
            patch("prosefmt.clipboard.platform.system", return_value="Linux"),
            patch("prosefmt.clipboard._run_stdout", return_value="text") as mock,
        ):
            assert clipboard_read(selection="clipboard") == "text"
            mock.assert_called_once_with(["wl-paste", "--no-newline"])

    # -- macOS / Windows -------------------------------------------------------

    def test_macos_ignores_selection(self):
        with (
            patch("prosefmt.clipboard.platform.system", return_value="Darwin"),
            patch("prosefmt.clipboard._run_stdout", return_value="text"),
        ):
            for sel in ("auto", "primary", "clipboard"):
                assert clipboard_read(selection=sel) == "text"

    def test_windows_ignores_selection(self):
        with (
            patch("prosefmt.clipboard.platform.system", return_value="Windows"),
            patch("prosefmt.clipboard._run_stdout", return_value="text"),
        ):
            for sel in ("auto", "primary", "clipboard"):
                assert clipboard_read(selection=sel) == "text"


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
