"""Platform-aware mode picker — wraps native system menu tools.

Tool priority (first found on PATH wins):
  rofi     — best on i3 / X11; modern builds also work on Wayland
  wofi     — Wayland-native (sway, hyprland)
  fuzzel   — Wayland-native, minimal
  dmenu    — lightweight X11 fallback
  zenity   — GTK dialog, works anywhere with a display server
  fzf      — terminal-based, always works if installed

All tools except zenity support free-form input: the user can type a custom
prompt that is not in the mode list and it will be returned as-is, letting
``prosefmt menu`` use it as an ad-hoc one-shot instruction.

Usage::

    from prosefmt.picker import pick, best_picker, check_picker_tools

    choice = pick(["fix", "rephrase", "summarize"])
    if choice is None:
        sys.exit(0)          # user cancelled
    if choice in config.modes:
        run_mode(choice)     # known mode
    else:
        run_adhoc(choice)    # custom prompt
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Priority order: first tool found on PATH is used.
# osascript (macOS native) is last — fzf is preferred when available.
_PICKER_PRIORITY: list[str] = ["rofi", "wofi", "fuzzel", "dmenu", "zenity", "fzf", "osascript"]

# Pen-to-square icon (Font Awesome 6 Free Solid \uf044) + label
_DEFAULT_PROMPT = "\uf044 prosefmt"


def available_pickers() -> list[str]:
    """Return all picker tools found on PATH, in priority order."""
    return [t for t in _PICKER_PRIORITY if shutil.which(t)]


def best_picker() -> str | None:
    """Return the name of the highest-priority available picker, or None."""
    found = available_pickers()
    return found[0] if found else None


def pick(choices: list[str], prompt: str = _DEFAULT_PROMPT) -> str | None:
    """Show an interactive picker and return the user's selection.

    Returns:
        A string from ``choices`` (user selected a mode), or a free-form
        string the user typed (treat as a custom one-shot prompt), or
        ``None`` if the user cancelled / no picker is available.
    """
    tool = best_picker()
    if tool is None:
        return None
    fn = _DISPATCHERS.get(tool)
    return fn(choices, prompt) if fn else None


def check_picker_tools() -> dict[str, bool]:
    """Return availability status for all known picker tools.

    Returns a dict ``{tool_name: is_installed}`` in priority order.
    """
    return {t: shutil.which(t) is not None for t in _PICKER_PRIORITY}


def install_hints_picker(platform_info: object | None = None) -> list[str]:
    """Return human-readable install suggestions for picker tools.

    When *platform_info* (a :class:`~prosefmt.platform.PlatformInfo`) is
    provided the hints are narrowed to the relevant package manager.
    """
    if best_picker() is not None:
        return []

    if platform_info is not None:
        os_name: str = getattr(platform_info, "os", "")
        display: str = getattr(platform_info, "display", "")
        install_cmd = getattr(platform_info, "install_cmd", None)

        if os_name == "macos":
            return ["  Install:  brew install fzf"]

        if os_name == "linux" and install_cmd is not None:
            tool = "wofi" if display == "wayland" else "rofi"
            cmd = install_cmd(tool)
            if cmd:
                alt = "rofi" if tool == "wofi" else "fzf"
                return [f"  Install:  {cmd}  (or: {alt})"]

    # Fallback — show all common options
    return [
        "  Install at least one picker tool:",
        "  # Fedora / RHEL:  sudo dnf install rofi",
        "  # Ubuntu / Mint:  sudo apt install rofi",
        "  # Arch / Manjaro: sudo pacman -S rofi",
        "  # Wayland users:  sudo dnf install wofi   (or: fuzzel)",
        "  # macOS:          brew install fzf",
    ]


# ---------------------------------------------------------------------------
# Per-tool implementations
# ---------------------------------------------------------------------------


def _pick_rofi(choices: list[str], prompt: str) -> str | None:
    """rofi in dmenu mode — supports free-form input by default."""
    result = subprocess.run(
        [
            "rofi",
            "-dmenu",
            "-i",
            "-p",
            prompt,
            "-theme-str",
            "window {width: 28%;}",
        ],
        input="\n".join(choices),
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or None


def _pick_wofi(choices: list[str], prompt: str) -> str | None:
    """wofi in dmenu mode — Wayland-native."""
    result = subprocess.run(
        ["wofi", "--dmenu", "--prompt", prompt],
        input="\n".join(choices),
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or None


def _pick_fuzzel(choices: list[str], prompt: str) -> str | None:
    """fuzzel in dmenu mode — Wayland-native."""
    result = subprocess.run(
        ["fuzzel", "--dmenu", f"--prompt={prompt}: "],
        input="\n".join(choices),
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or None


def _pick_dmenu(choices: list[str], prompt: str) -> str | None:
    """Classic dmenu — minimal X11 picker."""
    result = subprocess.run(
        ["dmenu", "-p", prompt],
        input="\n".join(choices),
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or None


def _pick_zenity(choices: list[str], prompt: str) -> str | None:
    """zenity --list — GTK dialog.

    Does not support free-form input natively, so a "Custom prompt…"
    entry is appended; selecting it opens a zenity --entry dialog.
    """
    _CUSTOM = "Custom prompt…"
    result = subprocess.run(
        [
            "zenity",
            "--list",
            "--title",
            prompt,
            "--column",
            "Mode",
            "--hide-header",
            "--width",
            "320",
            "--height",
            "400",
            *choices,
            _CUSTOM,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    choice = result.stdout.strip()
    if not choice or choice == _CUSTOM:
        if choice != _CUSTOM:
            return None
        # Ask for custom text
        entry = subprocess.run(
            [
                "zenity",
                "--entry",
                "--title",
                prompt,
                "--text",
                "Enter your prompt:",
            ],
            capture_output=True,
            text=True,
        )
        return entry.stdout.strip() or None
    return choice


def _pick_fzf(choices: list[str], prompt: str) -> str | None:
    """fzf — terminal-based, supports free-form via --print-query.

    Exit codes:
      0   → match selected; stdout: query\\nselection
      1   → no match; stdout: query
      130 → user cancelled (Esc / Ctrl-C)
    """
    result = subprocess.run(
        ["fzf", "--prompt", f"{prompt}> ", "--print-query"],
        input="\n".join(choices),
        capture_output=True,
        text=True,
    )
    lines = result.stdout.strip().splitlines()
    if result.returncode == 130 or not lines:
        return None  # cancelled
    if result.returncode == 0 and len(lines) >= 2:
        return lines[-1]  # selected item from list
    return lines[0] or None  # free-form query (returncode == 1)


def _pick_osascript(choices: list[str], prompt: str) -> str | None:
    """macOS native list picker via ``choose from list``.

    Does not support free-form input — user must select from the list.
    Install ``fzf`` (``brew install fzf``) for free-form support.
    """
    items = ", ".join(f'"{c}"' for c in choices)
    esc_prompt = prompt.replace("\\", "\\\\").replace('"', '\\"')
    script = f'choose from list {{{items}}} with title "prosefmt" with prompt "{esc_prompt}"'
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    choice = result.stdout.strip()
    if choice == "false":
        return None
    return choice


_DISPATCHERS: dict[str, Callable[[list[str], str], str | None]] = {
    "rofi": _pick_rofi,
    "wofi": _pick_wofi,
    "fuzzel": _pick_fuzzel,
    "dmenu": _pick_dmenu,
    "zenity": _pick_zenity,
    "fzf": _pick_fzf,
    "osascript": _pick_osascript,
}
