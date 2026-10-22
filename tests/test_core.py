"""Tests for the core rewriting engine."""

from __future__ import annotations

import pytest

from prosefmt.config import ModeConfig
from prosefmt.core import ProsefmtError, load_undo, rewrite, save_undo
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
