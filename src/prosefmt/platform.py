"""Platform detection — OS, display server, Linux distro, and package manager.

Centralises platform identification so that install hints, ``config init``,
``check``, clipboard, and notifications all share a single source of truth.

This module is intentionally independent of the rest of prosefmt (no internal
imports) so it can be loaded early without circular-dependency issues.
"""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from enum import Enum, auto


@dataclass(frozen=True)
class PlatformInfo:
    """Snapshot of the detected platform."""

    os: str  # "linux", "macos", "windows", "unknown"
    display: str  # "x11", "wayland", "quartz", "win32", ""
    distro: str  # "fedora", "ubuntu", "arch", "debian", "opensuse", ""
    pkg_manager: str  # "dnf", "apt", "pacman", "zypper", "brew", ""

    def install_cmd(self, *packages: str) -> str | None:
        """Return an install command string, or ``None`` if unknown."""
        if not self.pkg_manager or not packages:
            return None
        pkg_str = " ".join(packages)
        prefix = {
            "dnf": "sudo dnf install",
            "apt": "sudo apt install",
            "pacman": "sudo pacman -S",
            "zypper": "sudo zypper install",
            "brew": "brew install",
        }
        pfx = prefix.get(self.pkg_manager)
        return f"{pfx} {pkg_str}" if pfx else None

    def to_dict(self) -> dict[str, str]:
        """Serialise to a plain dict (for TOML ``[platform]``)."""
        return {
            "os": self.os,
            "display": self.display,
            "distro": self.distro,
            "pkg_manager": self.pkg_manager,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> PlatformInfo:
        """Deserialise from a TOML dict, filling blanks from auto-detection."""
        auto = detect()
        return cls(
            os=data.get("os") or auto.os,
            display=data.get("display") or auto.display,
            distro=data.get("distro") or auto.distro,
            pkg_manager=data.get("pkg_manager") or auto.pkg_manager,
        )


def detect() -> PlatformInfo:
    """Auto-detect OS, display server, Linux distro, and package manager."""
    system = platform.system()

    if system == "Darwin":
        return PlatformInfo(
            os="macos",
            display="quartz",
            distro="macos",
            pkg_manager="brew" if shutil.which("brew") else "",
        )

    if system == "Windows":
        return PlatformInfo(
            os="windows",
            display="win32",
            distro="windows",
            pkg_manager="winget" if shutil.which("winget") else "",
        )

    if system == "Linux":
        return PlatformInfo(
            os="linux",
            display=_linux_display(),
            distro=_detect_linux_distro(),
            pkg_manager=_detect_linux_pkg_manager(),
        )

    return PlatformInfo(os="unknown", display="", distro="", pkg_manager="")


# ---------------------------------------------------------------------------
# Linux helpers
# ---------------------------------------------------------------------------


def _linux_display() -> str:
    """Detect the Linux display server — single source of truth.

    Checks ``WAYLAND_DISPLAY`` first (set by all Wayland compositors),
    then falls back to ``XDG_SESSION_TYPE``.  Used by both ``detect()``
    (PlatformInfo) and ``detect_platform()`` (Platform enum) so they
    always agree.
    """
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        return "wayland"
    return "x11"


# Map distro IDs (from /etc/os-release) to canonical family names.
_DISTRO_FAMILIES: dict[str, str] = {
    "fedora": "fedora",
    "rhel": "fedora",
    "centos": "fedora",
    "rocky": "fedora",
    "almalinux": "fedora",
    "ubuntu": "ubuntu",
    "debian": "debian",
    "linuxmint": "ubuntu",
    "pop": "ubuntu",
    "elementary": "ubuntu",
    "zorin": "ubuntu",
    "arch": "arch",
    "manjaro": "arch",
    "endeavouros": "arch",
    "garuda": "arch",
    "opensuse-tumbleweed": "opensuse",
    "opensuse-leap": "opensuse",
    "sles": "opensuse",
}


def _detect_linux_distro() -> str:
    """Read ``/etc/os-release`` and return the canonical distro family."""
    try:
        with open("/etc/os-release", encoding="utf-8") as fh:
            data: dict[str, str] = {}
            for line in fh:
                line = line.strip()
                if "=" in line:
                    key, _, val = line.partition("=")
                    data[key] = val.strip('"')
        distro_id = data.get("ID", "").lower()
        return _DISTRO_FAMILIES.get(distro_id, distro_id)
    except OSError:
        return ""


def _detect_linux_pkg_manager() -> str:
    """Return the first package manager found on PATH."""
    for cmd in ("dnf", "apt", "pacman", "zypper"):
        if shutil.which(cmd):
            return cmd
    return ""


# ---------------------------------------------------------------------------
# Clipboard / notify platform enum
# ---------------------------------------------------------------------------


class Platform(Enum):
    """Coarse platform classification for clipboard and notification dispatch."""

    LINUX_X11 = auto()
    LINUX_WAYLAND = auto()
    MACOS = auto()
    WINDOWS = auto()
    UNKNOWN = auto()


def detect_platform() -> Platform:
    """Detect the platform for clipboard/notification operations.

    Uses ``_linux_display()`` so this always agrees with ``detect()``.
    """
    system = platform.system()
    if system == "Darwin":
        return Platform.MACOS
    if system == "Windows":
        return Platform.WINDOWS
    if system == "Linux":
        return Platform.LINUX_WAYLAND if _linux_display() == "wayland" else Platform.LINUX_X11
    return Platform.UNKNOWN


# ---------------------------------------------------------------------------
# Shared escaping helpers
# ---------------------------------------------------------------------------


def esc_applescript(s: str) -> str:
    """Escape a string for interpolation inside AppleScript double quotes."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
