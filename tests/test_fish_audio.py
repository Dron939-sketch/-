"""Тесты Fish Audio TTS — без реальных HTTP-запросов."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from ai import fish_audio_service as fa


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    for k in (
        "FISH_AUDIO_API_KEY", "FISH_AUDIO_VOICE_ID",
        "FISH_AUDIO_LATENCY", "FISH_AUDIO_BITRATE",
    ):
        monkeypatch.delenv(k, raising=False)
    yield


def test_is_configured_without_key():
    assert fa.is_configured() is False


def test_is_configured_with_key(monkeypatch):
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "sk-xxx")
    assert fa.is_configured() is True


def test_synthesize_returns_none_without_key():
    out = asyncio.run(fa.synthesize("привет"))
    assert out is None


def test_synthesize_returns_none_without_voice_id(monkeypatch):
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "sk-xxx")
    out = asyncio.run(fa.synthesize("привет"))
    assert out is None


def test_synthesize_returns_none_for_empty_text(monkeypatch):
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "sk-xxx")
    monkeypatch.setenv("FISH_AUDIO_VOICE_ID", "voice-1")
    assert asyncio.run(fa.synthesize("")) is None
    assert asyncio.run(fa.synthesize("   ")) is None


class _FakeResp:
    def __init__(self, status_code, content=b""):
        self.status_code = status_code
        self.content = content
        self.text = content.decode("utf-8", errors="replace") if content else ""


class _FakeClient:
    def __init__(self, response):
        self.response = response
        self.last_post = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, json=None, headers=None):
        self.last_post = {"url": url, "json": json, "headers": headers}
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_synthesize_success(monkeypatch):
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "sk-xxx")
    monkeypatch.setenv("FISH_AUDIO_VOICE_ID", "voice-42")
    fake = _FakeClient(_FakeResp(200, b"\xff" * 200))
    with patch("ai.fish_audio_service.httpx.AsyncClient", return_value=fake):
        out = asyncio.run(fa.synthesize("Привет, Коломна"))
    assert out is not None
    assert len(out) == 200
    # Проверяем payload
    p = fake.last_post["json"]
    assert p["text"] == "Привет, Коломна"
    assert p["reference_id"] == "voice-42"
    assert p["format"] == "mp3"
    assert p["mp3_bitrate"] == 128
    assert p["latency"] == "balanced"
    assert fake.last_post["headers"]["Authorization"] == "Bearer sk-xxx"


def test_synthesize_payment_required(monkeypatch):
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "sk-xxx")
    monkeypatch.setenv("FISH_AUDIO_VOICE_ID", "voice-42")
    fake = _FakeClient(_FakeResp(402, b"Payment required"))
    with patch("ai.fish_audio_service.httpx.AsyncClient", return_value=fake):
        out = asyncio.run(fa.synthesize("test"))
    assert out is None


def test_synthesize_short_response_rejected(monkeypatch):
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "sk-xxx")
    monkeypatch.setenv("FISH_AUDIO_VOICE_ID", "voice-42")
    fake = _FakeClient(_FakeResp(200, b"\x00" * 50))   # < 100 байт
    with patch("ai.fish_audio_service.httpx.AsyncClient", return_value=fake):
        out = asyncio.run(fa.synthesize("test"))
    assert out is None


def test_synthesize_other_status(monkeypatch):
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "sk-xxx")
    monkeypatch.setenv("FISH_AUDIO_VOICE_ID", "voice-42")
    fake = _FakeClient(_FakeResp(503, b"Service unavailable"))
    with patch("ai.fish_audio_service.httpx.AsyncClient", return_value=fake):
        out = asyncio.run(fa.synthesize("test"))
    assert out is None


def test_synthesize_swallows_exception(monkeypatch):
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "sk-xxx")
    monkeypatch.setenv("FISH_AUDIO_VOICE_ID", "voice-42")
    fake = _FakeClient(RuntimeError("network died"))
    with patch("ai.fish_audio_service.httpx.AsyncClient", return_value=fake):
        out = asyncio.run(fa.synthesize("test"))
    assert out is None


def test_bitrate_override(monkeypatch):
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "sk-xxx")
    monkeypatch.setenv("FISH_AUDIO_VOICE_ID", "voice-1")
    monkeypatch.setenv("FISH_AUDIO_BITRATE", "192")
    fake = _FakeClient(_FakeResp(200, b"\xff" * 200))
    with patch("ai.fish_audio_service.httpx.AsyncClient", return_value=fake):
        asyncio.run(fa.synthesize("test"))
    assert fake.last_post["json"]["mp3_bitrate"] == 192


def test_latency_override(monkeypatch):
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "sk-xxx")
    monkeypatch.setenv("FISH_AUDIO_VOICE_ID", "voice-1")
    monkeypatch.setenv("FISH_AUDIO_LATENCY", "normal")
    fake = _FakeClient(_FakeResp(200, b"\xff" * 200))
    with patch("ai.fish_audio_service.httpx.AsyncClient", return_value=fake):
        asyncio.run(fa.synthesize("test"))
    assert fake.last_post["json"]["latency"] == "normal"


def test_invalid_latency_falls_back_to_balanced(monkeypatch):
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "sk-xxx")
    monkeypatch.setenv("FISH_AUDIO_VOICE_ID", "voice-1")
    monkeypatch.setenv("FISH_AUDIO_LATENCY", "lightspeed")
    fake = _FakeClient(_FakeResp(200, b"\xff" * 200))
    with patch("ai.fish_audio_service.httpx.AsyncClient", return_value=fake):
        asyncio.run(fa.synthesize("test"))
    assert fake.last_post["json"]["latency"] == "balanced"


def test_long_text_truncated(monkeypatch):
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "sk-xxx")
    monkeypatch.setenv("FISH_AUDIO_VOICE_ID", "voice-1")
    fake = _FakeClient(_FakeResp(200, b"\xff" * 200))
    with patch("ai.fish_audio_service.httpx.AsyncClient", return_value=fake):
        asyncio.run(fa.synthesize("а" * 6000))
    assert len(fake.last_post["json"]["text"]) <= 4500
