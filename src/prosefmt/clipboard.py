"""Cross-platform clipboard helpers with save/restore support.

No external Python dependencies — uses platform-native CLI tools:
  Linux (X11):     xclip / xdotool
  Linux (Wayland): wl-copy / wl-paste / wtype
  macOS:           pbcopy / pbpaste / osascript
  Windows:         clip.exe / Get-Clipboard, SendInput for copy/paste
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from prosefmt.platform import Platform, detect_platform

if TYPE_CHECKING:
    from prosefmt.platform import PlatformInfo


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


# How long to wait for Cmd+C / Ctrl+C to land in the clipboard.
_CAPTURE_TIMEOUT_SECS = 0.6
_CAPTURE_POLL_SECS = 0.05


# ---------------------------------------------------------------------------
# Paste
# ---------------------------------------------------------------------------


def paste_to_active_window() -> bool:
    """Simulate Ctrl+V / Cmd+V in the currently focused window.

    Returns ``True`` if a paste tool was found and invoked, ``False``
    if no tool is available (caller should fall back or error).
    """
    plat = detect_platform()

    if plat == Platform.LINUX_X11:
        subprocess.run(
            ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
            check=False,
            capture_output=True,
        )
        return True

    if plat == Platform.LINUX_WAYLAND:
        if shutil.which("wtype"):
            subprocess.run(
                ["wtype", "-M", "ctrl", "v", "-m", "ctrl"],
                check=False,
                capture_output=True,
            )
            return True
        if shutil.which("ydotool"):
            subprocess.run(
                ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
                check=False,
                capture_output=True,
            )
            return True
        return False

    if plat in (Platform.MACOS, Platform.WINDOWS):
        return _send_ctrl_key("v")

    return False


def capture_selection() -> str:
    """Copy the focused window's selection and return it.

    macOS and Windows have no Linux-style primary selection, so ``--system``
    sends Cmd+C / Ctrl+C, waits until the clipboard changes, and restores the
    previous clipboard contents before returning. The caller then rewrites the
    returned text and pastes it back.

    Returns an empty string when nothing is selected or the copy shortcut
    could not be sent. Linux should keep using :func:`clipboard_read`.
    """
    saved = clipboard_read(selection="clipboard")
    token = f"prosefmt-capture-{time.monotonic_ns()}"
    try:
        clipboard_write(token)
        if not _send_ctrl_key("c"):
            return ""
        deadline = time.monotonic() + _CAPTURE_TIMEOUT_SECS
        while time.monotonic() < deadline:
            current = clipboard_read(selection="clipboard")
            if current and current != token:
                return current
            time.sleep(_CAPTURE_POLL_SECS)
        return ""
    finally:
        clipboard_write(saved)


def _send_ctrl_key(char: str) -> bool:
    """Send Cmd+*char* on macOS or Ctrl+*char* on Windows to the focused window."""
    plat = detect_platform()
    key = char[:1].lower()
    if not key:
        return False

    if plat == Platform.MACOS:
        script = f'tell application "System Events" to keystroke "{key}" using command down'
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
        return True

    if plat == Platform.WINDOWS:
        if os.name == "nt" and _windows_sendinput_ctrl(key):
            return True
        ps_cmd = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            f'[System.Windows.Forms.SendKeys]::SendWait("^{key}")'
        )
        subprocess.run(
            ["powershell.exe", "-Command", ps_cmd],
            check=False,
            capture_output=True,
        )
        return True

    return False


def _windows_sendinput_ctrl(char: str) -> bool:
    """Send Ctrl+*char* with ``SendInput`` so PowerShell does not steal focus.

    Only called when ``os.name == "nt"``. Returns ``False`` if the key was
    not delivered, so the caller can fall back to ``SendKeys``.
    """
    import ctypes
    from ctypes import wintypes

    vk = ord(char.upper())
    user32 = ctypes.windll.user32
    ulong_ptr = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ulong_ptr),
        ]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ulong_ptr),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    class INPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]

        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    input_keyboard = 1
    keyeventf_keyup = 0x0002
    vk_control = 0x11

    def _key(code: int, flags: int = 0) -> INPUT:
        return INPUT(type=input_keyboard, ki=KEYBDINPUT(wVk=code, dwFlags=flags))

    seq = (INPUT * 4)(
        _key(vk_control),
        _key(vk),
        _key(vk, keyeventf_keyup),
        _key(vk_control, keyeventf_keyup),
    )
    sent = user32.SendInput(4, ctypes.byref(seq), ctypes.sizeof(INPUT))
    return sent == 4


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


def install_hints(platform_info: PlatformInfo | None = None) -> list[str]:
    """Return human-readable install instructions for missing clipboard tools.

    When *platform_info* is provided the hints are narrowed to the single
    relevant package manager.  Otherwise a multi-distro fallback is shown.
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
    platform_info: PlatformInfo | None,
    packages: list[str],
    fallback_names: list[str],
) -> list[str]:
    """Format install hints — one-line when platform is known, multi-line otherwise."""
    if platform_info is not None:
        cmd = platform_info.install_cmd(*packages)
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
        # Only strip trailing newlines (tool artifact), preserve leading whitespace
        # so indentation in code snippets survives clipboard round-trips.
        return result.stdout.rstrip("\n") if result.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _run_stdin(cmd: list[str], text: str) -> None:
    with contextlib.suppress(FileNotFoundError, subprocess.TimeoutExpired):
        subprocess.run(cmd, input=text, check=False, capture_output=True, text=True, timeout=5)
