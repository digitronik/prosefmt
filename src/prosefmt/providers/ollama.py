"""Ollama provider — talks to a local Ollama server."""

from __future__ import annotations

import httpx

from prosefmt.providers.base import ProviderError


class OllamaProvider:
    """Local Ollama LLM provider (no API key needed)."""

    def __init__(self, url: str = "http://localhost:11434", model: str = "qwen2.5:1.5b") -> None:
        self.url = url.rstrip("/")
        self.model = model
        self._client = httpx.Client(timeout=120)

    @property
    def name(self) -> str:
        return "ollama"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        try:
            resp = self._client.post(
                f"{self.url}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"Ollama returned HTTP {exc.response.status_code}") from exc
        except httpx.ConnectError as exc:
            raise ProviderError("Cannot connect to Ollama — is it running? (ollama serve)") from exc

        data = resp.json()
        content = data.get("message", {}).get("content", "")
        if not content:
            error = data.get("error", "Empty response from model")
            raise ProviderError(f"Ollama error: {error}")
        return content

    def check_health(self) -> bool:
        try:
            resp = self._client.get(f"{self.url}/api/tags", timeout=3)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
