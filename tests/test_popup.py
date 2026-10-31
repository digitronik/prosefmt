"""Tests for the desktop popup display module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from prosefmt.popup import (
    _POPUP_PRIORITY,
    available_popups,
    best_popup,
    check_popup_tools,
    install_hints_popup,
    show_popup,
)


class TestAvailablePopups:
    def test_returns_installed_tools_in_priority_order(self):
        def fake_which(tool):
            return f"/usr/bin/{tool}" if tool in ("zenity", "rofi") else None

        with patch("prosefmt.popup.shutil.which", side_effect=fake_which):
            result = available_popups()

        assert result == ["zenity", "rofi"]

    def test_empty_when_nothing_installed(self):
        with patch("prosefmt.popup.shutil.which", return_value=None):
            assert available_popups() == []

    def test_all_tools_when_everything_installed(self):
        with patch("prosefmt.popup.shutil.which", return_value="/usr/bin/tool"):
            result = available_popups()
        assert result == _POPUP_PRIORITY


class TestBestPopup:
    def test_returns_first_available(self):
        def fake_which(t):
            return "/usr/bin/yad" if t == "yad" else None

        with patch("prosefmt.popup.shutil.which", side_effect=fake_which):
            assert best_popup() == "yad"

    def test_returns_none_when_nothing_installed(self):
        with patch("prosefmt.popup.shutil.which", return_value=None):
            assert best_popup() is None

    def test_prefers_zenity_over_others(self):
        def fake_which(t):
            return f"/usr/bin/{t}" if t in ("zenity", "rofi", "notify-send") else None

        with patch("prosefmt.popup.shutil.which", side_effect=fake_which):
            assert best_popup() == "zenity"


class TestCheckPopupTools:
    def test_reports_correctly(self):
        def fake_which(tool):
            return "/usr/bin/zenity" if tool == "zenity" else None

        with patch("prosefmt.popup.shutil.which", side_effect=fake_which):
            result = check_popup_tools()

        assert result["zenity"] is True
        assert result["yad"] is False
        assert result["rofi"] is False
        assert result["notify-send"] is False

    def test_all_keys_present(self):
        with patch("prosefmt.popup.shutil.which", return_value=None):
            result = check_popup_tools()
        assert set(result.keys()) == set(_POPUP_PRIORITY)


class TestInstallHintsPopup:
    def test_empty_when_popup_available(self):
        with patch("prosefmt.popup.shutil.which", return_value="/usr/bin/zenity"):
            assert install_hints_popup() == []

    def test_non_empty_when_nothing_installed(self):
        with patch("prosefmt.popup.shutil.which", return_value=None):
            hints = install_hints_popup()
        assert len(hints) > 0
        assert any("zenity" in h for h in hints)

    def test_with_linux_platform_info(self):
        from prosefmt.platform import PlatformInfo

        pi = PlatformInfo(os="linux", display="x11", distro="fedora", pkg_manager="dnf")
        with patch("prosefmt.popup.shutil.which", return_value=None):
            hints = install_hints_popup(pi)
        assert len(hints) > 0
        assert any("dnf" in h for h in hints)

    def test_with_macos_platform_info(self):
        from prosefmt.platform import PlatformInfo

        pi = PlatformInfo(os="macos", display="quartz", distro="macos", pkg_manager="brew")
        with patch("prosefmt.popup.shutil.which", return_value=None):
            hints = install_hints_popup(pi)
        assert any("zenity" in h or "osascript" in h for h in hints)


class TestShowPopup:
    """Test show_popup() dispatch."""

    def test_returns_false_when_no_tool(self):
        with patch("prosefmt.popup.best_popup", return_value=None):
            assert show_popup("hello") is False

    def test_delegates_to_zenity(self):
        stub = MagicMock(return_value=True)
        with (
            patch("prosefmt.popup.best_popup", return_value="zenity"),
            patch.dict("prosefmt.popup._DISPATCHERS", {"zenity": stub}),
        ):
            result = show_popup("test text", title="test title")
            stub.assert_called_once_with("test text", "test title")
            assert result is True

    def test_delegates_to_yad(self):
        stub = MagicMock(return_value=True)
        with (
            patch("prosefmt.popup.best_popup", return_value="yad"),
            patch.dict("prosefmt.popup._DISPATCHERS", {"yad": stub}),
        ):
            result = show_popup("text")
            assert result is True

    def test_delegates_to_rofi(self):
        stub = MagicMock(return_value=True)
        with (
            patch("prosefmt.popup.best_popup", return_value="rofi"),
            patch.dict("prosefmt.popup._DISPATCHERS", {"rofi": stub}),
        ):
            result = show_popup("text")
            assert result is True

    def test_delegates_to_notify_send(self):
        stub = MagicMock(return_value=True)
        with (
            patch("prosefmt.popup.best_popup", return_value="notify-send"),
            patch.dict("prosefmt.popup._DISPATCHERS", {"notify-send": stub}),
        ):
            result = show_popup("text")
            assert result is True

    def test_default_title(self):
        stub = MagicMock(return_value=True)
        with (
            patch("prosefmt.popup.best_popup", return_value="zenity"),
            patch.dict("prosefmt.popup._DISPATCHERS", {"zenity": stub}),
        ):
            show_popup("text")
            stub.assert_called_once_with("text", "prosefmt")


class TestPopupZenityUnit:
    """Unit-test the zenity dispatcher by mocking subprocess.run."""

    def test_calls_zenity_text_info(self):
        from prosefmt.popup import _popup_zenity

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("prosefmt.popup.subprocess.run", return_value=mock_result) as mock_run:
            result = _popup_zenity("Hello world", "Test Title")

        assert result is True
        args = mock_run.call_args
        cmd = args[0][0]
        assert cmd[0] == "zenity"
        assert "--text-info" in cmd
        assert "Test Title" in cmd
        assert args[1]["input"] == "Hello world"


class TestPopupRofiUnit:
    """Unit-test the rofi dispatcher."""

    def test_calls_rofi_e(self):
        from prosefmt.popup import _popup_rofi

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("prosefmt.popup.subprocess.run", return_value=mock_result) as mock_run:
            result = _popup_rofi("Hello", "Title")

        assert result is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "rofi"
        assert "-e" in cmd


class TestPopupYadUnit:
    """Unit-test the yad dispatcher."""

    def test_calls_yad_text_info(self):
        from prosefmt.popup import _popup_yad

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("prosefmt.popup.subprocess.run", return_value=mock_result) as mock_run:
            result = _popup_yad("Hello world", "Test Title")

        assert result is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "yad"
        assert "--text-info" in cmd
        assert "Test Title" in cmd


class TestPopupKdialogUnit:
    """Unit-test the kdialog dispatcher."""

    def test_calls_kdialog_textbox(self):
        from prosefmt.popup import _popup_kdialog

        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch("prosefmt.popup.subprocess.run", return_value=mock_result) as mock_run,
            patch("prosefmt.popup.os.unlink"),
        ):
            result = _popup_kdialog("Hello world", "Test Title")

        assert result is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "kdialog"
        assert "--textbox" in cmd


class TestPopupOsascriptUnit:
    """Unit-test the osascript (macOS) dispatcher."""

    def test_calls_osascript(self):
        from prosefmt.popup import _popup_osascript

        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch("prosefmt.popup.subprocess.run", return_value=mock_result) as mock_run,
            patch("prosefmt.popup.os.unlink"),
        ):
            result = _popup_osascript("Hello world", "Test Title")

        assert result is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "osascript"


class TestPopupNotifySendUnit:
    """Unit-test the notify-send fallback."""

    def test_truncates_long_text(self):
        from prosefmt.popup import _popup_notify

        long_text = "x" * 500

        with patch("prosefmt.popup.subprocess.run") as mock_run:
            _popup_notify(long_text, "Title")

        cmd = mock_run.call_args[0][0]
        # The body arg should be truncated
        body_arg = cmd[-1]
        assert len(body_arg) < 500
        assert "truncated" in body_arg

    def test_short_text_not_truncated(self):
        from prosefmt.popup import _popup_notify

        short_text = "Just a short message"

        with patch("prosefmt.popup.subprocess.run") as mock_run:
            _popup_notify(short_text, "Title")

        cmd = mock_run.call_args[0][0]
        body_arg = cmd[-1]
        assert body_arg == short_text


class TestShowPopupDispatchEdgeCases:
    """Edge cases for show_popup dispatch."""

    def test_unknown_dispatcher_returns_false(self):
        with (
            patch("prosefmt.popup.best_popup", return_value="unknown_tool"),
            patch.dict("prosefmt.popup._DISPATCHERS", {}, clear=True),
        ):
            assert show_popup("text") is False

    def test_delegates_to_kdialog(self):
        stub = MagicMock(return_value=True)
        with (
            patch("prosefmt.popup.best_popup", return_value="kdialog"),
            patch.dict("prosefmt.popup._DISPATCHERS", {"kdialog": stub}),
        ):
            result = show_popup("text", title="popup title")
            assert result is True
            stub.assert_called_once_with("text", "popup title")

    def test_delegates_to_osascript(self):
        stub = MagicMock(return_value=True)
        with (
            patch("prosefmt.popup.best_popup", return_value="osascript"),
            patch.dict("prosefmt.popup._DISPATCHERS", {"osascript": stub}),
        ):
            result = show_popup("text")
            assert result is True
