"""Shared fixtures for provider tests."""

from __future__ import annotations

import pytest

from prosefmt.config import Config, ProviderConfig


@pytest.fixture()
def app_config(tmp_path) -> Config:
    """A Config with defaults and a temp undo file."""
    config = Config.load()
    config.undo_file = str(tmp_path / "undo")
    return config


@pytest.fixture()
def ollama_pconfig() -> ProviderConfig:
    return ProviderConfig(name="ollama", url="http://localhost:11434", model="qwen2.5:1.5b")


@pytest.fixture()
def openai_pconfig() -> ProviderConfig:
    return ProviderConfig(
        name="openai", url="https://api.openai.com/v1", model="gpt-4o-mini", api_key="sk-test"
    )


@pytest.fixture()
def anthropic_pconfig() -> ProviderConfig:
    return ProviderConfig(
        name="anthropic",
        url="https://api.anthropic.com",
        model="claude-haiku-4-5-20251001",
        api_key="sk-ant-test",
    )
