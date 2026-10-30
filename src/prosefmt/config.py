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
    "You are a text rewriter. Output ONLY the rewritten text. "
    "No preamble, no explanation, no 'Here is'. "
    "Keep technical terms, code, URLs, and formatting unchanged."
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
                known_fields = {"url", "model", "api_key"}
                filtered = {k: v for k, v in pdata.items() if k in known_fields}
                self.providers[pname] = ProviderConfig(name=pname, **filtered)

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


_DEFAULT_CONFIG_CONTENT = (
    "# prosefmt configuration\n"
    "# https://github.com/digitronik/prosefmt\n"
    "#\n"
    "# This file is the single source of truth for all modes and prompts.\n"
    "# Edit any prompt to fit your model, language, and writing style.\n"
    "# The picker menu updates automatically whenever you add or remove a mode.\n"
    "#\n"
    "# ── Prompt tips for small local models (1.5B-3B) ─────────────────────────────\n"
    "#   • Keep system_prompt SHORT (1-2 sentences). Long prompts confuse SLMs.\n"
    "#   • Use simple, direct instructions. Avoid double negations.\n"
    "#   • Use short sentences with one instruction each.\n"
    "#   • Translation to non-Latin scripts (Hindi, Chinese, Arabic, …) needs\n"
    '#     a larger model (≥7B). Use the per-mode "model" field to override.\n'
    "\n"
    "# ── General ───────────────────────────────────────────────────────────────────\n"
    "\n"
    '# Default mode — used when you run `prosefmt "text"` without --mode.\n'
    '# Change to any mode name defined below (e.g. "professional", "translate-czech").\n'
    'default_mode = "fix"\n'
    "\n"
    "# Default provider (options: ollama, openai, anthropic, openai-compat)\n"
    'default_provider = "ollama"\n'
    "\n"
    "# System prompt — prepended to every mode's instruction.\n"
    "# Keep it SHORT when using local models (qwen2.5, phi3, gemma).\n"
    'system_prompt = """You are a text rewriter. Output ONLY the rewritten text.\n'
    "No preamble, no explanation, no 'Here is'.\n"
    'Keep technical terms, code, URLs, and formatting unchanged."""\n'
    "\n"
    "# ── Providers ─────────────────────────────────────────────────────────────────\n"
    "\n"
    "[providers.ollama]\n"
    'url   = "http://localhost:11434"\n'
    'model = "qwen2.5:1.5b"          # change to any model you have pulled\n'
    "\n"
    "[providers.openai]\n"
    'model = "gpt-4o-mini"\n'
    "# API key: set PROSEFMT_OPENAI_API_KEY or OPENAI_API_KEY env var\n"
    "\n"
    "[providers.anthropic]\n"
    'model = "claude-haiku-4-5-20251001"\n'
    "# API key: set PROSEFMT_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY env var\n"
    "\n"
    "# Any OpenAI-compatible endpoint (Groq, Together AI, LM Studio, vLLM, etc.)\n"
    "# [providers.openai-compat]\n"
    '# url   = "https://api.groq.com/openai/v1"\n'
    '# model = "llama-3.3-70b-versatile"\n'
    "# API key: set PROSEFMT_COMPAT_API_KEY env var\n"
    "\n"
    "# ── Modes ─────────────────────────────────────────────────────────────────────\n"
    "#\n"
    "# Fields:\n"
    "#   prompt             (required) Instruction sent to the AI\n"
    "#   label              (optional) Name shown in notifications. Default: mode name\n"
    "#   preserve_structure (optional) Keep bullet/number list prefixes. Default: true\n"
    '#   default_output     (optional) "replace" | "popup" | "clipboard". '
    'Default: "replace"\n'
    "#   provider           (optional) Override the provider for this mode only\n"
    "#   model              (optional) Override the model for this mode only\n"
    "\n"
    "# ── Text Rewriting ────────────────────────────────────────────────────────────\n"
    "\n"
    "[modes.fix]\n"
    'prompt = "Fix all grammar, spelling, and punctuation errors. '
    'Keep the same meaning. Keep the same number of sentences."\n'
    'label  = "Grammar fixed"\n'
    "\n"
    "[modes.professional]\n"
    'prompt = "Rewrite this text in a professional, formal tone. '
    'Suitable for work emails and business messages."\n'
    'label  = "Made professional"\n'
    "\n"
    "[modes.casual]\n"
    'prompt = "Rewrite this text in a casual, friendly tone. '
    'Keep it natural and conversational."\n'
    'label  = "Made casual"\n'
    "\n"
    "[modes.rephrase]\n"
    'prompt = "Rephrase this text for better clarity. Keep the same meaning. '
    'Use different words."\n'
    'label  = "Rephrased"\n'
    "\n"
    "[modes.concise]\n"
    'prompt = "Make this text shorter. Remove unnecessary words. Keep the same meaning."\n'
    'label  = "Made concise"\n'
    "\n"
    "[modes.expand]\n"
    'prompt = "Expand this text with more detail and explanation. '
    'Keep the same meaning and tone."\n'
    'label  = "Expanded"\n'
    "\n"
    "[modes.email]\n"
    'prompt             = "Rewrite this as a professional email. '
    'Add a greeting at the start and a sign-off at the end."\n'
    'label              = "Formatted as email"\n'
    "preserve_structure = false\n"
    "\n"
    "[modes.summarize]\n"
    'prompt             = "Write a short summary of this text. Include only the key points. '
    'Use 2-3 sentences maximum."\n'
    'label              = "Summarized"\n'
    "preserve_structure = false\n"
    'default_output     = "popup"\n'
    "\n"
    "# ── Translation ───────────────────────────────────────────────────────────────\n"
    "# Remove the '#' characters to enable a language. Add more as you need them.\n"
    "#\n"
    "# IMPORTANT: Translation (especially to non-Latin scripts like Hindi, Chinese,\n"
    "# Arabic) needs a larger model. Small models (1.5B-3B) will produce garbage.\n"
    '# Use "model" to override per mode — e.g. model = "qwen2.5:7b"\n'
    '# Or route to a cloud provider — e.g. provider = "openai"\n'
    "#\n"
    "# Workflow tip — translate an incoming message without replacing it:\n"
    '#   set default_output = "popup" so the translation appears in a popup\n'
    "#   and the original text is left untouched.\n"
    "\n"
    "# [modes.translate-english]\n"
    '# prompt         = "Translate the following text to English. Output only the translation."\n'
    '# label          = "Translated to English"\n'
    '# default_output = "popup"\n'
    '# model          = "qwen2.5:7b"   # translation needs a larger model\n'
    "\n"
    "# [modes.translate-czech]\n"
    '# prompt = "Translate the following text to Czech. Keep technical terms in English. '
    'Output only the translation."\n'
    '# label  = "Přeloženo do češtiny"\n'
    '# model  = "qwen2.5:7b"\n'
    "\n"
    "# [modes.translate-hindi]\n"
    '# prompt = "Translate the following text to Hindi (Devanagari script). '
    'Keep technical terms in English. Output only the Hindi translation."\n'
    '# label  = "हिंदी में अनुवादित"\n'
    '# model  = "qwen2.5:7b"   # Hindi needs ≥7B model for coherent output\n'
    "\n"
    "# [modes.translate-french]\n"
    '# prompt = "Translate the following text to French. Keep technical terms in English. '
    'Output only the translation."\n'
    '# label  = "Traduit en français"\n'
    '# model  = "qwen2.5:7b"\n'
    "\n"
    "# [modes.translate-spanish]\n"
    '# prompt = "Translate the following text to Spanish. Keep technical terms in English. '
    'Output only the translation."\n'
    '# label  = "Traducido al español"\n'
    '# model  = "qwen2.5:7b"\n'
    "\n"
    "# ── Analysis ──────────────────────────────────────────────────────────────────\n"
    "# These modes show a popup by default (don't replace the original text).\n"
    "\n"
    "# [modes.explain]\n"
    '# prompt         = "Explain this text in simple terms. Be brief. Use 2-3 sentences."\n'
    '# label          = "Explained"\n'
    '# default_output = "popup"\n'
    "\n"
    "# [modes.review]\n"
    '# prompt         = "Review this text. List issues with grammar, clarity, or tone. '
    'Be specific."\n'
    '# label          = "Reviewed"\n'
    '# default_output = "popup"\n'
    '# provider       = "openai"   # heavier task — uncomment to use a cloud model\n'
    "\n"
    "# ── Code ──────────────────────────────────────────────────────────────────────\n"
    "\n"
    "# [modes.add-comments]\n"
    '# prompt             = "Add clear, concise comments to this code. '
    'Do not change any code."\n'
    '# label              = "Comments added"\n'
    "# preserve_structure = false\n"
    "\n"
    "# [modes.commit-message]\n"
    '# prompt         = "Write a concise git commit message for this diff. '
    'Use conventional commits format."\n'
    '# label          = "Commit message"\n'
    '# default_output = "popup"\n'
)
