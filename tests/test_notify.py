"""Tests for the desktop notification module."""

from __future__ import annotations

from unittest.mock import patch

from prosefmt.clipboard import Platform
from prosefmt.notify import notify


class TestNotify:
    """Test notify() dispatches to the right tool and never raises."""

    def test_linux_uses_notify_send(self, monkeypatch):
        with (
            patch("prosefmt.notify.detect_platform", return_value=Platform.LINUX_X11),
            patch("prosefmt.notify.shutil.which", return_value="/usr/bin/notify-send"),
            patch("prosefmt.notify.subprocess.run") as mock_run,
        ):
            notify("prosefmt", "test message")
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "notify-send"
            assert "prosefmt" in cmd
            assert "test message" in cmd

    def test_linux_notify_send_urgency(self, monkeypatch):
        with (
            patch("prosefmt.notify.detect_platform", return_value=Platform.LINUX_X11),
            patch("prosefmt.notify.shutil.which", return_value="/usr/bin/notify-send"),
            patch("prosefmt.notify.subprocess.run") as mock_run,
        ):
            notify("title", "body", urgency="critical")
            cmd = mock_run.call_args[0][0]
            assert "critical" in cmd

    def test_macos_uses_osascript(self):
        with (
            patch("prosefmt.notify.detect_platform", return_value=Platform.MACOS),
            patch("prosefmt.notify.subprocess.run") as mock_run,
        ):
            notify("prosefmt", "test")
            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "osascript"

    def test_windows_uses_powershell(self):
        with (
            patch("prosefmt.notify.detect_platform", return_value=Platform.WINDOWS),
            patch("prosefmt.notify.subprocess.run") as mock_run,
        ):
            notify("prosefmt", "test")
            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "powershell.exe"

    def test_unknown_platform_uses_stderr_fallback(self, capsys):
        with patch("prosefmt.notify.detect_platform", return_value=Platform.UNKNOWN):
            notify("prosefmt", "test")
        captured = capsys.readouterr()
        assert "prosefmt" in captured.err
        assert "test" in captured.err

    def test_notify_without_body(self, monkeypatch):
        with (
            patch("prosefmt.notify.detect_platform", return_value=Platform.LINUX_X11),
            patch("prosefmt.notify.shutil.which", return_value="/usr/bin/notify-send"),
            patch("prosefmt.notify.subprocess.run") as mock_run,
        ):
            notify("prosefmt")
            cmd = mock_run.call_args[0][0]
            # Body should not appear in args
            assert cmd[-1] == "prosefmt"

    def test_notify_never_raises_on_exception(self, monkeypatch):
        """Even if subprocess fails, notify should not raise."""
        with (
            patch("prosefmt.notify.detect_platform", return_value=Platform.LINUX_X11),
            patch("prosefmt.notify.shutil.which", return_value="/usr/bin/notify-send"),
            patch("prosefmt.notify.subprocess.run", side_effect=OSError("boom")),
        ):
            # Should not raise
            notify("prosefmt", "test")

    def test_linux_no_notify_send_uses_stderr(self, capsys):
        with (
            patch("prosefmt.notify.detect_platform", return_value=Platform.LINUX_X11),
            patch("prosefmt.notify.shutil.which", return_value=None),
        ):
            notify("prosefmt", "test")
        captured = capsys.readouterr()
        assert "prosefmt" in captured.err
