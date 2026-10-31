"""Configuration management — reads TOML config + environment variables."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prosefmt.platform import PlatformInfo
from prosefmt.platform import detect as _detect_platform


def _config_dir() -> Path:
    """Platform-appropriate config directory.

    Linux / macOS: ``$XDG_CONFIG_HOME/prosefmt`` (default ``~/.config/prosefmt``)
    Windows:       ``%LOCALAPPDATA%\\prosefmt`` (matches the undo-file location)
    """
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "prosefmt"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "prosefmt"


def _config_path() -> Path:
    return _config_dir() / "config.toml"


def _default_undo_file() -> str:
    """Private undo file under XDG_STATE_HOME (not world-readable /tmp)."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return str(base / "prosefmt" / "undo")


# Fallback — used only when default_config.toml cannot be read.
# The real system prompt lives in default_config.toml (single source of truth).
_FALLBACK_SYSTEM_PROMPT = (
    "You are a text rewriter. Output ONLY the rewritten text. "
    "No preamble, no explanation, no 'Here is'. "
    "Keep technical terms, code, URLs, and formatting unchanged."
)


@dataclass
class ProviderConfig:
    """Settings for a single AI provider."""

    name: str
    type: str = ""  # "ollama" | "openai-compat" | "anthropic" — inferred from name if empty
    url: str = ""
    model: str = ""
    api_key: str = ""
    api_key_env: str = ""  # custom env var name for the API key (e.g. "GROQ_API_KEY")
    temperature: float | None = None
    seed: int | None = None


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
    temperature: float | None = None  # override global/provider temperature
    default_output: str = "replace"  # "replace" | "popup" | "clipboard"


@dataclass
class Config:
    """Top-level configuration."""

    default_mode: str = "fix"
    default_provider: str = "ollama"
    temperature: float = 0.1
    seed: int | None = 42
    system_prompt: str = _FALLBACK_SYSTEM_PROMPT
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    modes: dict[str, ModeConfig] = field(default_factory=dict)
    undo_file: str = field(default_factory=_default_undo_file)
    platform: PlatformInfo = field(default_factory=_detect_platform)

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
        """Set up default providers and modes from the shipped config template.

        ``default_config.toml`` is the single source of truth for all
        built-in prompts, labels, and provider settings.  Python code
        never hardcodes prompt text — users own every instruction.
        """
        try:
            raw = _parse_default_config()
        except Exception:
            # Template unreadable (broken install) — minimal fallback
            self.providers["ollama"] = ProviderConfig(
                name="ollama", url="http://localhost:11434", model="qwen2.5:1.5b"
            )
            self.modes["fix"] = ModeConfig(
                name="fix", prompt="Fix grammar and spelling.", label="Grammar fixed"
            )
            return

        # Top-level settings from template
        if "default_mode" in raw:
            self.default_mode = raw["default_mode"]
        if "default_provider" in raw:
            self.default_provider = raw["default_provider"]
        if "temperature" in raw:
            self.temperature = float(raw["temperature"])
        if "seed" in raw:
            val = raw["seed"]
            self.seed = None if val is None else int(val)
        if "system_prompt" in raw:
            self.system_prompt = raw["system_prompt"]

        # Providers
        for pname, pdata in raw.get("providers", {}).items():
            self.providers[pname] = ProviderConfig(
                name=pname,
                url=pdata.get("url", ""),
                model=pdata.get("model", ""),
            )

        # Modes
        for mname, mdata in raw.get("modes", {}).items():
            raw_temp = mdata.get("temperature")
            self.modes[mname] = ModeConfig(
                name=mname,
                prompt=mdata.get("prompt", ""),
                label=mdata.get("label", mname),
                preserve_structure=mdata.get("preserve_structure", True),
                temperature=float(raw_temp) if raw_temp is not None else None,
                default_output=mdata.get("default_output", "replace"),
            )

    def _apply_toml(self, raw: dict[str, Any]) -> None:
        """Overlay TOML values onto the config."""
        if "platform" in raw:
            self.platform = PlatformInfo.from_dict(raw["platform"])

        if "default_mode" in raw:
            self.default_mode = raw["default_mode"]
        if "default_provider" in raw:
            self.default_provider = raw["default_provider"]
        if "temperature" in raw:
            self.temperature = float(raw["temperature"])
        if "seed" in raw:
            val = raw["seed"]
            self.seed = None if val is None else int(val)
        if "system_prompt" in raw:
            self.system_prompt = raw["system_prompt"]

        for pname, pdata in raw.get("providers", {}).items():
            if pname in self.providers:
                pc = self.providers[pname]
                if "type" in pdata:
                    pc.type = pdata["type"]
                if "url" in pdata:
                    pc.url = pdata["url"]
                if "model" in pdata:
                    pc.model = pdata["model"]
                if "api_key" in pdata:
                    pc.api_key = pdata["api_key"]
                if "api_key_env" in pdata:
                    pc.api_key_env = pdata["api_key_env"]
                if "temperature" in pdata:
                    pc.temperature = float(pdata["temperature"])
                if "seed" in pdata:
                    val = pdata["seed"]
                    pc.seed = None if val is None else int(val)
            else:
                known_fields = {
                    "type",
                    "url",
                    "model",
                    "api_key",
                    "api_key_env",
                    "temperature",
                    "seed",
                }
                filtered = {k: v for k, v in pdata.items() if k in known_fields}
                if "temperature" in filtered:
                    filtered["temperature"] = float(filtered["temperature"])
                if "seed" in filtered and filtered["seed"] is not None:
                    filtered["seed"] = int(filtered["seed"])
                self.providers[pname] = ProviderConfig(name=pname, **filtered)

        for mname, mdata in raw.get("modes", {}).items():
            existing = self.modes.get(mname)
            # Inherit defaults from the builtin mode if it exists, otherwise
            # use ModeConfig dataclass defaults.  No hardcoded mode names.
            default_preserve = existing.preserve_structure if existing else True
            default_output = existing.default_output if existing else "replace"
            default_label = existing.label if existing else mname.replace("-", " ").title()
            raw_temp = mdata.get("temperature")
            mode_temp = (
                float(raw_temp)
                if raw_temp is not None
                else (existing.temperature if existing else None)
            )
            self.modes[mname] = ModeConfig(
                name=mname,
                prompt=mdata.get("prompt", existing.prompt if existing else ""),
                label=mdata.get("label", default_label),
                preserve_structure=mdata.get("preserve_structure", default_preserve),
                provider=mdata.get("provider") or None,
                model=mdata.get("model") or None,
                temperature=mode_temp,
                default_output=mdata.get("default_output", default_output),
            )

    def _apply_env(self) -> None:
        """Override API keys from environment variables (never store secrets in config)."""
        env_map: dict[str, list[str]] = {
            "openai": ["PROSEFMT_OPENAI_API_KEY", "OPENAI_API_KEY"],
            "anthropic": ["PROSEFMT_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"],
            "openai-compat": ["PROSEFMT_COMPAT_API_KEY"],
        }
        for provider in self.providers.values():
            # Build candidate env vars: custom api_key_env first, then defaults.
            candidates: list[str] = []
            if provider.api_key_env:
                candidates.append(provider.api_key_env)
            candidates.extend(env_map.get(provider.name, []))
            for var in candidates:
                val = os.environ.get(var, "")
                if val:
                    provider.api_key = val
                    break

    def effective_temperature(self, provider: ProviderConfig) -> float:
        if provider.temperature is not None:
            return provider.temperature
        return self.temperature

    def effective_seed(self, provider: ProviderConfig) -> int | None:
        if provider.seed is not None:
            return provider.seed
        return self.seed


