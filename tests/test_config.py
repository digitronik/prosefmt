"""Tests for configuration loading and merging."""

from __future__ import annotations

from pathlib import Path

import pytest

from prosefmt.config import Config, init_config


class TestConfigDefaults:
    def test_default_mode_is_fix(self):
        config = Config.load()
        assert config.default_mode == "fix"

    def test_default_provider_is_ollama(self):
        config = Config.load()
        assert config.default_provider == "ollama"

    def test_default_modes_exist(self):
        config = Config.load()
        assert "fix" in config.modes
        assert "professional" in config.modes
        assert "casual" in config.modes
        assert "rephrase" in config.modes
        assert "summarize" in config.modes
        assert "email" in config.modes
        assert "concise" in config.modes
        assert "expand" in config.modes

    def test_default_providers_exist(self):
        config = Config.load()
        assert "ollama" in config.providers
        assert "openai" in config.providers
        assert "anthropic" in config.providers

    def test_system_prompt_is_set(self):
        config = Config.load()
        assert len(config.system_prompt) > 50

    def test_default_sampling(self):
        config = Config.load()
        assert config.temperature == 0.1
        assert config.seed == 42


class TestConfigFromFile:
    def test_load_custom_provider(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("""\
default_provider = "openai"

[providers.openai]
model = "gpt-4o"
""")
        config = Config.load(cfg_file)
        assert config.default_provider == "openai"
        assert config.providers["openai"].model == "gpt-4o"

    def test_load_custom_mode(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("""\
[modes.translate]
prompt = "Translate to French."
label = "Translated"
""")
        config = Config.load(cfg_file)
        assert "translate" in config.modes
        assert config.modes["translate"].prompt == "Translate to French."
        assert config.modes["translate"].label == "Translated"
        assert "fix" in config.modes

    def test_override_builtin_mode(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("""\
[modes.fix]
prompt = "Custom fix prompt."
label = "Custom fixed"
""")
        config = Config.load(cfg_file)
        assert config.modes["fix"].prompt == "Custom fix prompt."

    def test_custom_system_prompt(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text('system_prompt = "Be concise."')
        config = Config.load(cfg_file)
        assert config.system_prompt == "Be concise."

    def test_sampling_from_file(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("temperature = 0.5\nseed = 7\n")
        config = Config.load(cfg_file)
        assert config.temperature == 0.5
        assert config.seed == 7

    def test_provider_sampling_override(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("""\
[providers.ollama]
temperature = 0.2
seed = 99
""")
        config = Config.load(cfg_file)
        pc = config.providers["ollama"]
        assert config.effective_temperature(pc) == 0.2
        assert config.effective_seed(pc) == 99

    def test_mode_temperature_from_file(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("""\
[modes.fix]
prompt = "Fix grammar."
temperature = 0.05
""")
        config = Config.load(cfg_file)
        assert config.modes["fix"].temperature == 0.05

    def test_builtin_mode_temperature_defaults(self, tmp_path: Path):
        config = Config.load(tmp_path / "nope.toml")
        assert config.modes["fix"].temperature is None
        assert config.modes["summarize"].temperature == 0.4
        assert config.modes["rephrase"].temperature == 0.4
        assert config.modes["expand"].temperature == 0.4

    def test_nonexistent_file_uses_defaults(self, tmp_path: Path):
        config = Config.load(tmp_path / "nope.toml")
        assert config.default_provider == "ollama"
        assert "fix" in config.modes


class TestDefaultMode:
    def test_default_mode_from_file(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text('default_mode = "professional"\n')
        config = Config.load(cfg_file)
        assert config.default_mode == "professional"

    def test_default_mode_fallback(self, tmp_path: Path):
        config = Config.load(tmp_path / "nope.toml")
        assert config.default_mode == "fix"


class TestConfigEnv:
    def test_openai_key_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
        config = Config.load(tmp_path / "nope.toml")
        assert config.providers["openai"].api_key == "sk-test-123"

    def test_prosefmt_env_takes_priority(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("OPENAI_API_KEY", "generic")
        monkeypatch.setenv("PROSEFMT_OPENAI_API_KEY", "specific")
        config = Config.load(tmp_path / "nope.toml")
        assert config.providers["openai"].api_key == "specific"


class TestModeProviderOverride:
    def test_per_mode_provider_parsed(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("""\
[modes.review]
prompt = "Review this."
label = "Reviewed"
provider = "openai"
model = "gpt-4o"
""")
        config = Config.load(cfg_file)
        assert config.modes["review"].provider == "openai"
        assert config.modes["review"].model == "gpt-4o"

    def test_per_mode_default_output_parsed(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("""\
[modes.summarize]
prompt = "Summarize."
default_output = "popup"
""")
        config = Config.load(cfg_file)
        assert config.modes["summarize"].default_output == "popup"

    def test_mode_without_override_has_none(self, tmp_path: Path):
        config = Config.load(tmp_path / "nope.toml")
        assert config.modes["fix"].provider is None
        assert config.modes["fix"].model is None

    def test_default_output_defaults_to_replace(self, tmp_path: Path):
        config = Config.load(tmp_path / "nope.toml")
        assert config.modes["fix"].default_output == "replace"

    def test_overriding_builtin_preserves_other_fields(self, tmp_path: Path):
        """Overriding just the prompt should not reset preserve_structure."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("""\
[modes.fix]
prompt = "My custom fix prompt."
""")
        config = Config.load(cfg_file)
        assert config.modes["fix"].prompt == "My custom fix prompt."
        assert config.modes["fix"].preserve_structure is True  # default preserved


class TestCustomProviderFromToml:
    def test_unknown_keys_are_ignored(self, tmp_path: Path):
        """Extra/typo keys in a custom provider should not crash."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("""\
[providers.groq]
url = "https://api.groq.com/openai/v1"
model = "llama3-70b"
typo_field = "should be ignored"
""")
        config = Config.load(cfg_file)
        assert "groq" in config.providers
        assert config.providers["groq"].url == "https://api.groq.com/openai/v1"
        assert config.providers["groq"].model == "llama3-70b"

    def test_custom_provider_minimal(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("""\
[providers.local]
url = "http://localhost:1234/v1"
""")
        config = Config.load(cfg_file)
        assert "local" in config.providers
        assert config.providers["local"].url == "http://localhost:1234/v1"


class TestInitConfig:
    def test_creates_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        path = init_config()
        assert path.exists()
        assert "prosefmt" in path.read_text(encoding="utf-8").lower()

    def test_does_not_overwrite(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        path = init_config()
        path.read_text(encoding="utf-8")
        path.write_text("custom content", encoding="utf-8")
        init_config()
        assert path.read_text(encoding="utf-8") == "custom content"
