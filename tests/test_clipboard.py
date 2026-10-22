"""Tests for clipboard platform detection and tool checking."""

from __future__ import annotations

from unittest.mock import patch

from prosefmt.clipboard import Platform, check_clipboard_tools, detect_platform


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
