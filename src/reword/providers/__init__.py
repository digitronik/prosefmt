"""Provider registry — resolves a provider name to a concrete instance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from reword.providers.base import Provider, ProviderError

if TYPE_CHECKING:
    from reword.config import ProviderConfig


def get_provider(name: str, config: ProviderConfig) -> Provider:
    """Instantiate a provider by name using the given config."""
    if name == "ollama":
        from reword.providers.ollama import OllamaProvider

        return OllamaProvider(url=config.url, model=config.model)

    if name in ("openai", "openai-compat"):
        from reword.providers.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(url=config.url, model=config.model, api_key=config.api_key)

    if name == "anthropic":
        from reword.providers.anthropic import AnthropicProvider

        return AnthropicProvider(url=config.url, model=config.model, api_key=config.api_key)

    raise ProviderError(f"Unknown provider: {name}")
