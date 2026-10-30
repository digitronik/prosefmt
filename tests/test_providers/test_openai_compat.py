"""Tests for the OpenAI-compatible provider."""

from __future__ import annotations

import pytest

from prosefmt.providers.base import ProviderError
from prosefmt.providers.openai_compat import OpenAICompatProvider


class TestOpenAICompatProvider:
    def test_name(self):
        p = OpenAICompatProvider()
        assert p.name == "openai-compat"

    def test_complete_success(self, httpx_mock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            json={
                "choices": [{"message": {"content": "Polished text."}}],
            },
        )
        p = OpenAICompatProvider(api_key="sk-test")
        result = p.complete("system", "user")
        assert result == "Polished text."

    def test_sends_auth_header(self, httpx_mock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            json={"choices": [{"message": {"content": "ok"}}]},
        )
        p = OpenAICompatProvider(api_key="sk-test-key")
        p.complete("s", "u")

        request = httpx_mock.get_request()
        assert request.headers["authorization"] == "Bearer sk-test-key"

    def test_no_auth_header_without_key(self, httpx_mock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            json={"choices": [{"message": {"content": "ok"}}]},
        )
        p = OpenAICompatProvider(api_key="")
        p.complete("s", "u")

        request = httpx_mock.get_request()
        assert "authorization" not in request.headers

    def test_http_error(self, httpx_mock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            status_code=401,
            text="Unauthorized",
        )
        p = OpenAICompatProvider(api_key="bad-key")
        with pytest.raises(ProviderError, match="HTTP 401"):
            p.complete("s", "u")

    def test_malformed_response(self, httpx_mock):
        httpx_mock.add_response(
            url="https://api.openai.com/v1/chat/completions",
            json={"error": {"message": "Something broke"}},
        )
        p = OpenAICompatProvider(api_key="sk-test")
        with pytest.raises(ProviderError, match="Something broke"):
            p.complete("s", "u")

    def test_custom_url(self, httpx_mock):
        httpx_mock.add_response(
            url="http://localhost:8080/v1/chat/completions",
            json={"choices": [{"message": {"content": "local"}}]},
        )
        p = OpenAICompatProvider(url="http://localhost:8080/v1", model="local-model")
        result = p.complete("s", "u")
        assert result == "local"

    def test_complete_timeout(self, httpx_mock):
        import httpx

        httpx_mock.add_exception(httpx.ReadTimeout("timed out"))
        p = OpenAICompatProvider(api_key="sk-test")
        with pytest.raises(ProviderError, match="timed out"):
            p.complete("s", "u")
