"""List-structure preservation logic for rewrite modes.

Bullets and numbered lists are stripped before sending text to the AI
(so the model never loses or mangles them), then re-attached to the result.

All mode definitions — prompts, labels, defaults — live in
``default_config.toml`` (the single source of truth).  Python code
never hardcodes prompt text.
"""

from __future__ import annotations

import re

_BULLET_RE = re.compile(r"^(\s*[-*\u2022+\u00b7]\s+)(.*)", re.MULTILINE)
_NUMBER_RE = re.compile(r"^(\s*\d+[\.\)]\s+)(.*)", re.MULTILINE)


def strip_list_prefixes(text: str) -> tuple[list[str], str]:
    """Strip bullet / number prefixes so the model never sees (or loses) them.

    Returns (prefixes, stripped_text).  Each prefix corresponds to a line;
    empty string means the line had no list prefix.
    """
    prefixes: list[str] = []
    stripped_lines: list[str] = []

    for line in text.split("\n"):
        m = _BULLET_RE.match(line) or _NUMBER_RE.match(line)
        if m:
            prefixes.append(m.group(1))
            stripped_lines.append(m.group(2))
        else:
            prefixes.append("")
            stripped_lines.append(line)

    return prefixes, "\n".join(stripped_lines)


def restore_list_prefixes(text: str, prefixes: list[str]) -> str:
    """Re-attach previously stripped list prefixes to the model output."""
    lines = text.split("\n")

    if len(lines) != len(prefixes) or not any(prefixes):
        return text

    return "\n".join(p + line for p, line in zip(prefixes, lines, strict=False))


def has_list_structure(text: str) -> bool:
    """Quick check whether the text contains bullet / numbered lists."""
    return bool(_BULLET_RE.search(text) or _NUMBER_RE.search(text))
