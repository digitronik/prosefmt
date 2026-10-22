"""Core rewriting engine — the brain of Reword."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from reword.modes import has_list_structure, restore_list_prefixes, strip_list_prefixes
from reword.providers.base import ProviderError

if TYPE_CHECKING:
    from reword.config import Config, ModeConfig
    from reword.providers.base import Provider


class RewordError(Exception):
    """Top-level error for rewriting failures."""


def rewrite(text: str, mode: ModeConfig, *, provider: Provider, config: Config) -> str:
    """Rewrite *text* according to *mode* using the given *provider*.

    Handles list-structure preservation automatically for modes that
    request it.
    """
    if not text.strip():
        raise RewordError("No text to rewrite")

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
        raise RewordError(f"Rewrite failed: {exc}") from exc

    result = result.strip()

    if prefixes:
        result = restore_list_prefixes(result, prefixes)

    return result


def save_undo(text: str, undo_path: str) -> None:
    """Save the original text so it can be restored later."""
    Path(undo_path).write_text(text)


def load_undo(undo_path: str) -> str | None:
    """Load the saved original text, or None if nothing to undo."""
    p = Path(undo_path)
    if p.exists():
        text = p.read_text()
        p.unlink()
        return text
    return None
