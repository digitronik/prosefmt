"""OpenAI-compatible provider — works with OpenAI, Groq, Together, LM Studio, vLLM, etc."""

from __future__ import annotations

import httpx

from prosefmt.providers.base import ProviderError


class OpenAICompatProvider:
    """Any service that speaks the OpenAI ``/v1/chat/completions`` protocol."""

    def __init__(
        self,
        url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        api_key: str = "",
    ) -> None:
        self.url = url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self._client = httpx.Client(timeout=120)

    @property
    def name(self) -> str:
        return "openai-compat"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            resp = self._client.post(
                f"{self.url}/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300]
            raise ProviderError(
                f"OpenAI-compatible API returned HTTP {exc.response.status_code}: {body}"
            ) from exc
        except httpx.ConnectError as exc:
            raise ProviderError(f"Cannot connect to {self.url}") from exc

        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            error = data.get("error", {}).get("message", str(data))
            raise ProviderError(f"Unexpected API response: {error}") from exc

    def check_health(self) -> bool:
        try:
            resp = self._client.get(f"{self.url}/models", timeout=5)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False
