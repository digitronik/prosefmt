"""Tests for the platform-aware mode picker."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from prosefmt.picker import (
    _PICKER_PRIORITY,
    available_pickers,
    best_picker,
    check_picker_tools,
    install_hints_picker,
    pick,
)


class TestAvailablePickers:
    def test_returns_installed_tools_in_priority_order(self):
        def fake_which(tool):
            # Simulate only rofi and fzf installed
            return f"/usr/bin/{tool}" if tool in ("rofi", "fzf") else None

        with patch("prosefmt.picker.shutil.which", side_effect=fake_which):
            result = available_pickers()

        assert result == ["rofi", "fzf"]

    def test_empty_when_nothing_installed(self):
        with patch("prosefmt.picker.shutil.which", return_value=None):
            assert available_pickers() == []

    def test_all_tools_when_everything_installed(self):
        with patch("prosefmt.picker.shutil.which", return_value="/usr/bin/tool"):
            result = available_pickers()
        assert result == _PICKER_PRIORITY


class TestBestPicker:
    def test_returns_first_available(self):
        def fake_which(t):
            return "/usr/bin/wofi" if t == "wofi" else None

        with patch("prosefmt.picker.shutil.which", side_effect=fake_which):
            # rofi not found, wofi found → wofi should be returned
            assert best_picker() == "wofi"

    def test_returns_none_when_nothing_installed(self):
        with patch("prosefmt.picker.shutil.which", return_value=None):
            assert best_picker() is None


class TestCheckPickerTools:
    def test_reports_correctly(self):
        def fake_which(tool):
            return "/usr/bin/rofi" if tool == "rofi" else None

        with patch("prosefmt.picker.shutil.which", side_effect=fake_which):
            result = check_picker_tools()

        assert result["rofi"] is True
        assert result["wofi"] is False
        assert result["fzf"] is False

    def test_all_keys_present(self):
        with patch("prosefmt.picker.shutil.which", return_value=None):
            result = check_picker_tools()
        assert set(result.keys()) == set(_PICKER_PRIORITY)


class TestInstallHints:
    def test_empty_when_picker_available(self):
        with patch("prosefmt.picker.shutil.which", return_value="/usr/bin/rofi"):
            assert install_hints_picker() == []

    def test_non_empty_when_nothing_installed(self):
        with patch("prosefmt.picker.shutil.which", return_value=None):
            hints = install_hints_picker()
        assert len(hints) > 0
        assert any("rofi" in h for h in hints)

    def test_with_linux_platform_info(self):
        from prosefmt.platform import PlatformInfo

        pi = PlatformInfo(os="linux", display="x11", distro="fedora", pkg_manager="dnf")
        with patch("prosefmt.picker.shutil.which", return_value=None):
            hints = install_hints_picker(pi)
        assert len(hints) > 0
        assert any("dnf" in h for h in hints)

    def test_with_wayland_platform_info(self):
        from prosefmt.platform import PlatformInfo

        pi = PlatformInfo(os="linux", display="wayland", distro="fedora", pkg_manager="dnf")
        with patch("prosefmt.picker.shutil.which", return_value=None):
            hints = install_hints_picker(pi)
        assert len(hints) > 0
        assert any("wofi" in h for h in hints)

    def test_with_macos_platform_info(self):
        from prosefmt.platform import PlatformInfo

        pi = PlatformInfo(os="macos", display="quartz", distro="macos", pkg_manager="brew")
        with patch("prosefmt.picker.shutil.which", return_value=None):
            hints = install_hints_picker(pi)
        assert any("fzf" in h for h in hints)


class TestPick:
    """Test pick() dispatch.

    _DISPATCHERS holds direct function references, so patching individual
    _pick_* names won't affect it.  We patch the dict itself via patch.dict.
    """

    def test_returns_none_when_no_picker(self):
        with patch("prosefmt.picker.best_picker", return_value=None):
            assert pick(["fix", "rephrase"]) is None

    def test_delegates_to_rofi(self):
        stub = MagicMock(return_value="fix")
        with (
            patch("prosefmt.picker.best_picker", return_value="rofi"),
            patch.dict("prosefmt.picker._DISPATCHERS", {"rofi": stub}),
        ):
            result = pick(["fix", "rephrase"], prompt="test")
            stub.assert_called_once_with(["fix", "rephrase"], "test")
            assert result == "fix"

    def test_delegates_to_wofi(self):
        with (
            patch("prosefmt.picker.best_picker", return_value="wofi"),
            patch.dict("prosefmt.picker._DISPATCHERS", {"wofi": lambda c, p: "rephrase"}),
        ):
            assert pick(["fix", "rephrase"]) == "rephrase"

    def test_delegates_to_fzf(self):
        with (
            patch("prosefmt.picker.best_picker", return_value="fzf"),
            patch.dict("prosefmt.picker._DISPATCHERS", {"fzf": lambda c, p: "summarize"}),
        ):
            assert pick(["fix", "summarize"]) == "summarize"

    def test_returns_custom_free_form(self):
        """User types something not in the list — caller treats it as a custom prompt."""
        with (
            patch("prosefmt.picker.best_picker", return_value="rofi"),
            patch.dict("prosefmt.picker._DISPATCHERS", {"rofi": lambda c, p: "make it rhyme"}),
        ):
            assert pick(["fix", "rephrase"]) == "make it rhyme"

    def test_cancelled_returns_none(self):
        with (
            patch("prosefmt.picker.best_picker", return_value="rofi"),
            patch.dict("prosefmt.picker._DISPATCHERS", {"rofi": lambda c, p: None}),
        ):
            assert pick(["fix"]) is None


class TestPickRofiUnit:
    """Unit-test the rofi dispatcher by mocking subprocess.run."""

    def test_returns_selection(self):
        from prosefmt.picker import _pick_rofi

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "fix\n"

        with patch("prosefmt.picker.subprocess.run", return_value=mock_result):
            assert _pick_rofi(["fix", "rephrase"], "test") == "fix"

    def test_returns_none_on_cancel(self):
        from prosefmt.picker import _pick_rofi

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("prosefmt.picker.subprocess.run", return_value=mock_result):
            assert _pick_rofi(["fix"], "test") is None


class TestPickWofiUnit:
    """Unit-test the wofi dispatcher."""

    def test_returns_selection(self):
        from prosefmt.picker import _pick_wofi

        mock_result = MagicMock()
        mock_result.stdout = "rephrase\n"

        with patch("prosefmt.picker.subprocess.run", return_value=mock_result):
            assert _pick_wofi(["fix", "rephrase"], "test") == "rephrase"

    def test_returns_none_on_cancel(self):
        from prosefmt.picker import _pick_wofi

        mock_result = MagicMock()
        mock_result.stdout = ""

        with patch("prosefmt.picker.subprocess.run", return_value=mock_result):
            assert _pick_wofi(["fix"], "test") is None


class TestPickFuzzelUnit:
    """Unit-test the fuzzel dispatcher."""

    def test_returns_selection(self):
        from prosefmt.picker import _pick_fuzzel

        mock_result = MagicMock()
        mock_result.stdout = "fix\n"

        with patch("prosefmt.picker.subprocess.run", return_value=mock_result):
            assert _pick_fuzzel(["fix", "rephrase"], "test") == "fix"

    def test_returns_none_on_cancel(self):
        from prosefmt.picker import _pick_fuzzel

        mock_result = MagicMock()
        mock_result.stdout = ""

        with patch("prosefmt.picker.subprocess.run", return_value=mock_result):
            assert _pick_fuzzel(["fix"], "test") is None


class TestPickDmenuUnit:
    """Unit-test the dmenu dispatcher."""

    def test_returns_selection(self):
        from prosefmt.picker import _pick_dmenu

        mock_result = MagicMock()
        mock_result.stdout = "casual\n"

        with patch("prosefmt.picker.subprocess.run", return_value=mock_result):
            assert _pick_dmenu(["fix", "casual"], "test") == "casual"

    def test_returns_none_on_cancel(self):
        from prosefmt.picker import _pick_dmenu

        mock_result = MagicMock()
        mock_result.stdout = ""

        with patch("prosefmt.picker.subprocess.run", return_value=mock_result):
            assert _pick_dmenu(["fix"], "test") is None


class TestPickZenityUnit:
    """Unit-test the zenity dispatcher."""

    def test_returns_selection(self):
        from prosefmt.picker import _pick_zenity

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "summarize\n"

        with patch("prosefmt.picker.subprocess.run", return_value=mock_result):
            assert _pick_zenity(["fix", "summarize"], "test") == "summarize"

    def test_returns_none_on_cancel(self):
        from prosefmt.picker import _pick_zenity

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("prosefmt.picker.subprocess.run", return_value=mock_result):
            assert _pick_zenity(["fix"], "test") is None

    def test_custom_prompt_entry(self):
        """Selecting 'Custom prompt…' should open an entry dialog."""
        from prosefmt.picker import _pick_zenity

        list_result = MagicMock()
        list_result.returncode = 0
        list_result.stdout = "Custom prompt…\n"

        entry_result = MagicMock()
        entry_result.stdout = "translate to french\n"

        with patch(
            "prosefmt.picker.subprocess.run",
            side_effect=[list_result, entry_result],
        ):
            assert _pick_zenity(["fix"], "test") == "translate to french"

    def test_custom_prompt_cancelled(self):
        from prosefmt.picker import _pick_zenity

        list_result = MagicMock()
        list_result.returncode = 0
        list_result.stdout = "Custom prompt…\n"

        entry_result = MagicMock()
        entry_result.stdout = ""

        with patch(
            "prosefmt.picker.subprocess.run",
            side_effect=[list_result, entry_result],
        ):
            assert _pick_zenity(["fix"], "test") is None


class TestPickOsascriptUnit:
    """Unit-test the osascript (macOS) dispatcher."""

    def test_returns_selection(self):
        from prosefmt.picker import _pick_osascript

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "professional\n"

        with patch("prosefmt.picker.subprocess.run", return_value=mock_result):
            assert _pick_osascript(["fix", "professional"], "test") == "professional"

    def test_returns_none_on_cancel(self):
        from prosefmt.picker import _pick_osascript

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("prosefmt.picker.subprocess.run", return_value=mock_result):
            assert _pick_osascript(["fix"], "test") is None

    def test_returns_none_on_false(self):
        """osascript returns 'false' when the user clicks Cancel."""
        from prosefmt.picker import _pick_osascript

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "false\n"

        with patch("prosefmt.picker.subprocess.run", return_value=mock_result):
            assert _pick_osascript(["fix"], "test") is None


class TestPickFzfUnit:
    """Unit-test the fzf dispatcher (covers free-form + cancel cases)."""

    def test_returns_selected_item(self):
        from prosefmt.picker import _pick_fzf

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "fi\nfix\n"  # query + selection

        with patch("prosefmt.picker.subprocess.run", return_value=mock_result):
            assert _pick_fzf(["fix", "rephrase"], "test") == "fix"

    def test_returns_query_when_no_match(self):
        from prosefmt.picker import _pick_fzf

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "make it rhyme\n"  # no match, query only

        with patch("prosefmt.picker.subprocess.run", return_value=mock_result):
            assert _pick_fzf(["fix"], "test") == "make it rhyme"

    def test_returns_none_on_cancel(self):
        from prosefmt.picker import _pick_fzf

        mock_result = MagicMock()
        mock_result.returncode = 130
        mock_result.stdout = ""

        with patch("prosefmt.picker.subprocess.run", return_value=mock_result):
            assert _pick_fzf(["fix"], "test") is None
