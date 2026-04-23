"""System-health snapshot.

Two parts, both cheap:

  1. `Heartbeat` — in-process registry the scheduler pokes every tick so
     the health endpoint can tell whether the background loops are alive.
     No DB write; process restart resets the heartbeats to empty (which
     correctly surfaces as "not yet ticked" until the first cycle).

  2. `collect_health()` — pings the real dependencies (Postgres pool,
     Redis, DeepSeek key presence) and bundles everything into a report
     with an overall `status` string: ok | degraded | down.

Pure / fail-safe: every probe catches its own exceptions; the health
endpoint itself never raises.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# Fixed set so keys can't drift between scheduler / UI.
LOOP_NAMES = ("collection", "weather", "snapshot")


class Heartbeat:
    """Tiny in-process registry of {loop_name: last_tick_utc}."""

    _ticks: Dict[str, datetime] = {}

    @classmethod
    def tick(cls, loop_name: str) -> None:
        cls._ticks[loop_name] = datetime.now(tz=timezone.utc)

    @classmethod
    def snapshot(cls) -> Dict[str, Optional[datetime]]:
        return {name: cls._ticks.get(name) for name in LOOP_NAMES}

    @classmethod
    def reset(cls) -> None:
        cls._ticks.clear()


async def _probe_db(pool: Any, timeout: float = 2.0) -> Dict[str, Any]:
    if pool is None:
        return {"status": "disabled", "detail": "DATABASE_URL not set или pool не создан"}
    try:
        async with pool.acquire() as conn:
            await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=timeout)
        return {"status": "ok", "detail": "SELECT 1 прошёл"}
    except asyncio.TimeoutError:
        return {"status": "down", "detail": f"ping >{timeout}s"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "down", "detail": f"{type(exc).__name__}: {exc}"[:200]}


async def _probe_redis(cache: Any, timeout: float = 1.5) -> Dict[str, Any]:
    if cache is None or not getattr(cache, "enabled", False):
        return {"status": "disabled", "detail": "REDIS_URL не задан или кэш отключён"}
    redis = getattr(cache, "_redis", None)
    if redis is None:
        return {"status": "disabled", "detail": "redis клиент не инициализирован"}
    try:
        ping = redis.ping() if hasattr(redis, "ping") else None
        if asyncio.iscoroutine(ping):
            await asyncio.wait_for(ping, timeout=timeout)
            return {"status": "ok", "detail": "PING прошёл"}
        # Sync ping or no ping method → assume ok since connection exists.
        return {"status": "ok", "detail": "клиент живой"}
    except asyncio.TimeoutError:
        return {"status": "down", "detail": f"ping >{timeout}s"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "down", "detail": f"{type(exc).__name__}: {exc}"[:200]}


def _probe_deepseek(api_key: Optional[str]) -> Dict[str, Any]:
    if not api_key:
        return {"status": "disabled", "detail": "DEEPSEEK_API_KEY не задан"}
    return {"status": "ok", "detail": "ключ настроен (реальный запрос не делаем)"}


def _probe_scheduler(ticks: Dict[str, Optional[datetime]], stale_after_s: int) -> Dict[str, Any]:
    """Heartbeat rollup: every tracked loop should have ticked recently.

    - no ticks yet → status="starting"
    - any loop stale → "stale"
    - all fresh → "ok"
    """
    now = datetime.now(tz=timezone.utc)
    loops_status = {}
    never = 0
    stale = 0
    for name, ts in ticks.items():
        if ts is None:
            loops_status[name] = {"status": "starting", "last_tick": None, "age_seconds": None}
            never += 1
            continue
        age = (now - ts).total_seconds()
        entry_status = "stale" if age > stale_after_s else "ok"
        if entry_status == "stale":
            stale += 1
        loops_status[name] = {
            "status": entry_status,
            "last_tick": ts.isoformat(),
            "age_seconds": int(age),
        }

    if never == len(ticks):
        overall = "starting"
    elif stale > 0:
        overall = "stale"
    else:
        overall = "ok"
    return {"status": overall, "loops": loops_status}


def _rollup(probes: Dict[str, Dict[str, Any]]) -> str:
    """Overall status: `down` beats `stale` beats `disabled`/`starting` beats `ok`."""
    statuses = {p.get("status") for p in probes.values()}
    if "down" in statuses:
        return "down"
    if "stale" in statuses:
        return "degraded"
    if statuses <= {"ok", "disabled", "starting"} and "ok" in statuses:
        return "ok"
    return "degraded"


async def collect_health(
    *,
    pool: Any,
    cache: Any,
    deepseek_api_key: Optional[str],
    stale_after_s: int = 2400,   # 40 min — collection interval is 10 min, this is 4× slack
) -> Dict[str, Any]:
    """Assemble the full /health/system payload.

    Never raises. Every sub-probe is independent; one failure doesn't mask
    the others.
    """
    db_p, redis_p = await asyncio.gather(
        _probe_db(pool),
        _probe_redis(cache),
        return_exceptions=False,
    )
    deepseek_p = _probe_deepseek(deepseek_api_key)
    scheduler_p = _probe_scheduler(Heartbeat.snapshot(), stale_after_s=stale_after_s)

    probes = {
        "database":  db_p,
        "redis":     redis_p,
        "deepseek":  deepseek_p,
        "scheduler": scheduler_p,
    }
    overall = _rollup(probes)
    return {
        "status": overall,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "components": probes,
    }
