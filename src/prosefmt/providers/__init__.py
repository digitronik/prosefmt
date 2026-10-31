"""Provider registry — resolves a provider name to a concrete instance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prosefmt.providers.base import Provider, ProviderError

if TYPE_CHECKING:
    from prosefmt.config import Config, ProviderConfig


def get_provider(name: str, config: ProviderConfig, app_config: Config) -> Provider:
    """Instantiate a provider by name using the given config."""
    temperature = app_config.effective_temperature(config)
    seed = app_config.effective_seed(config)

    if name == "ollama":
        from prosefmt.providers.ollama import OllamaProvider

        return OllamaProvider(
            url=config.url, model=config.model, temperature=temperature, seed=seed
        )

    if name in ("openai", "openai-compat"):
        from prosefmt.providers.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(
            url=config.url,
            model=config.model,
            api_key=config.api_key,
            temperature=temperature,
            seed=seed,
        )

    if name == "anthropic":
        from prosefmt.providers.anthropic import AnthropicProvider

        return AnthropicProvider(
            url=config.url,
            model=config.model,
            api_key=config.api_key,
            temperature=temperature,
            seed=seed,
        )

    raise ProviderError(f"Unknown provider: {name}")
