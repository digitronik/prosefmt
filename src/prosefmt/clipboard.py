"""Cross-platform clipboard helpers with save/restore support.

No external Python dependencies — uses platform-native CLI tools:
  Linux (X11):     xclip / xdotool
  Linux (Wayland): wl-copy / wl-paste / wtype
  macOS:           pbcopy / pbpaste / osascript
  Windows:         PowerShell clip.exe / Get-Clipboard
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
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


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def clipboard_read(selection: str = "auto") -> str:
    """Read text from the system clipboard.

    Args:
        selection: Which buffer to read on Linux.
            ``"auto"``      — primary first, fall back to clipboard (default)
            ``"primary"``   — primary selection only (highlighted text)
            ``"clipboard"`` — clipboard selection only (Ctrl+C buffer)

            On macOS / Windows the parameter is ignored (single clipboard).
    """
    plat = detect_platform()

    if plat == Platform.LINUX_X11:
        return _x11_read(selection)

    if plat == Platform.LINUX_WAYLAND:
        return _wayland_read(selection)

    if plat == Platform.MACOS:
        return _run_stdout(["pbpaste"])

    if plat == Platform.WINDOWS:
        return _run_stdout(["powershell.exe", "-Command", "Get-Clipboard"])

    return ""


def _x11_read(selection: str) -> str:
    if selection == "primary":
        return _run_stdout(["xclip", "-o", "-selection", "primary"])
    if selection == "clipboard":
        return _run_stdout(["xclip", "-o", "-selection", "clipboard"])
    # auto — try primary (highlighted text) first, fall back to clipboard
    for sel in ("primary", "clipboard"):
        text = _run_stdout(["xclip", "-o", "-selection", sel])
        if text:
            return text
    return ""


def _wayland_read(selection: str) -> str:
    if selection == "primary":
        return _run_stdout(["wl-paste", "--primary", "--no-newline"])
    if selection == "clipboard":
        return _run_stdout(["wl-paste", "--no-newline"])
    # auto — try primary first, fall back to clipboard
    text = _run_stdout(["wl-paste", "--primary", "--no-newline"])
    if text:
        return text
    return _run_stdout(["wl-paste", "--no-newline"])


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


def clipboard_write(text: str) -> None:
    """Write text to the system clipboard (Ctrl+C buffer)."""
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


# ---------------------------------------------------------------------------
# Paste
# ---------------------------------------------------------------------------


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
            subprocess.run(
                ["wtype", "-M", "ctrl", "v", "-m", "ctrl"],
                check=False,
                capture_output=True,
            )
        elif shutil.which("ydotool"):
            subprocess.run(
                ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
                check=False,
                capture_output=True,
            )

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


# ---------------------------------------------------------------------------
# Save / Restore  (context manager)
# ---------------------------------------------------------------------------

_PASTE_SETTLE_SECS = 0.15


@contextmanager
def preserve_clipboard() -> Generator[None, None, None]:
    """Save the clipboard, yield, then restore it.

    Wrap the write → paste sequence so the user's Ctrl+C buffer survives::

        with preserve_clipboard():
            clipboard_write(new_text)
            paste_to_active_window()

    On exit the context manager waits briefly for the target application to
    process the paste, then writes the old clipboard content back.
    """
    saved = clipboard_read(selection="clipboard")
    try:
        yield
    finally:
        if saved:
            time.sleep(_PASTE_SETTLE_SECS)
            clipboard_write(saved)


# ---------------------------------------------------------------------------
# Tool checks
# ---------------------------------------------------------------------------


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


def install_hints(platform_info: object | None = None) -> list[str]:
    """Return human-readable install instructions for missing clipboard tools.

    When *platform_info* (a :class:`~prosefmt.platform.PlatformInfo`) is
    provided the hints are narrowed to the single relevant package manager.
    Otherwise a multi-distro fallback is shown.
    """
    missing = check_clipboard_tools()
    if not missing:
        return []

    plat = detect_platform()
    hints: list[str] = []

    if plat == Platform.LINUX_X11:
        packages = [t for t in ("xclip", "xdotool") if not shutil.which(t)]
        if packages:
            hints.extend(_targeted_hints(platform_info, packages, packages))

    elif plat == Platform.LINUX_WAYLAND:
        wl_missing = any(not shutil.which(t) for t in ("wl-copy", "wl-paste"))
        paste_missing = not shutil.which("wtype") and not shutil.which("ydotool")
        packages: list[str] = []
        if wl_missing:
            packages.append("wl-clipboard")
        if paste_missing:
            packages.append("wtype")
        if packages:
            hints.extend(_targeted_hints(platform_info, packages, packages))

    return hints


def _targeted_hints(
    platform_info: object | None,
    packages: list[str],
    fallback_names: list[str],
) -> list[str]:
    """Format install hints — one-line when platform is known, multi-line otherwise."""
    if platform_info is not None:
        cmd = platform_info.install_cmd(*packages)  # type: ignore[union-attr]
        if cmd:
            return [f"  {cmd}"]
    # Fallback: show all common managers
    pkg = " ".join(fallback_names)
    return [
        f"  # Debian / Ubuntu / Mint:   sudo apt install {pkg}",
        f"  # Fedora / RHEL / CentOS:   sudo dnf install {pkg}",
        f"  # Arch / Manjaro:            sudo pacman -S {pkg}",
        f"  # openSUSE:                  sudo zypper install {pkg}",
    ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


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
