"""Shared test fixtures."""

from __future__ import annotations

import pytest

from txtfmt.config import Config, ModeConfig, ProviderConfig


@pytest.fixture()
def default_config(tmp_path) -> Config:
    """A Config with defaults and a temp undo file."""
    config = Config.load()
    config.undo_file = str(tmp_path / "undo")
    return config


@pytest.fixture()
def sample_mode() -> ModeConfig:
    return ModeConfig(
        name="fix",
        prompt="Fix grammar, spelling, and punctuation only.",
        label="Grammar fixed",
        preserve_structure=True,
    )


@pytest.fixture()
def ollama_provider_config() -> ProviderConfig:
    return ProviderConfig(
        name="ollama",
        url="http://localhost:11434",
        model="qwen2.5:1.5b",
    )


class FakeProvider:
    """A test double that returns a fixed response."""

    def __init__(self, response: str = "Fixed text.") -> None:
        self._response = response
        self.last_system: str = ""
        self.last_user: str = ""
        self.call_count: int = 0

    @property
    def name(self) -> str:
        return "fake"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.last_system = system_prompt
        self.last_user = user_prompt
        self.call_count += 1
        return self._response

    def check_health(self) -> bool:
        return True


@pytest.fixture()
def fake_provider() -> FakeProvider:
    return FakeProvider()
