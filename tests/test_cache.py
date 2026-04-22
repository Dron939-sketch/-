"""Tests for the DeepSeek response cache.

Use an in-memory `FakeRedis` that conforms to the duck-typed RedisLike
interface — no real broker, no network.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import pytest

from ai.cache import ResponseCache, make_cache_key


class FakeRedis:
    def __init__(self):
        self.store: Dict[str, str] = {}
        self.gets = 0
        self.sets = 0

    async def get(self, key: str) -> Optional[bytes]:
        self.gets += 1
        v = self.store.get(key)
        return v.encode("utf-8") if v is not None else None

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> Any:
        self.sets += 1
        self.store[key] = value
        return True


def test_make_cache_key_is_stable_and_keyed_by_model():
    a = make_cache_key("sys", "user", "deepseek-chat")
    b = make_cache_key("sys", "user", "deepseek-chat")
    c = make_cache_key("sys", "user", "deepseek-reasoner")
    assert a == b
    assert a != c
    assert a.startswith("citymind:ds:")


def test_disabled_cache_is_a_noop():
    cache = ResponseCache(redis=None)
    assert cache.enabled is False
    assert asyncio.run(cache.get("anything")) is None
    asyncio.run(cache.set("anything", {"x": 1}))  # must not raise


def test_cache_roundtrip_with_fake_redis():
    fake = FakeRedis()
    cache = ResponseCache(redis=fake, ttl_seconds=60)
    asyncio.run(cache.set("key1", {"items": [{"id": "a", "sentiment": -0.5}]}))
    assert fake.sets == 1
    payload = asyncio.run(cache.get("key1"))
    assert payload == {"items": [{"id": "a", "sentiment": -0.5}]}
    assert fake.gets == 1


def test_corrupt_payload_returns_none():
    fake = FakeRedis()
    fake.store["broken"] = "not-json"
    cache = ResponseCache(redis=fake)
    assert asyncio.run(cache.get("broken")) is None


def test_redis_failure_during_get_returns_none():
    class FailingRedis:
        async def get(self, key):
            raise ConnectionError("boom")

        async def set(self, *a, **kw):
            return None

    cache = ResponseCache(redis=FailingRedis())
    assert asyncio.run(cache.get("k")) is None
