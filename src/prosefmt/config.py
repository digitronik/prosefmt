"""Configuration management — reads TOML config + environment variables."""

from __future__ import annotations

import os
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _config_dir() -> Path:
    """XDG-compliant config directory."""
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "prosefmt"


def _config_path() -> Path:
    return _config_dir() / "config.toml"


def _default_undo_file() -> str:
    """Cross-platform temp path for the last-rewrite undo snapshot."""
    return str(Path(tempfile.gettempdir()) / "prosefmt-undo")


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
    # Per-mode overrides — leave None to use the global defaults
    provider: str | None = None  # override config.default_provider
    model: str | None = None  # override provider's default model
    default_output: str = "replace"  # "replace" | "popup" | "clipboard"


@dataclass
class Config:
    """Top-level configuration."""

    default_mode: str = "fix"
    default_provider: str = "ollama"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    modes: dict[str, ModeConfig] = field(default_factory=dict)
    undo_file: str = field(default_factory=_default_undo_file)

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
        from prosefmt.modes import BUILTIN_MODES

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
        if "default_mode" in raw:
            self.default_mode = raw["default_mode"]
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
            # preserve_structure default: False for summarize/email, True otherwise
            existing = self.modes.get(mname)
            _no_preserve = ("summarize", "email")
            if existing:
                default_preserve = existing.preserve_structure
            else:
                default_preserve = mname not in _no_preserve
            default_label = existing.label if existing else mname.replace("-", " ").title()
            self.modes[mname] = ModeConfig(
                name=mname,
                prompt=mdata.get("prompt", existing.prompt if existing else ""),
                label=mdata.get("label", default_label),
                preserve_structure=mdata.get("preserve_structure", default_preserve),
                provider=mdata.get("provider") or None,
                model=mdata.get("model") or None,
                default_output=mdata.get("default_output", "replace"),
            )

    def _apply_env(self) -> None:
        """Override API keys from environment variables (never store secrets in config)."""
        env_map = {
            "openai": ["PROSEFMT_OPENAI_API_KEY", "OPENAI_API_KEY"],
            "anthropic": ["PROSEFMT_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"],
            "openai-compat": ["PROSEFMT_COMPAT_API_KEY"],
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
    path.write_text(_DEFAULT_CONFIG_CONTENT, encoding="utf-8")
    return path


_DEFAULT_CONFIG_CONTENT = '''\
# prosefmt configuration
# https://github.com/digitronik/prosefmt
#
# This file is the single source of truth for all modes and prompts.
# Edit any prompt to fit your model, language, and writing style.
# The picker menu updates automatically whenever you add or remove a mode.

# ── General ───────────────────────────────────────────────────────────────────

# Default mode — used when you run `prosefmt "text"` without --mode.
# Change to any mode name defined below (e.g. "professional", "translate-czech").
default_mode = "fix"

# Default provider (options: ollama, openai, anthropic, openai-compat)
default_provider = "ollama"

# System prompt — prepended to every mode's instruction.
# Keep it SHORT when using local models (qwen2.5, phi3, gemma).
system_prompt = """You are a text editor. Output ONLY the rewritten text.
No preamble, no explanations, no 'Here is…'.
Keep technical terms, code, URLs, and markdown structure exactly as written."""

# ── Providers ─────────────────────────────────────────────────────────────────

[providers.ollama]
url   = "http://localhost:11434"
model = "qwen2.5:1.5b"          # change to any model you have pulled

[providers.openai]
model = "gpt-4o-mini"
# API key: set PROSEFMT_OPENAI_API_KEY or OPENAI_API_KEY env var

[providers.anthropic]
model = "claude-haiku-4-5-20251001"
# API key: set PROSEFMT_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY env var

# Any OpenAI-compatible endpoint (Groq, Together AI, LM Studio, vLLM, etc.)
# [providers.openai-compat]
# url   = "https://api.groq.com/openai/v1"
# model = "llama-3.3-70b-versatile"
# API key: set PROSEFMT_COMPAT_API_KEY env var

# ── Modes ─────────────────────────────────────────────────────────────────────
#
# Fields:
#   prompt             (required) Instruction sent to the AI
#   label              (optional) Name shown in notifications. Default: mode name
#   preserve_structure (optional) Keep bullet/number list prefixes. Default: true
#   default_output     (optional) "replace" | "popup" | "clipboard". Default: "replace"
#   provider           (optional) Override the provider for this mode only
#   model              (optional) Override the model for this mode only

# ── Text Rewriting ────────────────────────────────────────────────────────────

[modes.fix]
prompt = "Fix grammar, spelling, and punctuation only. Do not change meaning or add sentences."
label  = "Grammar fixed"

[modes.professional]
prompt = "Rewrite in a professional tone suitable for workplace emails and Slack."
label  = "Made professional"

[modes.casual]
prompt = "Rewrite in a casual, friendly, conversational tone."
label  = "Made casual"

[modes.rephrase]
prompt = "Rephrase for better clarity and flow without changing the meaning."
label  = "Rephrased"

[modes.concise]
prompt = "Make the text more concise — same meaning, fewer words."
label  = "Made concise"

[modes.expand]
prompt = "Expand the text with more detail and explanation, keeping the same meaning."
label  = "Expanded"

[modes.email]
prompt             = "Rewrite as a professional email with an appropriate greeting and sign-off."
label              = "Formatted as email"
preserve_structure = false

[modes.summarize]
prompt             = "Summarize concisely, keeping the key points."
label              = "Summarized"
preserve_structure = false
default_output     = "popup"

# ── Translation ───────────────────────────────────────────────────────────────
# Remove the \'#\' characters to enable a language. Add more as you need them.
#
# Workflow tip — translate an incoming message without replacing it:
#   set default_output = "popup" so the translation appears in a popup
#   and the original text is left untouched.

# [modes.translate-english]
# prompt         = "Translate to English. Keep technical terms, code, and URLs as-is."
# label          = "Translated to English"
# default_output = "popup"

# [modes.translate-czech]
# prompt = "Translate to Czech. Keep technical terms, code, and URLs in English."
# label  = "Přeloženo do češtiny"

# [modes.translate-hindi]
# prompt = "Translate to Hindi. Keep technical terms, code, and URLs in English."
# label  = "हिंदी में अनुवादित"

# [modes.translate-french]
# prompt = "Translate to French. Keep technical terms, code, and URLs in English."
# label  = "Traduit en français"

# [modes.translate-spanish]
# prompt = "Translate to Spanish. Keep technical terms, code, and URLs in English."
# label  = "Traducido al español"

# ── Analysis ──────────────────────────────────────────────────────────────────
# These modes show a popup by default (don't replace the original text).

# [modes.explain]
# prompt         = "Explain this in simple terms. Be brief."
# label          = "Explained"
# default_output = "popup"

# [modes.review]
# prompt         = "Review this text. List any issues with grammar, clarity, or tone."
# label          = "Reviewed"
# default_output = "popup"
# provider       = "openai"   # heavier task — uncomment to use a cloud model

# ── Code ──────────────────────────────────────────────────────────────────────

# [modes.add-comments]
# prompt             = "Add clear, concise comments to this code. Do not change the code."
# label              = "Comments added"
# preserve_structure = false

# [modes.commit-message]
# prompt         = "Write a concise git commit message for this diff. Use conventional commits."
# label          = "Commit message"
# default_output = "popup"
'''
