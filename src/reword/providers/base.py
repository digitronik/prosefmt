"""Abstract base for AI providers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class ProviderError(Exception):
    """Raised when a provider request fails."""


@runtime_checkable
class Provider(Protocol):
    """Any object that can complete a system + user prompt pair."""

    @property
    def name(self) -> str: ...

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send the prompts and return the model's response text."""
        ...

    def check_health(self) -> bool:
        """Return True if the provider is reachable and ready."""
        ...
