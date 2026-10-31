"""Tests for platform detection and install command generation."""

from __future__ import annotations

from unittest.mock import mock_open, patch

from prosefmt.platform import PlatformInfo, detect


def _which(binary: str):
    """Return a fake shutil.which side_effect that only finds *binary*."""
    return lambda c: f"/usr/bin/{binary}" if c == binary else None


class TestDetect:
    def test_macos(self):
        with (
            patch("prosefmt.platform.platform.system", return_value="Darwin"),
            patch("prosefmt.platform.shutil.which", return_value="/opt/homebrew/bin/brew"),
        ):
            pi = detect()
        assert pi.os == "macos"
        assert pi.display == "quartz"
        assert pi.distro == "macos"
        assert pi.pkg_manager == "brew"

    def test_macos_no_brew(self):
        with (
            patch("prosefmt.platform.platform.system", return_value="Darwin"),
            patch("prosefmt.platform.shutil.which", return_value=None),
        ):
            pi = detect()
        assert pi.os == "macos"
        assert pi.pkg_manager == ""

    def test_windows(self):
        with (
            patch("prosefmt.platform.platform.system", return_value="Windows"),
            patch("prosefmt.platform.shutil.which", return_value="C:\\winget.exe"),
        ):
            pi = detect()
        assert pi.os == "windows"
        assert pi.display == "win32"
        assert pi.pkg_manager == "winget"

    def test_linux_x11_fedora(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        os_release = "ID=fedora\nVERSION_ID=41\n"
        with (
            patch("prosefmt.platform.platform.system", return_value="Linux"),
            patch("builtins.open", mock_open(read_data=os_release)),
            patch("prosefmt.platform.shutil.which", side_effect=_which("dnf")),
        ):
            pi = detect()
        assert pi.os == "linux"
        assert pi.display == "x11"
        assert pi.distro == "fedora"
        assert pi.pkg_manager == "dnf"

    def test_linux_wayland_ubuntu(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        os_release = 'ID=ubuntu\nVERSION_ID="24.04"\n'
        with (
            patch("prosefmt.platform.platform.system", return_value="Linux"),
            patch("builtins.open", mock_open(read_data=os_release)),
            patch("prosefmt.platform.shutil.which", side_effect=_which("apt")),
        ):
            pi = detect()
        assert pi.os == "linux"
        assert pi.display == "wayland"
        assert pi.distro == "ubuntu"
        assert pi.pkg_manager == "apt"

    def test_linux_arch(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        os_release = "ID=arch\n"
        with (
            patch("prosefmt.platform.platform.system", return_value="Linux"),
            patch("builtins.open", mock_open(read_data=os_release)),
            patch("prosefmt.platform.shutil.which", side_effect=_which("pacman")),
        ):
            pi = detect()
        assert pi.distro == "arch"
        assert pi.pkg_manager == "pacman"

    def test_linux_manjaro_maps_to_arch(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        os_release = "ID=manjaro\n"
        with (
            patch("prosefmt.platform.platform.system", return_value="Linux"),
            patch("builtins.open", mock_open(read_data=os_release)),
            patch("prosefmt.platform.shutil.which", side_effect=_which("pacman")),
        ):
            pi = detect()
        assert pi.distro == "arch"

    def test_linux_mint_maps_to_ubuntu(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        os_release = "ID=linuxmint\n"
        with (
            patch("prosefmt.platform.platform.system", return_value="Linux"),
            patch("builtins.open", mock_open(read_data=os_release)),
            patch("prosefmt.platform.shutil.which", side_effect=_which("apt")),
        ):
            pi = detect()
        assert pi.distro == "ubuntu"

    def test_unknown_os(self):
        with patch("prosefmt.platform.platform.system", return_value="FreeBSD"):
            pi = detect()
        assert pi.os == "unknown"
        assert pi.display == ""

    def test_linux_no_os_release(self, monkeypatch):
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        with (
            patch("prosefmt.platform.platform.system", return_value="Linux"),
            patch("builtins.open", side_effect=OSError("no file")),
            patch("prosefmt.platform.shutil.which", return_value=None),
        ):
            pi = detect()
        assert pi.distro == ""
        assert pi.pkg_manager == ""


class TestPlatformInfoInstallCmd:
    def test_dnf(self):
        pi = PlatformInfo(os="linux", display="x11", distro="fedora", pkg_manager="dnf")
        assert pi.install_cmd("rofi") == "sudo dnf install rofi"

    def test_apt_multiple(self):
        pi = PlatformInfo(os="linux", display="x11", distro="ubuntu", pkg_manager="apt")
        assert pi.install_cmd("xclip", "xdotool") == "sudo apt install xclip xdotool"

    def test_pacman(self):
        pi = PlatformInfo(os="linux", display="x11", distro="arch", pkg_manager="pacman")
        assert pi.install_cmd("zenity") == "sudo pacman -S zenity"

    def test_brew(self):
        pi = PlatformInfo(os="macos", display="quartz", distro="macos", pkg_manager="brew")
        assert pi.install_cmd("fzf") == "brew install fzf"

    def test_unknown_returns_none(self):
        pi = PlatformInfo(os="linux", display="x11", distro="", pkg_manager="")
        assert pi.install_cmd("rofi") is None

    def test_no_packages_returns_none(self):
        pi = PlatformInfo(os="linux", display="x11", distro="fedora", pkg_manager="dnf")
        assert pi.install_cmd() is None


class TestPlatformInfoSerialization:
    def test_round_trip(self):
        pi = PlatformInfo(os="linux", display="wayland", distro="fedora", pkg_manager="dnf")
        d = pi.to_dict()
        assert d == {"os": "linux", "display": "wayland", "distro": "fedora", "pkg_manager": "dnf"}

    def test_from_dict_fills_blanks(self):
        with (
            patch("prosefmt.platform.platform.system", return_value="Darwin"),
            patch("prosefmt.platform.shutil.which", return_value="/opt/homebrew/bin/brew"),
        ):
            pi = PlatformInfo.from_dict({"os": "macos"})
        assert pi.os == "macos"
        assert pi.display == "quartz"
