"""Text diff formatting — show what changed between original and result.

Produces a human-readable unified diff suitable for terminal output or
popup display.

Usage::

    from prosefmt.diff import format_diff, has_changes

    diff_text = format_diff(original, result)
    if has_changes(original, result):
        print(diff_text)
"""

from __future__ import annotations

import difflib


def format_diff(
    original: str,
    result: str,
    *,
    context_lines: int = 3,
    color: bool = True,
) -> str:
    """Produce a unified diff between *original* and *result*.

    Args:
        original: The text before rewriting.
        result: The text after rewriting.
        context_lines: Number of surrounding context lines (default 3).
        color: Whether to add ANSI colour codes (red/green).

    Returns:
        A formatted diff string. Empty string if texts are identical.
    """
    if original == result:
        return ""

    original_lines = original.splitlines(keepends=True)
    result_lines = result.splitlines(keepends=True)

    # Ensure final newlines for clean diff output
    if original_lines and not original_lines[-1].endswith("\n"):
        original_lines[-1] += "\n"
    if result_lines and not result_lines[-1].endswith("\n"):
        result_lines[-1] += "\n"

    diff_lines = list(
        difflib.unified_diff(
            original_lines,
            result_lines,
            fromfile="original",
            tofile="rewritten",
            n=context_lines,
        )
    )

    if not diff_lines:
        return ""

    if color:
        diff_lines = [_colorize_line(line) for line in diff_lines]

    return "".join(diff_lines)


def has_changes(original: str, result: str) -> bool:
    """Return True if there are any differences between original and result."""
    return original != result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# ANSI colour codes
_RED = "\033[31m"
_GREEN = "\033[32m"
_CYAN = "\033[36m"
_RESET = "\033[0m"
_BOLD = "\033[1m"


def _colorize_line(line: str) -> str:
    """Add ANSI colour to a unified diff line."""
    if line.startswith("---") or line.startswith("+++"):
        return f"{_BOLD}{line}{_RESET}"
    if line.startswith("@@"):
        return f"{_CYAN}{line}{_RESET}"
    if line.startswith("-"):
        return f"{_RED}{line}{_RESET}"
    if line.startswith("+"):
        return f"{_GREEN}{line}{_RESET}"
    return line
