"""Unit tests for the NVIDIA LLM provider (Step 2). No network access."""

import pytest

from app.services import llm
from app.core.config import settings


class _FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _FakeClient:
    """Minimal async-context-manager stand-in for httpx.AsyncClient."""

    def __init__(self, handler, calls):
        self._handler = handler
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None):
        self._calls.append({"url": url, "json": json, "headers": headers})
        return self._handler(self._calls, url, json, headers)


def _install_fake(monkeypatch, handler):
    calls = []
    monkeypatch.setattr(
        llm.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeClient(handler, calls),
    )
    return calls


def _ok(text):
    return _FakeResponse(200, {"choices": [{"message": {"content": text}}]})


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def _fast(_delay):
        return None

    monkeypatch.setattr(llm.asyncio, "sleep", _fast)


@pytest.fixture
def _key(monkeypatch):
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "test-key-123")
    return "test-key-123"


MESSAGES = [{"role": "user", "content": "hello"}]


async def test_missing_key_raises_before_http(monkeypatch):
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", None)
    calls = _install_fake(monkeypatch, lambda *a: _ok("never"))

    with pytest.raises(llm.LLMUnavailableError, match="NVIDIA_API_KEY"):
        await llm.chat(MESSAGES)
    assert calls == []


async def test_retry_429_then_success(monkeypatch, _key):
    responses = [_FakeResponse(429), _FakeResponse(429), _ok("hi")]
    calls = _install_fake(monkeypatch, lambda *a: responses.pop(0))

    result = await llm.chat(MESSAGES)
    assert result["text"] == "hi"
    assert result["model"] == settings.NVIDIA_MODEL_FAST
    assert isinstance(result["latency_seconds"], float)
    assert len(calls) == 3


async def test_primary_500_falls_back_to_strong(monkeypatch, _key):
    def handler(calls, url, payload, headers):
        if payload["model"] == settings.NVIDIA_MODEL_FAST:
            return _FakeResponse(500)
        return _ok("strong answer")

    calls = _install_fake(monkeypatch, handler)

    result = await llm.chat(MESSAGES)
    assert result["text"] == "strong answer"
    assert result["model"] == settings.NVIDIA_MODEL_STRONG
    # 3 attempts on fast, then 1 on strong.
    assert len(calls) == 4


async def test_400_raises_immediately_without_key_leak(monkeypatch, _key):
    calls = _install_fake(monkeypatch, lambda *a: _FakeResponse(400))

    with pytest.raises(llm.LLMUnavailableError) as excinfo:
        await llm.chat(MESSAGES)
    assert "HTTP 400" in str(excinfo.value)
    assert "test-key-123" not in str(excinfo.value)
    assert len(calls) == 1


def test_candidate_models():
    assert llm.candidate_models() == [
        "nvidia/nemotron-3-nano-30b-a3b",
        "openai/gpt-oss-20b",
        "nvidia/nemotron-3-super-120b-a12b",
        "meta/llama-3.3-70b-instruct",
    ]
