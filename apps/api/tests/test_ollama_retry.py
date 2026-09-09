import asyncio

import httpx
import pytest

from app import ollama


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FlakyClient:
    """Fails with a TransportError the first `fail_times` calls, then succeeds."""

    calls = {"count": 0}

    def __init__(self, fail_times, payload, **kwargs):
        self.fail_times = fail_times
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json):
        _FlakyClient.calls["count"] += 1
        if _FlakyClient.calls["count"] <= self.fail_times:
            raise httpx.ConnectError("connection refused")
        return _FakeResponse(self.payload)


def test_generate_retries_transient_failures_then_succeeds(monkeypatch):
    _FlakyClient.calls["count"] = 0
    monkeypatch.setattr(ollama, "RETRY_BACKOFF_SECONDS", 0)
    monkeypatch.setattr(ollama.httpx, "AsyncClient", lambda **kw: _FlakyClient(fail_times=1, payload={"response": "ok"}, **kw))

    text, model = asyncio.run(ollama.generate("hello", model="test-model"))
    assert text == "ok"
    assert model == "test-model"
    assert _FlakyClient.calls["count"] == 2


def test_generate_gives_up_after_max_attempts(monkeypatch):
    _FlakyClient.calls["count"] = 0
    monkeypatch.setattr(ollama, "RETRY_BACKOFF_SECONDS", 0)
    monkeypatch.setattr(ollama.httpx, "AsyncClient", lambda **kw: _FlakyClient(fail_times=99, payload={}, **kw))

    with pytest.raises(httpx.ConnectError):
        asyncio.run(ollama.generate("hello", model="test-model"))
    assert _FlakyClient.calls["count"] == ollama.MAX_ATTEMPTS