def init_config(*, overwrite: bool = False) -> tuple[Path, bool]:
    """Create a default config file.

    Returns ``(path, created)`` where *created* is ``True`` when a new file
    was written and ``False`` when an existing file was left untouched.
    """
    path = _config_path()
    if path.exists() and not overwrite:
        return path, False

    platform_info = _detect_platform()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_default_config_content(platform_info), encoding="utf-8")
    return path, True


def _default_config_content(platform_info: PlatformInfo) -> str:
    """Generate config file content with auto-detected platform values."""
    platform_section = (
        "# ── Platform (auto-detected) ──────────────────────────────────────────────────\n"
        "# Detected on first run. Override if detection is wrong.\n"
        "\n"
        "[platform]\n"
        f'os          = "{platform_info.os}"\n'
        f'display     = "{platform_info.display}"\n'
        f'distro      = "{platform_info.distro}"\n'
        f'pkg_manager = "{platform_info.pkg_manager}"'
    )
    template = _read_default_config_template()
    return template.replace("{{PLATFORM}}", platform_section)


def _parse_default_config() -> dict[str, Any]:
    """Parse the shipped config template for runtime defaults.

    The template contains a ``{{PLATFORM}}`` placeholder that is replaced
    with an empty ``[platform]`` section before parsing.
    """
    template = _read_default_config_template()
    content = template.replace(
        "{{PLATFORM}}",
        '[platform]\nos = ""\ndisplay = ""\ndistro = ""\npkg_manager = ""',
    )
    return tomllib.loads(content)


def _read_default_config_template() -> str:
    """Read the default config template shipped alongside this module."""
    return (Path(__file__).parent / "default_config.toml").read_text(encoding="utf-8")
