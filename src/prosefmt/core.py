"""Core rewriting engine — the brain of prosefmt."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from prosefmt.modes import has_list_structure, restore_list_prefixes, strip_list_prefixes
from prosefmt.providers.base import ProviderError

if TYPE_CHECKING:
    from prosefmt.config import Config, ModeConfig
    from prosefmt.providers.base import Provider


class ProsefmtError(Exception):
    """Top-level error for rewriting failures."""


# Patterns that small local models commonly wrap around their output.
# [^\n]* on the fence opener handles ```text, ```python3, ``` (trailing space), etc.
_FENCE_RE = re.compile(r"^```[^\n]*\n(.*?)```\s*$", re.DOTALL)
_PREAMBLE_RE = re.compile(
    r"^(?:Here(?:'s| is)(?: the)? (?:corrected|rewritten|revised|updated|fixed)"
    r"[^:\n]*:\s*)",
    re.IGNORECASE,
)


def sanitize_output(text: str) -> str:
    """Strip common model artifacts — markdown fences and preamble lines.

    Small local models (1.5B-3B) often ignore "output ONLY the text"
    instructions and wrap their answer in markdown fences or add a
    leading "Here is the corrected text:" line.  This function strips
    those artifacts conservatively.
    """
    text = text.strip()

    # Strip markdown code fences: ```...\n content \n```
    m = _FENCE_RE.match(text)
    if m:
        text = m.group(1).strip()

    # Strip known preamble patterns
    text = _PREAMBLE_RE.sub("", text, count=1)

    return text.strip()


def rewrite(text: str, mode: ModeConfig, *, provider: Provider, config: Config) -> str:
    """Rewrite *text* according to *mode* using the given *provider*.

    Handles list-structure preservation and output sanitization
    automatically.
    """
    if not text.strip():
        raise ProsefmtError("No text to rewrite")

    text_to_send = text
    prefixes: list[str] | None = None

    if mode.preserve_structure and has_list_structure(text):
        prefixes, text_to_send = strip_list_prefixes(text)

    user_prompt = f"{mode.prompt}\n\nText:\n{text_to_send}"

    try:
        result = provider.complete(config.system_prompt, user_prompt)
    except ProviderError:
        raise
    except Exception as exc:
        raise ProsefmtError(f"Rewrite failed: {exc}") from exc

    result = sanitize_output(result)

    if prefixes:
        result = restore_list_prefixes(result, prefixes)

    return result


def save_undo(text: str, undo_path: str) -> None:
    """Save the original text so it can be restored later."""
    import os
    import stat

    p = Path(undo_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    # Restrict to owner-only — undo may contain private text.
    if os.name != "nt":
        p.chmod(stat.S_IRUSR | stat.S_IWUSR)


def load_undo(undo_path: str) -> str | None:
    """Load the saved original text, or None if nothing to undo."""
    p = Path(undo_path)
    if p.exists():
        text = p.read_text(encoding="utf-8")
        p.unlink()
        return text
    return None
