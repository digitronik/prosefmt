"""Tests for the Anthropic provider."""

from __future__ import annotations

import pytest

from reword.providers.anthropic import AnthropicProvider
from reword.providers.base import ProviderError


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
