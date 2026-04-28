"""Тесты VK search функций (search_users, search_news) — мок aiohttp."""

import asyncio
from unittest.mock import patch

import pytest

from collectors import vk_discover


class _FakeResp:
    def __init__(self, payload):
        self.payload = payload

    async def json(self): return self.payload
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return None


class _FakeSession:
    def __init__(self, resp):
        self.resp = resp

    def get(self, url, **kw):
        return self.resp

    async def __aenter__(self): return self
    async def __aexit__(self, *a): return None


# ---------------------------------------------------------------------------
# search_users
# ---------------------------------------------------------------------------

def _fake_settings(token: str = "tok"):
    """Settings — frozen, мокаем целиком через SimpleNamespace."""
    from types import SimpleNamespace
    return SimpleNamespace(vk_api_token=token)


def test_search_users_no_token(monkeypatch):
    monkeypatch.setattr("collectors.vk_discover.settings", _fake_settings(""))
    out = asyncio.run(vk_discover.search_users("Иванов"))
    assert out == []


def test_search_users_short_query(monkeypatch):
    monkeypatch.setattr("collectors.vk_discover.settings", _fake_settings("tok"))
    out = asyncio.run(vk_discover.search_users("Ив"))
    assert out == []


def test_search_users_success(monkeypatch):
    monkeypatch.setattr("collectors.vk_discover.settings", _fake_settings("tok"))
    fake = _FakeSession(_FakeResp({
        "response": {
            "items": [
                {
                    "id": 100, "first_name": "Иван", "last_name": "Иванов",
                    "domain": "ivanov", "city": {"title": "Коломна"},
                    "photo_100": "https://x/p.jpg",
                    "bdate": "1.1.1990",
                },
                {
                    "id": 200, "first_name": "Игорь", "last_name": "Иванов",
                    "domain": "igor200", "city": "string-not-dict",
                    "photo_100": None,
                },
            ],
        },
    }))
    with patch("collectors.vk_discover.aiohttp.ClientSession", return_value=fake):
        out = asyncio.run(vk_discover.search_users("Иванов"))
    assert len(out) == 2
    assert out[0]["name"] == "Иван Иванов"
    assert out[0]["domain"] == "ivanov"
    assert out[0]["city"] == "Коломна"
    assert out[0]["url"] == "https://vk.com/ivanov"
    # city как строка — не падает
    assert out[1]["city"] is None


def test_search_users_handles_error(monkeypatch):
    monkeypatch.setattr("collectors.vk_discover.settings", _fake_settings("tok"))
    fake = _FakeSession(_FakeResp({"error": {"error_code": 5, "error_msg": "auth"}}))
    with patch("collectors.vk_discover.aiohttp.ClientSession", return_value=fake):
        out = asyncio.run(vk_discover.search_users("Иванов"))
    assert out == []


# ---------------------------------------------------------------------------
# search_news
# ---------------------------------------------------------------------------

def test_search_news_no_token(monkeypatch):
    monkeypatch.setattr("collectors.vk_discover.settings", _fake_settings(""))
    out = asyncio.run(vk_discover.search_news("дороги"))
    assert out == []


def test_search_news_success(monkeypatch):
    monkeypatch.setattr("collectors.vk_discover.settings", _fake_settings("tok"))
    fake = _FakeSession(_FakeResp({
        "response": {
            "items": [
                {
                    "text": "Сегодня яма на улице Ленина " * 5,
                    "owner_id": -100, "id": 555,
                    "likes": {"count": 12}, "reposts": {"count": 3},
                    "views": {"count": 500}, "date": 1700000000,
                },
                {
                    "text": "",   # пустые посты выкидываются
                    "owner_id": -100, "id": 556,
                },
            ],
        },
    }))
    with patch("collectors.vk_discover.aiohttp.ClientSession", return_value=fake):
        out = asyncio.run(vk_discover.search_news("дороги"))
    assert len(out) == 1
    assert "Ленина" in out[0]["text"]
    assert out[0]["likes"] == 12
    assert out[0]["url"] == "https://vk.com/wall-100_555"


def test_search_news_truncates_text(monkeypatch):
    monkeypatch.setattr("collectors.vk_discover.settings", _fake_settings("tok"))
    long = "а" * 1000
    fake = _FakeSession(_FakeResp({
        "response": {"items": [{"text": long, "owner_id": 1, "id": 2}]},
    }))
    with patch("collectors.vk_discover.aiohttp.ClientSession", return_value=fake):
        out = asyncio.run(vk_discover.search_news("test"))
    assert len(out[0]["text"]) <= 240
