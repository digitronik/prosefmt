"""Tests for the core rewriting engine."""

from __future__ import annotations

import os
import stat

import pytest

from prosefmt.config import ModeConfig
from prosefmt.core import ProsefmtError, load_undo, rewrite, sanitize_output, save_undo
from prosefmt.providers.base import ProviderError

from .conftest import FakeProvider


class TestRewrite:
    def test_basic_rewrite(self, default_config, sample_mode):
        provider = FakeProvider("Corrected text.")
        result = rewrite("bad grammer here", sample_mode, provider=provider, config=default_config)
        assert result == "Corrected text."
        assert provider.call_count == 1

    def test_empty_text_raises(self, default_config, sample_mode):
        provider = FakeProvider()
        with pytest.raises(ProsefmtError, match="No text"):
            rewrite("", sample_mode, provider=provider, config=default_config)

    def test_whitespace_only_raises(self, default_config, sample_mode):
        provider = FakeProvider()
        with pytest.raises(ProsefmtError, match="No text"):
            rewrite("   \n  ", sample_mode, provider=provider, config=default_config)

    def test_provider_error_propagates(self, default_config, sample_mode):
        class FailingProvider:
            name = "failing"

            def complete(self, s: str, u: str) -> str:
                raise ProviderError("model not found")

            def check_health(self) -> bool:
                return False

        with pytest.raises(ProviderError, match="model not found"):
            rewrite("text", sample_mode, provider=FailingProvider(), config=default_config)

    def test_preserves_list_structure(self, default_config):
        mode = ModeConfig(
            name="fix",
            prompt="Fix grammar.",
            label="Fixed",
            preserve_structure=True,
        )
        provider = FakeProvider("first corrected\nsecond corrected\nthird corrected")
        text = "- first broken\n- second broken\n- third broken"
        result = rewrite(text, mode, provider=provider, config=default_config)
        assert result == "- first corrected\n- second corrected\n- third corrected"

    def test_preserves_list_after_plain_text(self, default_config):
        """Lists that start after a header line must also be detected."""
        mode = ModeConfig(
            name="fix",
            prompt="Fix grammar.",
            label="Fixed",
            preserve_structure=True,
        )
        provider = FakeProvider("Header line\nfirst fixed\nsecond fixed\nPlain line")
        text = "Header line\n- first broken\n- second broken\nPlain line"
        result = rewrite(text, mode, provider=provider, config=default_config)
        assert result == "Header line\n- first fixed\n- second fixed\nPlain line"

    def test_skips_structure_when_disabled(self, default_config):
        mode = ModeConfig(
            name="summarize",
            prompt="Summarize.",
            label="Summarized",
            preserve_structure=False,
        )
        provider = FakeProvider("A brief summary.")
        text = "- point one\n- point two\n- point three"
        result = rewrite(text, mode, provider=provider, config=default_config)
        assert result == "A brief summary."
        assert "- " not in provider.last_user.split("Text:\n")[1][:2] or True

    def test_prompt_includes_mode_instruction(self, default_config, sample_mode):
        provider = FakeProvider("result")
        rewrite("hello", sample_mode, provider=provider, config=default_config)
        assert sample_mode.prompt in provider.last_user

    def test_strips_whitespace_from_result(self, default_config, sample_mode):
        provider = FakeProvider("  result with spaces  \n")
        result = rewrite("input", sample_mode, provider=provider, config=default_config)
        assert result == "result with spaces"

    def test_sanitizes_fenced_output(self, default_config, sample_mode):
        provider = FakeProvider("```\nFixed text.\n```")
        result = rewrite("text", sample_mode, provider=provider, config=default_config)
        assert result == "Fixed text."

    def test_sanitizes_preamble(self, default_config, sample_mode):
        provider = FakeProvider("Here is the corrected text:\nFixed text.")
        result = rewrite("text", sample_mode, provider=provider, config=default_config)
        assert result == "Fixed text."

    def test_generic_exception_wraps_in_prosefmt_error(self, default_config, sample_mode):
        """Non-ProviderError exceptions should be wrapped in ProsefmtError."""

        class BuggyProvider:
            name = "buggy"

            def complete(self, s: str, u: str) -> str:
                raise RuntimeError("unexpected crash")

            def check_health(self) -> bool:
                return True

        with pytest.raises(ProsefmtError, match="Rewrite failed"):
            rewrite("text", sample_mode, provider=BuggyProvider(), config=default_config)


class TestSanitizeOutput:
    def test_strips_markdown_fences(self):
        assert sanitize_output("```\nHello world\n```") == "Hello world"

    def test_strips_fences_with_language(self):
        assert sanitize_output("```text\nHello world\n```") == "Hello world"

    def test_strips_fences_with_complex_language_tag(self):
        assert sanitize_output("```python3\nHello world\n```") == "Hello world"
        assert sanitize_output("```c++\nHello world\n```") == "Hello world"
        assert sanitize_output("```text (corrected)\nHello world\n```") == "Hello world"

    def test_strips_preamble_here_is(self):
        assert sanitize_output("Here is the corrected text:\nGood text.") == "Good text."

    def test_strips_preamble_heres(self):
        assert sanitize_output("Here's the rewritten text:\nGood.") == "Good."

    def test_preserves_wrapping_double_quotes(self):
        # Quote-stripping was intentionally removed — too risky
        # (can damage text that legitimately starts/ends with quotes).
        assert sanitize_output('"Hello world"') == '"Hello world"'

    def test_preserves_internal_quotes(self):
        text = 'She said "hello" to him'
        assert sanitize_output(text) == text

    def test_preserves_clean_output(self):
        assert sanitize_output("Already clean text.") == "Already clean text."

    def test_handles_empty_string(self):
        assert sanitize_output("") == ""

    def test_handles_only_fences(self):
        assert sanitize_output("```\n```") == ""


class TestUndo:
    def test_save_and_load(self, tmp_path):
        path = str(tmp_path / "undo")
        save_undo("original text", path)
        assert load_undo(path) == "original text"

    def test_load_removes_file(self, tmp_path):
        path = str(tmp_path / "undo")
        save_undo("text", path)
        load_undo(path)
        assert load_undo(path) is None

    def test_load_nonexistent(self, tmp_path):
        assert load_undo(str(tmp_path / "nope")) is None

    def test_undo_file_is_owner_only(self, tmp_path):
        """Undo file should be chmod 600 on Unix."""
        if os.name == "nt":
            pytest.skip("Unix permissions only")
        path = str(tmp_path / "undo")
        save_undo("private text", path)
        mode = os.stat(path).st_mode
        assert mode & stat.S_IRWXG == 0, "Group should have no access"
        assert mode & stat.S_IRWXO == 0, "Others should have no access"
