"""Unit tests for the operations/status helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pytest

from ops.status import Heartbeat, collect_health


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

def test_heartbeat_snapshot_starts_empty():
    Heartbeat.reset()
    snap = Heartbeat.snapshot()
    assert snap == {"collection": None, "weather": None, "snapshot": None}


def test_heartbeat_tick_records_timestamp():
    Heartbeat.reset()
    Heartbeat.tick("collection")
    snap = Heartbeat.snapshot()
    assert snap["collection"] is not None
    assert (datetime.now(tz=timezone.utc) - snap["collection"]).total_seconds() < 2


def test_heartbeat_ignores_unknown_loop_in_snapshot():
    Heartbeat.reset()
    Heartbeat.tick("made_up_loop")   # stored but not surfaced
    Heartbeat.tick("weather")
    snap = Heartbeat.snapshot()
    assert "made_up_loop" not in snap
    assert snap["weather"] is not None


# ---------------------------------------------------------------------------
# collect_health: DB probe
# ---------------------------------------------------------------------------

class _FakeConn:
    def __init__(self, raise_error: bool = False):
        self.raise_error = raise_error

    async def fetchval(self, sql: str):
        if self.raise_error:
            raise RuntimeError("db down")
        return 1


class _FakePool:
    """Async context-manager returning a _FakeConn from `acquire()`."""

    def __init__(self, raise_error: bool = False):
        self.raise_error = raise_error

    def acquire(self):
        parent = self

        class _CM:
            async def __aenter__(self_inner):
                return _FakeConn(raise_error=parent.raise_error)

            async def __aexit__(self_inner, *exc):
                return False

        return _CM()


class _FakeRedis:
    def __init__(self, raise_error: bool = False):
        self.raise_error = raise_error

    async def ping(self):
        if self.raise_error:
            raise RuntimeError("redis down")
        return True


class _FakeCache:
    def __init__(self, redis: Optional[_FakeRedis], enabled: bool = True):
        self._redis = redis
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled


@pytest.mark.asyncio
async def test_db_ok_when_pool_responds():
    Heartbeat.reset()
    report = await collect_health(pool=_FakePool(), cache=None, deepseek_api_key="k")
    assert report["components"]["database"]["status"] == "ok"


@pytest.mark.asyncio
async def test_db_disabled_when_pool_is_none():
    Heartbeat.reset()
    report = await collect_health(pool=None, cache=None, deepseek_api_key=None)
    assert report["components"]["database"]["status"] == "disabled"


@pytest.mark.asyncio
async def test_db_down_on_query_error():
    Heartbeat.reset()
    report = await collect_health(pool=_FakePool(raise_error=True), cache=None, deepseek_api_key=None)
    assert report["components"]["database"]["status"] == "down"


# ---------------------------------------------------------------------------
# Redis probe
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_redis_ok_when_ping_succeeds():
    Heartbeat.reset()
    cache = _FakeCache(redis=_FakeRedis(), enabled=True)
    report = await collect_health(pool=None, cache=cache, deepseek_api_key=None)
    assert report["components"]["redis"]["status"] == "ok"


@pytest.mark.asyncio
async def test_redis_disabled_when_cache_is_none():
    Heartbeat.reset()
    report = await collect_health(pool=None, cache=None, deepseek_api_key=None)
    assert report["components"]["redis"]["status"] == "disabled"


@pytest.mark.asyncio
async def test_redis_down_on_ping_error():
    Heartbeat.reset()
    cache = _FakeCache(redis=_FakeRedis(raise_error=True), enabled=True)
    report = await collect_health(pool=None, cache=cache, deepseek_api_key=None)
    assert report["components"]["redis"]["status"] == "down"


# ---------------------------------------------------------------------------
# DeepSeek probe
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deepseek_ok_when_key_set():
    Heartbeat.reset()
    report = await collect_health(pool=None, cache=None, deepseek_api_key="sk-abc")
    assert report["components"]["deepseek"]["status"] == "ok"


@pytest.mark.asyncio
async def test_deepseek_disabled_when_key_missing():
    Heartbeat.reset()
    report = await collect_health(pool=None, cache=None, deepseek_api_key="")
    assert report["components"]["deepseek"]["status"] == "disabled"


# ---------------------------------------------------------------------------
# Scheduler probe + rollup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scheduler_starting_when_no_ticks():
    Heartbeat.reset()
    report = await collect_health(pool=None, cache=None, deepseek_api_key=None)
    sch = report["components"]["scheduler"]
    assert sch["status"] == "starting"
    assert all(v["status"] == "starting" for v in sch["loops"].values())


@pytest.mark.asyncio
async def test_scheduler_ok_after_recent_tick():
    Heartbeat.reset()
    for name in ("collection", "weather", "snapshot"):
        Heartbeat.tick(name)
    report = await collect_health(pool=None, cache=None, deepseek_api_key=None)
    sch = report["components"]["scheduler"]
    assert sch["status"] == "ok"
    assert all(v["status"] == "ok" for v in sch["loops"].values())


@pytest.mark.asyncio
async def test_scheduler_stale_when_tick_too_old(monkeypatch):
    Heartbeat.reset()
    # Manually inject an ancient tick.
    Heartbeat._ticks["collection"] = datetime.now(tz=timezone.utc) - timedelta(hours=3)
    Heartbeat.tick("weather")
    Heartbeat.tick("snapshot")
    report = await collect_health(
        pool=None, cache=None, deepseek_api_key=None, stale_after_s=2400,
    )
    sch = report["components"]["scheduler"]
    assert sch["status"] == "stale"
    assert sch["loops"]["collection"]["status"] == "stale"
    assert sch["loops"]["weather"]["status"] == "ok"


# ---------------------------------------------------------------------------
# Overall rollup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_overall_ok_when_one_component_ok_others_disabled():
    Heartbeat.reset()
    for name in ("collection", "weather", "snapshot"):
        Heartbeat.tick(name)
    report = await collect_health(pool=None, cache=None, deepseek_api_key=None)
    # database + redis + deepseek all disabled; scheduler ok → overall ok.
    assert report["status"] == "ok"


@pytest.mark.asyncio
async def test_overall_down_when_any_component_down():
    Heartbeat.reset()
    for name in ("collection", "weather", "snapshot"):
        Heartbeat.tick(name)
    report = await collect_health(pool=_FakePool(raise_error=True), cache=None, deepseek_api_key=None)
    assert report["status"] == "down"


@pytest.mark.asyncio
async def test_overall_degraded_when_only_stale():
    Heartbeat.reset()
    Heartbeat._ticks["collection"] = datetime.now(tz=timezone.utc) - timedelta(hours=3)
    Heartbeat.tick("weather")
    Heartbeat.tick("snapshot")
    report = await collect_health(pool=None, cache=None, deepseek_api_key=None, stale_after_s=600)
    assert report["status"] == "degraded"


@pytest.mark.asyncio
async def test_report_shape_is_stable():
    Heartbeat.reset()
    report = await collect_health(pool=None, cache=None, deepseek_api_key=None)
    assert set(report.keys()) == {"status", "generated_at", "components"}
    assert set(report["components"].keys()) == {"database", "redis", "deepseek", "scheduler"}
