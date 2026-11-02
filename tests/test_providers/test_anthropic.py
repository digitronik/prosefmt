"""Tests for the Anthropic provider."""

from __future__ import annotations

import pytest

from prosefmt.providers.anthropic import AnthropicProvider
from prosefmt.providers.base import ProviderError


class TestAnthropicProvider:
    def test_name(self):
        p = AnthropicProvider(api_key="test")
        assert p.name == "anthropic"

    def test_missing_key_raises(self):
        p = AnthropicProvider(api_key="")
        with pytest.raises(ProviderError, match="API key not set"):
            p.complete("system", "user")

    def test_complete_success(self, httpx_mock):
        httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            json={
                "content": [{"type": "text", "text": "Claude says hello."}],
            },
        )
        p = AnthropicProvider(api_key="sk-ant-test")
        result = p.complete("system", "user")
        assert result == "Claude says hello."

    def test_sends_correct_headers(self, httpx_mock):
        httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            json={"content": [{"type": "text", "text": "ok"}]},
        )
        p = AnthropicProvider(api_key="sk-ant-key")
        p.complete("s", "u")

        request = httpx_mock.get_request()
        assert request.headers["x-api-key"] == "sk-ant-key"
        assert request.headers["anthropic-version"] == "2023-06-01"

    def test_sends_temperature(self, httpx_mock):
        httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            json={"content": [{"type": "text", "text": "ok"}]},
        )
        p = AnthropicProvider(api_key="sk-ant-key", temperature=0.1)
        p.complete("s", "u")

        import json

        payload = json.loads(httpx_mock.get_request().read())
        assert payload["temperature"] == 0.1

    def test_http_error(self, httpx_mock):
        httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            status_code=429,
            text="Rate limited",
        )
        p = AnthropicProvider(api_key="sk-ant-test")
        with pytest.raises(ProviderError, match="HTTP 429"):
            p.complete("s", "u")

    def test_health_check_with_key(self):
        assert AnthropicProvider(api_key="key").check_health() is True

    def test_health_check_without_key(self):
        assert AnthropicProvider(api_key="").check_health() is False

    def test_complete_timeout(self, httpx_mock):
        import httpx

        httpx_mock.add_exception(httpx.ReadTimeout("timed out"))
        p = AnthropicProvider(api_key="sk-ant-test")
        with pytest.raises(ProviderError, match="timed out"):
            p.complete("s", "u")

    def test_complete_connect_error(self, httpx_mock):
        import httpx

        httpx_mock.add_exception(httpx.ConnectError("refused"))
        p = AnthropicProvider(api_key="sk-ant-test")
        with pytest.raises(ProviderError, match="Cannot connect"):
            p.complete("s", "u")

    def test_malformed_response(self, httpx_mock):
        httpx_mock.add_response(
            url="https://api.anthropic.com/v1/messages",
            json={"error": {"message": "Something broke"}},
        )
        p = AnthropicProvider(api_key="sk-ant-test")
        with pytest.raises(ProviderError, match="Something broke"):
            p.complete("s", "u")
