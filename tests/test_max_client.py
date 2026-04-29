"""Тесты Max-клиента (notify/max_client.py)."""

import asyncio
from unittest.mock import patch

import pytest

from notify import max_client


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    for k in ("MAX_BOT_TOKEN", "MAX_BOT_USERNAME"):
        monkeypatch.delenv(k, raising=False)
    yield


# ---------------------------------------------------------------------------
# is_configured / bot_username / deeplink
# ---------------------------------------------------------------------------

def test_is_configured_without_token():
    assert max_client.is_configured() is False


def test_is_configured_with_token(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "tok")
    assert max_client.is_configured() is True


def test_bot_username_default_empty():
    assert max_client.bot_username() == ""


def test_deeplink_requires_username(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "tok")
    out = max_client.deeplink_for("a" * 32)
    assert out is None  # нет MAX_BOT_USERNAME


def test_deeplink_full(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "tok")
    monkeypatch.setenv("MAX_BOT_USERNAME", "JarvisBot")
    out = max_client.deeplink_for("a" * 32)
    assert out is not None
    assert "max.ru/JarvisBot" in out
    assert "start=web_" in out
    assert "a" * 32 in out


def test_deeplink_empty_identity(monkeypatch):
    monkeypatch.setenv("MAX_BOT_USERNAME", "JarvisBot")
    assert max_client.deeplink_for("") is None


# ---------------------------------------------------------------------------
# parse_bot_started
# ---------------------------------------------------------------------------

def test_parse_bot_started_simple():
    event = {
        "update_type": "bot_started",
        "chat_id": 123,
        "payload": {"payload": "web_abc123def456ghi"},
        "user": {"name": "Иван"},
    }
    out = max_client.parse_bot_started(event)
    assert out["chat_id"] == "123"
    assert out["payload"] == "web_abc123def456ghi"
    assert out["user_name"] == "Иван"


def test_parse_bot_started_chat_in_payload():
    event = {
        "update_type": "bot_started",
        "payload": {"chat_id": 555, "payload": "web_xyz"},
        "user": {"first_name": "Аня"},
    }
    out = max_client.parse_bot_started(event)
    assert out["chat_id"] == "555"
    assert out["user_name"] == "Аня"


def test_parse_bot_started_wrong_type():
    assert max_client.parse_bot_started({"update_type": "message_created"}) is None


def test_parse_bot_started_no_chat():
    assert max_client.parse_bot_started({"update_type": "bot_started"}) is None


def test_parse_bot_started_not_dict():
    assert max_client.parse_bot_started(None) is None
    assert max_client.parse_bot_started([]) is None


# ---------------------------------------------------------------------------
# extract_identity_from_payload
# ---------------------------------------------------------------------------

def test_extract_identity_valid():
    out = max_client.extract_identity_from_payload("web_" + "a" * 32)
    assert out == "a" * 32


def test_extract_identity_too_short():
    assert max_client.extract_identity_from_payload("web_short") is None


def test_extract_identity_no_prefix():
    assert max_client.extract_identity_from_payload("nothing") is None


def test_extract_identity_empty():
    assert max_client.extract_identity_from_payload("") is None


# ---------------------------------------------------------------------------
# send_message — мок aiohttp
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, status, text=""):
        self.status = status
        self._text = text

    async def text(self): return self._text
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return None


class _FakeSession:
    def __init__(self, resp):
        self.resp = resp
        self.last_post = None

    def post(self, url, **kw):
        self.last_post = {"url": url, **kw}
        return self.resp

    async def __aenter__(self): return self
    async def __aexit__(self, *a): return None


def test_send_message_no_token():
    out = asyncio.run(max_client.send_message("123", "hi"))
    assert out is False


def test_send_message_success(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "tok")
    fake = _FakeSession(_FakeResp(200))
    with patch("notify.max_client.aiohttp.ClientSession", return_value=fake):
        out = asyncio.run(max_client.send_message("777", "Привет"))
    assert out is True
    assert fake.last_post["url"].endswith("/messages")
    assert fake.last_post["params"]["chat_id"] == "777"
    assert fake.last_post["json"]["text"] == "Привет"
    assert "Bearer tok" in fake.last_post["headers"]["Authorization"]


def test_send_message_error(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "tok")
    fake = _FakeSession(_FakeResp(403, "forbidden"))
    with patch("notify.max_client.aiohttp.ClientSession", return_value=fake):
        out = asyncio.run(max_client.send_message("777", "hi"))
    assert out is False


def test_send_message_swallows_exception(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "tok")

    class _Err:
        async def __aenter__(self): raise RuntimeError("network down")
        async def __aexit__(self, *a): return None

    with patch("notify.max_client.aiohttp.ClientSession", return_value=_Err()):
        out = asyncio.run(max_client.send_message("777", "hi"))
    assert out is False


# ---------------------------------------------------------------------------
# broadcast — sequential count of successes
# ---------------------------------------------------------------------------

def test_broadcast_counts_successes(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "tok")
    statuses = iter([200, 200, 500, 200])

    class _SeqSession:
        def post(self, url, **kw):
            return _FakeResp(next(statuses))
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None

    with patch("notify.max_client.aiohttp.ClientSession",
               side_effect=lambda *a, **kw: _SeqSession()):
        n = asyncio.run(max_client.broadcast(["a", "b", "c", "d"], "msg"))
    assert n == 3   # 200 + 200 + 500 (fail) + 200


def test_broadcast_empty():
    assert asyncio.run(max_client.broadcast([], "x")) == 0
    assert asyncio.run(max_client.broadcast(["a"], "")) == 0
