"""Tests for the text diff formatting module."""

from __future__ import annotations

from prosefmt.diff import format_diff, has_changes


class TestHasChanges:
    def test_identical_texts(self):
        assert has_changes("hello", "hello") is False

    def test_different_texts(self):
        assert has_changes("hello", "world") is True

    def test_empty_strings(self):
        assert has_changes("", "") is False

    def test_whitespace_difference(self):
        assert has_changes("hello ", "hello") is True

    def test_newline_difference(self):
        assert has_changes("hello\nworld", "hello\nearth") is True


class TestFormatDiff:
    def test_identical_returns_empty(self):
        assert format_diff("hello", "hello") == ""

    def test_basic_diff_no_color(self):
        original = "Their were a few things we didnt finish"
        result = "There were a few things we didn't finish"
        diff = format_diff(original, result, color=False)
        assert diff != ""
        assert "---" in diff
        assert "+++" in diff
        assert "-Their were" in diff or "- Their" in diff
        assert "+There were" in diff or "+ There" in diff

    def test_multiline_diff_no_color(self):
        original = "line one\nline two\nline three"
        result = "line one\nline TWO\nline three"
        diff = format_diff(original, result, color=False)
        assert "-line two" in diff
        assert "+line TWO" in diff
        # Context lines should appear
        assert "line one" in diff

    def test_color_output_contains_ansi(self):
        original = "hello"
        result = "world"
        diff = format_diff(original, result, color=True)
        assert "\033[" in diff  # ANSI escape codes

    def test_no_color_output_no_ansi(self):
        original = "hello"
        result = "world"
        diff = format_diff(original, result, color=False)
        assert "\033[" not in diff

    def test_fromfile_tofile_labels(self):
        diff = format_diff("old", "new", color=False)
        assert "original" in diff
        assert "rewritten" in diff

    def test_context_lines_parameter(self):
        lines_orig = [f"line {i}" for i in range(20)]
        lines_new = lines_orig.copy()
        lines_new[10] = "CHANGED line 10"
        original = "\n".join(lines_orig)
        result = "\n".join(lines_new)

        # With 1 context line, we should see fewer surrounding lines
        diff_1 = format_diff(original, result, context_lines=1, color=False)
        diff_5 = format_diff(original, result, context_lines=5, color=False)
        # More context = longer diff
        assert len(diff_5) > len(diff_1)

    def test_added_lines(self):
        original = "line one\nline two"
        result = "line one\nline two\nline three"
        diff = format_diff(original, result, color=False)
        assert "+line three" in diff

    def test_removed_lines(self):
        original = "line one\nline two\nline three"
        result = "line one\nline three"
        diff = format_diff(original, result, color=False)
        assert "-line two" in diff
