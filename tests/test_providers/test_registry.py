"""Tests for providers/__init__.py — the get_provider factory."""

from __future__ import annotations

import pytest

from prosefmt.config import ProviderConfig
from prosefmt.providers import ProviderError, get_provider
from prosefmt.providers.anthropic import AnthropicProvider
from prosefmt.providers.ollama import OllamaProvider
from prosefmt.providers.openai_compat import OpenAICompatProvider


class TestGetProvider:
    """Test provider factory dispatches and constructs correctly."""

    def test_ollama_by_name(self, app_config, ollama_pconfig):
        prov = get_provider("ollama", ollama_pconfig, app_config)
        assert isinstance(prov, OllamaProvider)
        assert prov.name == "ollama"
        assert prov.model == "qwen2.5:1.5b"

    def test_openai_by_name(self, app_config, openai_pconfig):
        prov = get_provider("openai", openai_pconfig, app_config)
        assert isinstance(prov, OpenAICompatProvider)
        assert prov.name == "openai-compat"

    def test_openai_compat_by_name(self, app_config):
        pc = ProviderConfig(name="openai-compat", url="http://localhost:8080/v1", model="local")
        prov = get_provider("openai-compat", pc, app_config)
        assert isinstance(prov, OpenAICompatProvider)

    def test_anthropic_by_name(self, app_config, anthropic_pconfig):
        prov = get_provider("anthropic", anthropic_pconfig, app_config)
        assert isinstance(prov, AnthropicProvider)
        assert prov.name == "anthropic"

    def test_custom_name_with_type_field(self, app_config):
        """A provider named 'groq' with type='openai-compat' should use OpenAICompat."""
        pc = ProviderConfig(
            name="groq",
            type="openai-compat",
            url="https://api.groq.com/openai/v1",
            model="llama-3.3-70b",
            api_key="gsk-test",
        )
        prov = get_provider("groq", pc, app_config)
        assert isinstance(prov, OpenAICompatProvider)
        assert prov.api_key == "gsk-test"

    def test_type_field_overrides_name(self, app_config):
        """Explicit type should take precedence over provider name."""
        pc = ProviderConfig(
            name="my-ollama", type="ollama", url="http://my-server:11434", model="qwen2.5:3b"
        )
        prov = get_provider("my-ollama", pc, app_config)
        assert isinstance(prov, OllamaProvider)

    def test_unknown_type_raises(self, app_config):
        pc = ProviderConfig(name="fakeprov", type="faketype")
        with pytest.raises(ProviderError, match="Unknown provider type"):
            get_provider("fakeprov", pc, app_config)

    def test_unknown_name_no_type_raises(self, app_config):
        pc = ProviderConfig(name="badname")
        with pytest.raises(ProviderError, match="Unknown provider type"):
            get_provider("badname", pc, app_config)

    def test_temperature_from_config(self, app_config, ollama_pconfig):
        """Provider should receive effective temperature from config."""
        app_config.temperature = 0.5
        prov = get_provider("ollama", ollama_pconfig, app_config)
        assert prov.temperature == 0.5

    def test_provider_temperature_override(self, app_config, ollama_pconfig):
        """Per-provider temperature should override global."""
        app_config.temperature = 0.5
        ollama_pconfig.temperature = 0.2
        prov = get_provider("ollama", ollama_pconfig, app_config)
        assert prov.temperature == 0.2

    def test_seed_from_config(self, app_config, ollama_pconfig):
        """Provider should receive effective seed from config."""
        app_config.seed = 99
        prov = get_provider("ollama", ollama_pconfig, app_config)
        assert prov.seed == 99

    def test_seed_none_from_config(self, app_config, ollama_pconfig):
        app_config.seed = None
        prov = get_provider("ollama", ollama_pconfig, app_config)
        assert prov.seed is None

    def test_api_key_passed_to_openai(self, app_config, openai_pconfig):
        prov = get_provider("openai", openai_pconfig, app_config)
        assert prov.api_key == "sk-test"

    def test_api_key_passed_to_anthropic(self, app_config, anthropic_pconfig):
        prov = get_provider("anthropic", anthropic_pconfig, app_config)
        assert prov.api_key == "sk-ant-test"
