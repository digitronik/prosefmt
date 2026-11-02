"""Provider registry — resolves a provider name to a concrete instance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prosefmt.providers.base import Provider, ProviderError

if TYPE_CHECKING:
    from prosefmt.config import Config, ProviderConfig


def get_provider(name: str, config: ProviderConfig, app_config: Config) -> Provider:
    """Instantiate a provider by name using the given config.

    Resolution order for the backend type:
      1. Explicit ``config.type`` field  (``type = "openai-compat"`` in TOML)
      2. The provider *name* itself       (``[providers.ollama]``)

    This lets users define ``[providers.groq]`` with ``type = "openai-compat"``
    and have it Just Work™.
    """
    provider_type = config.type or name
    temperature = app_config.effective_temperature(config)
    seed = app_config.effective_seed(config)

    if provider_type == "ollama":
        from prosefmt.providers.ollama import OllamaProvider

        return OllamaProvider(
            url=config.url, model=config.model, temperature=temperature, seed=seed
        )

    if provider_type in ("openai", "openai-compat"):
        from prosefmt.providers.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(
            url=config.url,
            model=config.model,
            api_key=config.api_key,
            temperature=temperature,
            seed=seed,
        )

    if provider_type == "anthropic":
        from prosefmt.providers.anthropic import AnthropicProvider

        return AnthropicProvider(
            url=config.url,
            model=config.model,
            api_key=config.api_key,
            temperature=temperature,
            seed=seed,
        )

    raise ProviderError(f"Unknown provider type '{provider_type}' for provider '{name}'")
