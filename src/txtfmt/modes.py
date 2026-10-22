"""Built-in rewrite modes and list-structure preservation logic."""

from __future__ import annotations

import re

BUILTIN_MODES: dict[str, dict] = {
    "fix": {
        "name": "fix",
        "prompt": "Fix grammar, spelling, and punctuation only. Do not add or remove sentences.",
        "label": "Grammar fixed",
        "preserve_structure": True,
    },
    "professional": {
        "name": "professional",
        "prompt": "Rewrite in a professional tone suitable for workplace emails and Slack.",
        "label": "Made professional",
        "preserve_structure": True,
    },
    "casual": {
        "name": "casual",
        "prompt": "Rewrite in a casual, friendly, conversational tone.",
        "label": "Made casual",
        "preserve_structure": True,
    },
    "rephrase": {
        "name": "rephrase",
        "prompt": "Rephrase for better clarity and flow without changing the meaning.",
        "label": "Rephrased",
        "preserve_structure": True,
    },
    "summarize": {
        "name": "summarize",
        "prompt": "Summarize concisely, keeping the key points.",
        "label": "Summarized",
        "preserve_structure": False,
    },
    "email": {
        "name": "email",
        "prompt": "Rewrite as a professional email with an appropriate greeting and sign-off.",
        "label": "Formatted as email",
        "preserve_structure": False,
    },
    "concise": {
        "name": "concise",
        "prompt": "Make the text more concise — same meaning, fewer words.",
        "label": "Made concise",
        "preserve_structure": True,
    },
    "expand": {
        "name": "expand",
        "prompt": "Expand the text with more detail and explanation, keeping the same meaning.",
        "label": "Expanded",
        "preserve_structure": True,
    },
}

_BULLET_RE = re.compile(r"^(\s*[-*\u2022+\u00b7]\s+)(.*)")
_NUMBER_RE = re.compile(r"^(\s*\d+\.\s+)(.*)")


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
