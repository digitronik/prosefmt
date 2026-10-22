"""Cross-platform clipboard and paste-back helpers.

No external Python dependencies — uses platform-native CLI tools:
  Linux (X11):    xclip / xdotool
  Linux (Wayland): wl-copy / wl-paste / wtype
  macOS:          pbcopy / pbpaste / osascript
  Windows:        PowerShell clip.exe / Get-Clipboard
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from enum import Enum, auto


class Platform(Enum):
    LINUX_X11 = auto()
    LINUX_WAYLAND = auto()
    MACOS = auto()
    WINDOWS = auto()
    UNKNOWN = auto()


def detect_platform() -> Platform:
    system = platform.system()
    if system == "Darwin":
        return Platform.MACOS
    if system == "Windows":
        return Platform.WINDOWS
    if system == "Linux":
        session = os.environ.get("XDG_SESSION_TYPE", "").lower()
        if session == "wayland":
            return Platform.LINUX_WAYLAND
        return Platform.LINUX_X11
    return Platform.UNKNOWN


def clipboard_read() -> str:
    """Read text from the system clipboard."""
    plat = detect_platform()

    if plat == Platform.LINUX_X11:
        for sel in ("primary", "clipboard"):
            text = _run_stdout(["xclip", "-o", "-selection", sel])
            if text:
                return text
        return ""

    if plat == Platform.LINUX_WAYLAND:
        return _run_stdout(["wl-paste", "--no-newline"])

    if plat == Platform.MACOS:
        return _run_stdout(["pbpaste"])

    if plat == Platform.WINDOWS:
        return _run_stdout(["powershell.exe", "-Command", "Get-Clipboard"])

    return ""


def clipboard_write(text: str) -> None:
    """Write text to the system clipboard."""
    plat = detect_platform()

    if plat == Platform.LINUX_X11:
        _run_stdin(["xclip", "-selection", "clipboard"], text)

    elif plat == Platform.LINUX_WAYLAND:
        _run_stdin(["wl-copy"], text)

    elif plat == Platform.MACOS:
        _run_stdin(["pbcopy"], text)

    elif plat == Platform.WINDOWS:
        _run_stdin(["clip.exe"], text)

    else:
        print(text, file=sys.stderr)


def paste_to_active_window() -> None:
    """Simulate Ctrl+V / Cmd+V in the currently focused window."""
    plat = detect_platform()

    if plat == Platform.LINUX_X11:
        subprocess.run(
            ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
            check=False,
            capture_output=True,
        )

    elif plat == Platform.LINUX_WAYLAND:
        if shutil.which("wtype"):
            subprocess.run(["wtype", "-M", "ctrl", "v", "-m", "ctrl"], check=False)
        elif shutil.which("ydotool"):
            subprocess.run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0"], check=False)

    elif plat == Platform.MACOS:
        applescript = 'tell application "System Events" to keystroke "v" using command down'
        subprocess.run(
            ["osascript", "-e", applescript],
            check=False,
            capture_output=True,
        )

    elif plat == Platform.WINDOWS:
        ps_cmd = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            '[System.Windows.Forms.SendKeys]::SendWait("^v")'
        )
        subprocess.run(
            ["powershell.exe", "-Command", ps_cmd],
            check=False,
            capture_output=True,
        )


def check_clipboard_tools() -> list[str]:
    """Return a list of missing clipboard tools for the current platform."""
    plat = detect_platform()
    missing: list[str] = []

    if plat == Platform.LINUX_X11:
        for tool in ("xclip", "xdotool"):
            if not shutil.which(tool):
                missing.append(tool)

    elif plat == Platform.LINUX_WAYLAND:
        for tool in ("wl-copy", "wl-paste"):
            if not shutil.which(tool):
                missing.append(tool)
        if not shutil.which("wtype") and not shutil.which("ydotool"):
            missing.append("wtype (or ydotool)")

    return missing


def install_hints() -> list[str]:
    """Return human-readable install instructions for missing clipboard tools.

    Returns an empty list when everything is installed or no tools are needed.
    Each entry is a ready-to-run shell command the user can copy-paste.
    """
    missing = check_clipboard_tools()
    if not missing:
        return []

    plat = detect_platform()
    hints: list[str] = []

    if plat == Platform.LINUX_X11:
        pkg = " ".join(t for t in ("xclip", "xdotool") if not shutil.which(t))
        if pkg:
            hints += [
                f"  # Debian / Ubuntu / Mint:   sudo apt install {pkg}",
                f"  # Fedora / RHEL / CentOS:   sudo dnf install {pkg}",
                f"  # Arch / Manjaro:            sudo pacman -S {pkg}",
                f"  # openSUSE:                  sudo zypper install {pkg}",
            ]

    elif plat == Platform.LINUX_WAYLAND:
        wl_pkg = " ".join(
            t for t in ("wl-copy", "wl-paste") if not shutil.which(t)
        )
        # wl-clipboard ships both wl-copy and wl-paste
        if wl_pkg:
            hints += [
                "  # Debian / Ubuntu / Mint:   sudo apt install wl-clipboard",
                "  # Fedora / RHEL / CentOS:   sudo dnf install wl-clipboard",
                "  # Arch / Manjaro:            sudo pacman -S wl-clipboard",
                "  # openSUSE:                  sudo zypper install wl-clipboard",
            ]
        if not shutil.which("wtype") and not shutil.which("ydotool"):
            hints.append("")
            hints += [
                "  # For paste-back (--system mode), also install wtype:",
                "  # Debian / Ubuntu / Mint:   sudo apt install wtype",
                "  # Fedora / RHEL / CentOS:   sudo dnf install wtype",
                "  # Arch / Manjaro:            sudo pacman -S wtype",
            ]

    return hints


def _run_stdout(cmd: list[str]) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _run_stdin(cmd: list[str], text: str) -> None:
    import contextlib

    with contextlib.suppress(FileNotFoundError, subprocess.TimeoutExpired):
        subprocess.run(cmd, input=text, check=False, capture_output=True, text=True, timeout=5)
