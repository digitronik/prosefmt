"""Configuration management — reads TOML config + environment variables."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _config_dir() -> Path:
    """XDG-compliant config directory."""
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "reword"


def _config_path() -> Path:
    return _config_dir() / "config.toml"


DEFAULT_SYSTEM_PROMPT = (
    "You are a text editor. Follow the instruction and output ONLY the rewritten text "
    "— no preamble, no explanations, no 'Here is…'. Rules that always apply: "
    "(1) Keep all technical terms, commands, code, URLs, and acronyms exactly as written "
    "— never simplify or replace them. "
    "(2) Preserve all structure — bullet points, numbered lists, markdown, and code blocks "
    "must appear in the output exactly as they appear in the input."
)


@dataclass
class ProviderConfig:
    """Settings for a single AI provider."""

    name: str
    url: str = ""
    model: str = ""
    api_key: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModeConfig:
    """A rewrite mode (built-in or custom)."""

    name: str
    prompt: str
    label: str = ""
    preserve_structure: bool = True


@dataclass
class Config:
    """Top-level configuration."""

    default_provider: str = "ollama"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    modes: dict[str, ModeConfig] = field(default_factory=dict)
    undo_file: str = "/tmp/reword-undo"

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load config from TOML file, falling back to defaults."""
        config = cls()
        config._apply_defaults()

        filepath = path or _config_path()
        if filepath.exists():
            with open(filepath, "rb") as f:
                raw = tomllib.load(f)
            config._apply_toml(raw)

        config._apply_env()
        return config

    def _apply_defaults(self) -> None:
        """Set up default providers and modes."""
        from reword.modes import BUILTIN_MODES

        self.providers = {
            "ollama": ProviderConfig(
                name="ollama",
                url="http://localhost:11434",
                model="qwen2.5:1.5b",
            ),
            "openai": ProviderConfig(
                name="openai",
                url="https://api.openai.com/v1",
                model="gpt-4o-mini",
            ),
            "anthropic": ProviderConfig(
                name="anthropic",
                url="https://api.anthropic.com",
                model="claude-haiku-4-5-20251001",
            ),
            "openai-compat": ProviderConfig(
                name="openai-compat",
                url="http://localhost:8080/v1",
                model="local-model",
            ),
        }
        self.modes = {name: ModeConfig(**m) for name, m in BUILTIN_MODES.items()}

    def _apply_toml(self, raw: dict[str, Any]) -> None:
        """Overlay TOML values onto the config."""
        if "default_provider" in raw:
            self.default_provider = raw["default_provider"]
        if "system_prompt" in raw:
            self.system_prompt = raw["system_prompt"]

        for pname, pdata in raw.get("providers", {}).items():
            if pname in self.providers:
                pc = self.providers[pname]
                if "url" in pdata:
                    pc.url = pdata["url"]
                if "model" in pdata:
                    pc.model = pdata["model"]
                if "api_key" in pdata:
                    pc.api_key = pdata["api_key"]
            else:
                self.providers[pname] = ProviderConfig(name=pname, **pdata)

        for mname, mdata in raw.get("modes", {}).items():
            preserve = mdata.get("preserve_structure", mname not in ("summarize", "email"))
            self.modes[mname] = ModeConfig(
                name=mname,
                prompt=mdata.get("prompt", ""),
                label=mdata.get("label", mname.replace("-", " ").title()),
                preserve_structure=preserve,
            )

    def _apply_env(self) -> None:
        """Override API keys from environment variables (never store secrets in config)."""
        env_map = {
            "openai": ["REWORD_OPENAI_API_KEY", "OPENAI_API_KEY"],
            "anthropic": ["REWORD_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"],
            "openai-compat": ["REWORD_COMPAT_API_KEY"],
        }
        for pname, env_vars in env_map.items():
            if pname in self.providers:
                for var in env_vars:
                    val = os.environ.get(var, "")
                    if val:
                        self.providers[pname].api_key = val
                        break


def init_config() -> Path:
    """Create a default config file if it doesn't exist. Returns the path."""
    path = _config_path()
    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_DEFAULT_CONFIG_CONTENT)
    return path


_DEFAULT_CONFIG_CONTENT = """\
# Reword configuration — https://github.com/digitronik/reword
#
# Default provider (options: ollama, openai, anthropic, openai-compat)
default_provider = "ollama"

# System prompt applied to every mode (customise to fit your writing style)
# system_prompt = "You are a text editor. Output ONLY the rewritten text..."

# --- Providers ----------------------------------------------------------------

[providers.ollama]
url = "http://localhost:11434"
model = "qwen2.5:1.5b"

[providers.openai]
# API key: set REWORD_OPENAI_API_KEY or OPENAI_API_KEY env var
model = "gpt-4o-mini"

[providers.anthropic]
# API key: set REWORD_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY env var
model = "claude-haiku-4-5-20251001"

# [providers.openai-compat]
# url = "http://localhost:8080/v1"
# model = "local-model"

# --- Custom modes (add as many as you like) -----------------------------------

# [modes.translate-french]
# prompt = "Translate to French. Keep technical terms in English."
# label = "Translated to French"

# [modes.code-comments]
# prompt = "Add clear, concise comments to this code."
# label = "Comments added"
# preserve_structure = false
"""
