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

    def test_defaults_come_from_toml_template(self):
        """Verify the single-catalogue design: all defaults are loaded from
        default_config.toml, not hardcoded in Python."""
        from prosefmt.config import _parse_default_config

        raw = _parse_default_config()
        config = Config.load()

        # Mode prompts must match the template exactly
        for mname, mdata in raw.get("modes", {}).items():
            assert mname in config.modes, f"template mode '{mname}' missing from defaults"
            assert config.modes[mname].prompt == mdata["prompt"]

        # Provider URLs must match the template
        for pname, pdata in raw.get("providers", {}).items():
            assert pname in config.providers
            if "url" in pdata:
                assert config.providers[pname].url == pdata["url"]

    def test_default_mode_prompts_are_non_empty(self):
        """Every default mode must have a real prompt (not empty)."""
        config = Config.load()
        for name, mode in config.modes.items():
            assert mode.prompt, f"mode '{name}' has an empty prompt"

    def test_summarize_default_output_is_popup(self):
        """Summarize mode should default to popup output."""
        config = Config.load()
        assert config.modes["summarize"].default_output == "popup"

    def test_fix_preserves_structure(self):
        config = Config.load()
        assert config.modes["fix"].preserve_structure is True

    def test_summarize_does_not_preserve_structure(self):
        config = Config.load()
        assert config.modes["summarize"].preserve_structure is False

    def test_email_does_not_preserve_structure(self):
        config = Config.load()
        assert config.modes["email"].preserve_structure is False

    def test_builtin_mode_temperature_defaults(self):
        config = Config.load()
        assert config.modes["fix"].temperature is None
        assert config.modes["summarize"].temperature == 0.4
        assert config.modes["rephrase"].temperature == 0.4
        assert config.modes["expand"].temperature == 0.4


class TestDefaultsFallback:
    def test_fallback_when_template_unreadable(self, monkeypatch):
        """If default_config.toml is missing/corrupt, minimal fallback kicks in."""
        import prosefmt.config as cfg_mod

        monkeypatch.setattr(cfg_mod, "_parse_default_config", _raise_oserror)
        config = Config()
        config._apply_defaults()

        assert "ollama" in config.providers
        assert "fix" in config.modes
        assert config.modes["fix"].prompt == "Fix grammar and spelling."


def _raise_oserror():
    raise OSError("missing template")


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

    def test_custom_api_key_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """api_key_env lets custom providers load keys from any env var."""
        toml_text = """\
[providers.groq]
type = "openai-compat"
url = "https://api.groq.com/openai/v1"
model = "llama-3.3-70b"
api_key_env = "GROQ_API_KEY"
"""
        (tmp_path / "config.toml").write_text(toml_text)
        monkeypatch.setenv("GROQ_API_KEY", "gsk-test-456")
        config = Config.load(tmp_path / "config.toml")
        assert config.providers["groq"].api_key == "gsk-test-456"

    def test_api_key_env_takes_priority_over_hardcoded_map(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """When api_key_env is set, it should be tried before the default env vars."""
        toml_text = """\
[providers.openai]
api_key_env = "MY_OPENAI_KEY"
"""
        (tmp_path / "config.toml").write_text(toml_text)
        monkeypatch.setenv("OPENAI_API_KEY", "default")
        monkeypatch.setenv("MY_OPENAI_KEY", "custom")
        config = Config.load(tmp_path / "config.toml")
        assert config.providers["openai"].api_key == "custom"


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

    def test_custom_provider_with_type(self, tmp_path: Path):
        """A custom provider name with an explicit type should dispatch correctly."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("""\
[providers.groq]
type = "openai-compat"
url = "https://api.groq.com/openai/v1"
model = "llama-3.3-70b-versatile"
""")
        config = Config.load(cfg_file)
        assert config.providers["groq"].type == "openai-compat"

    def test_builtin_provider_type_update(self, tmp_path: Path):
        """Adding type to a built-in provider should be stored."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("""\
[providers.ollama]
model = "llama3.2:3b"
""")
        config = Config.load(cfg_file)
        assert config.providers["ollama"].type == ""  # not set, inferred from name


class TestDefaultOutputOverlay:
    """Verify that default_output is properly inherited from builtins."""

    def test_summarize_inherits_popup(self, tmp_path: Path):
        """Overriding only the prompt should NOT reset default_output."""
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("""\
[modes.summarize]
prompt = "My custom summary prompt."
""")
        config = Config.load(cfg_file)
        assert config.modes["summarize"].default_output == "popup"
        assert config.modes["summarize"].prompt == "My custom summary prompt."

    def test_new_mode_defaults_to_replace(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("""\
[modes.custom]
prompt = "Do something."
""")
        config = Config.load(cfg_file)
        assert config.modes["custom"].default_output == "replace"


class TestPlatformConfig:
    def test_platform_from_toml(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("""\
[platform]
os = "macos"
display = "quartz"
distro = "macos"
pkg_manager = "brew"
""")
        config = Config.load(cfg_file)
        assert config.platform.os == "macos"
        assert config.platform.pkg_manager == "brew"

    def test_platform_autodetected_when_missing(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text('default_mode = "fix"\n')
        config = Config.load(cfg_file)
        # Should auto-detect — just verify it's populated
        assert config.platform.os in ("linux", "macos", "windows", "unknown")

    def test_platform_partial_override(self, tmp_path: Path):
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text("""\
[platform]
os = "linux"
pkg_manager = "dnf"
""")
        config = Config.load(cfg_file)
        assert config.platform.os == "linux"
        assert config.platform.pkg_manager == "dnf"
        # display and distro filled by auto-detection
        assert config.platform.display != ""


class TestInitConfig:
    def test_creates_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        path, created = init_config()
        assert created
        assert path.exists()
        assert "prosefmt" in path.read_text(encoding="utf-8").lower()

    def test_does_not_overwrite(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        path, _ = init_config()
        path.write_text("custom content", encoding="utf-8")
        path2, created = init_config()
        assert not created
        assert path2 == path
        assert path.read_text(encoding="utf-8") == "custom content"

    def test_overwrite_restores_defaults(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        path, _ = init_config()
        path.write_text("custom content", encoding="utf-8")
        path2, created = init_config(overwrite=True)
        assert created
        assert path2 == path
        assert "prosefmt" in path.read_text(encoding="utf-8").lower()

    def test_config_includes_platform_section(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        path, _ = init_config()
        content = path.read_text(encoding="utf-8")
        assert "[platform]" in content
        assert "pkg_manager" in content
