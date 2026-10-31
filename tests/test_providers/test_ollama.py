"""Tests for the Ollama provider."""

from __future__ import annotations

import pytest

from prosefmt.providers.base import ProviderError
from prosefmt.providers.ollama import OllamaProvider


class TestOllamaProvider:
    def test_name(self):
        p = OllamaProvider()
        assert p.name == "ollama"

    def test_default_url(self):
        p = OllamaProvider()
        assert p.url == "http://localhost:11434"

    def test_custom_model(self):
        p = OllamaProvider(model="llama3.2:3b")
        assert p.model == "llama3.2:3b"

    def test_complete_success(self, httpx_mock):
        httpx_mock.add_response(
            url="http://localhost:11434/api/chat",
            json={"message": {"role": "assistant", "content": "Fixed grammar."}},
        )
        p = OllamaProvider()
        result = p.complete("system", "user prompt")
        assert result == "Fixed grammar."

    def test_complete_sends_low_temperature_and_seed(self, httpx_mock):
        httpx_mock.add_response(
            url="http://localhost:11434/api/chat",
            json={"message": {"role": "assistant", "content": "ok"}},
        )
        p = OllamaProvider(temperature=0.1, seed=42)
        p.complete("system", "user")

        request = httpx_mock.get_request()
        import json

        payload = json.loads(request.read())
        assert payload["options"]["temperature"] == 0.1
        assert payload["options"]["seed"] == 42

    def test_complete_omits_seed_when_none(self, httpx_mock):
        httpx_mock.add_response(
            url="http://localhost:11434/api/chat",
            json={"message": {"role": "assistant", "content": "ok"}},
        )
        p = OllamaProvider(seed=None)
        p.complete("system", "user")

        import json

        payload = json.loads(httpx_mock.get_request().read())
        assert "seed" not in payload["options"]

    def test_complete_empty_response(self, httpx_mock):
        httpx_mock.add_response(
            url="http://localhost:11434/api/chat",
            json={"message": {"role": "assistant", "content": ""}},
        )
        p = OllamaProvider()
        with pytest.raises(ProviderError, match="Empty response"):
            p.complete("system", "user prompt")

    def test_complete_error_response(self, httpx_mock):
        httpx_mock.add_response(
            url="http://localhost:11434/api/chat",
            json={"error": "model not found"},
        )
        p = OllamaProvider()
        with pytest.raises(ProviderError, match="model not found"):
            p.complete("system", "user prompt")

    def test_complete_http_error(self, httpx_mock):
        httpx_mock.add_response(
            url="http://localhost:11434/api/chat",
            status_code=500,
        )
        p = OllamaProvider()
        with pytest.raises(ProviderError, match="HTTP 500"):
            p.complete("system", "user prompt")

    def test_health_check_success(self, httpx_mock):
        httpx_mock.add_response(
            url="http://localhost:11434/api/tags",
            json={"models": []},
        )
        p = OllamaProvider()
        assert p.check_health() is True

    def test_health_check_failure(self, httpx_mock):
        httpx_mock.add_response(
            url="http://localhost:11434/api/tags",
            status_code=500,
        )
        p = OllamaProvider()
        assert p.check_health() is False

    def test_complete_timeout(self, httpx_mock):
        import httpx

        httpx_mock.add_exception(httpx.ReadTimeout("timed out"))
        p = OllamaProvider()
        with pytest.raises(ProviderError, match="timed out"):
            p.complete("system", "user prompt")
