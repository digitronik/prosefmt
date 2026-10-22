"""Anthropic Claude provider — native Messages API."""

from __future__ import annotations

import httpx

from txtfmt.providers.base import ProviderError


class AnthropicProvider:
    """Anthropic Claude using the native ``/v1/messages`` endpoint."""

    def __init__(
        self,
        url: str = "https://api.anthropic.com",
        model: str = "claude-haiku-4-5-20251001",
        api_key: str = "",
    ) -> None:
        self.url = url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self._client = httpx.Client(timeout=120)

    @property
    def name(self) -> str:
        return "anthropic"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if not self.api_key:
            raise ProviderError(
                "Anthropic API key not set — export TXTFMT_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY"
            )

        try:
            resp = self._client.post(
                f"{self.url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 4096,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300]
            raise ProviderError(
                f"Anthropic returned HTTP {exc.response.status_code}: {body}"
            ) from exc
        except httpx.ConnectError as exc:
            raise ProviderError("Cannot connect to Anthropic API") from exc

        data = resp.json()
        try:
            return data["content"][0]["text"]
        except (KeyError, IndexError) as exc:
            error = data.get("error", {}).get("message", str(data))
            raise ProviderError(f"Unexpected Anthropic response: {error}") from exc

    def check_health(self) -> bool:
        return bool(self.api_key)
