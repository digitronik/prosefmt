"""Desktop popup display — shows AI results without replacing the original text.

Tool priority (first found on PATH wins):
  zenity   — GTK dialog, scrollable text-info window
  yad      — zenity fork with better features
  kdialog  — KDE native dialog
  rofi     — can display text in dmenu/message mode
  notify-send — last resort, short text only (no scroll, not copyable)

All tools display the result in a popup window that the user can read and
optionally copy from. The original text is never modified.

Usage::

    from prosefmt.popup import show_popup, best_popup, check_popup_tools

    show_popup("Translated text here", title="prosefmt — Translated to English")
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Priority order: first tool found on PATH is used.
_POPUP_PRIORITY: list[str] = ["zenity", "yad", "kdialog", "rofi", "notify-send"]

# Max characters for notify-send fallback (no scrolling)
_NOTIFY_MAX_CHARS = 300


def available_popups() -> list[str]:
    """Return all popup tools found on PATH, in priority order."""
    return [t for t in _POPUP_PRIORITY if shutil.which(t)]


def best_popup() -> str | None:
    """Return the name of the highest-priority available popup tool, or None."""
    found = available_popups()
    return found[0] if found else None


def show_popup(text: str, title: str = "prosefmt") -> bool:
    """Display *text* in a desktop popup window.

    Returns True if a popup was shown, False if no tool is available
    (caller should fall back to stdout).
    """
    tool = best_popup()
    if tool is None:
        return False
    fn = _DISPATCHERS.get(tool)
    if fn is None:
        return False
    return fn(text, title)


def check_popup_tools() -> dict[str, bool]:
    """Return availability status for all known popup tools.

    Returns a dict ``{tool_name: is_installed}`` in priority order.
    """
    return {t: shutil.which(t) is not None for t in _POPUP_PRIORITY}


def install_hints_popup() -> list[str]:
    """Return human-readable install suggestions for popup tools."""
    if best_popup() is not None:
        return []
    return [
        "  Install at least one popup tool:",
        "  # Fedora / RHEL:  sudo dnf install zenity",
        "  # Ubuntu / Mint:  sudo apt install zenity",
        "  # Arch / Manjaro: sudo pacman -S zenity",
        "  # KDE users:      kdialog is usually pre-installed",
        "  # Wayland/i3:     rofi can also display popups",
    ]


# ---------------------------------------------------------------------------
# Per-tool implementations
# ---------------------------------------------------------------------------


def _popup_zenity(text: str, title: str) -> bool:
    """zenity --text-info — scrollable, copyable GTK dialog."""
    subprocess.run(
        [
            "zenity",
            "--text-info",
            "--title",
            title,
            "--width",
            "600",
            "--height",
            "400",
            "--font",
            "monospace 11",
        ],
        input=text,
        capture_output=True,
        text=True,
        check=False,
    )
    return True


def _popup_yad(text: str, title: str) -> bool:
    """yad --text-info — zenity fork, richer features."""
    subprocess.run(
        [
            "yad",
            "--text-info",
            "--title",
            title,
            "--width",
            "600",
            "--height",
            "400",
            "--fontname",
            "monospace 11",
            "--button",
            "OK:0",
        ],
        input=text,
        capture_output=True,
        text=True,
        check=False,
    )
    return True


def _popup_kdialog(text: str, title: str) -> bool:
    """kdialog --textbox — KDE native dialog (reads from a temp file)."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(text)
        tmpfile = f.name

    try:
        subprocess.run(
            ["kdialog", "--title", title, "--textbox", tmpfile, "600", "400"],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        import os

        os.unlink(tmpfile)
    return True


def _popup_rofi(text: str, title: str) -> bool:
    """rofi -e — display text in a message window."""
    subprocess.run(
        [
            "rofi",
            "-e",
            text,
            "-p",
            title,
            "-theme-str",
            "window {width: 50%;}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return True


def _popup_notify(text: str, title: str) -> bool:
    """notify-send — last resort, truncates long text (not scrollable)."""
    display_text = text
    if len(text) > _NOTIFY_MAX_CHARS:
        display_text = text[:_NOTIFY_MAX_CHARS] + "\n\n… (truncated — install zenity for full text)"

    subprocess.run(
        [
            "notify-send",
            "-u",
            "normal",
            "-t",
            "30000",
            "-h",
            "string:x-dunst-stack-tag:prosefmt",
            title,
            display_text,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return True


_DISPATCHERS: dict[str, Callable[[str, str], bool]] = {
    "zenity": _popup_zenity,
    "yad": _popup_yad,
    "kdialog": _popup_kdialog,
    "rofi": _popup_rofi,
    "notify-send": _popup_notify,
}
