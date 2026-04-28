"""Учёт расхода DeepSeek API: запись + агрегация для админки.

Запись (`log_call`) — fail-safe: на отсутствующем pool просто молча
no-op, никогда не блокирует основной enricher pipeline.

Агрегация (`summary`, `daily`) — для admin-эндпоинтов.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db.pool import get_pool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

async def log_call(
    *,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    prompt_cache_hit_tokens: int = 0,
    prompt_cache_miss_tokens: int = 0,
    cost_usd: float = 0.0,
    cached_from_redis: bool = False,
) -> None:
    pool = get_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO deepseek_usage
                    (model, prompt_tokens, completion_tokens, total_tokens,
                     prompt_cache_hit_tokens, prompt_cache_miss_tokens,
                     cost_usd, cached_from_redis)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                model,
                int(prompt_tokens),
                int(completion_tokens),
                int(total_tokens),
                int(prompt_cache_hit_tokens),
                int(prompt_cache_miss_tokens),
                float(cost_usd),
                bool(cached_from_redis),
            )
    except Exception:  # noqa: BLE001
        logger.debug("deepseek_usage.log_call failed", exc_info=False)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

async def summary(days: int = 7) -> Dict[str, Any]:
    """Сводка за окно: вызовы, токены, стоимость, cache hit rate."""
    pool = get_pool()
    if pool is None:
        return _empty_summary(days)
    days = max(1, min(365, int(days)))
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*)                                AS calls,
                    COUNT(*) FILTER (WHERE cached_from_redis) AS redis_cached_calls,
                    COALESCE(SUM(prompt_tokens), 0)         AS prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0)     AS completion_tokens,
                    COALESCE(SUM(total_tokens), 0)          AS total_tokens,
                    COALESCE(SUM(prompt_cache_hit_tokens), 0)  AS cache_hit_tokens,
                    COALESCE(SUM(prompt_cache_miss_tokens), 0) AS cache_miss_tokens,
                    COALESCE(SUM(cost_usd), 0)              AS cost_usd
                FROM deepseek_usage
                WHERE created_at >= $1
                """,
                since,
            )
    except Exception:  # noqa: BLE001
        return _empty_summary(days)

    calls = int(row["calls"] or 0)
    cache_hit = int(row["cache_hit_tokens"] or 0)
    cache_miss = int(row["cache_miss_tokens"] or 0)
    cache_total = cache_hit + cache_miss
    return {
        "window_days":          days,
        "calls":                calls,
        "redis_cached_calls":   int(row["redis_cached_calls"] or 0),
        "prompt_tokens":        int(row["prompt_tokens"] or 0),
        "completion_tokens":    int(row["completion_tokens"] or 0),
        "total_tokens":         int(row["total_tokens"] or 0),
        "cache_hit_tokens":     cache_hit,
        "cache_miss_tokens":    cache_miss,
        "cache_hit_rate_pct":   round(100.0 * cache_hit / cache_total, 1) if cache_total > 0 else None,
        "cost_usd":             float(row["cost_usd"] or 0),
        "avg_cost_per_call_usd":(
            round(float(row["cost_usd"] or 0) / calls, 6) if calls > 0 else None
        ),
    }


def _empty_summary(days: int) -> Dict[str, Any]:
    return {
        "window_days": days, "calls": 0, "redis_cached_calls": 0,
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        "cache_hit_tokens": 0, "cache_miss_tokens": 0,
        "cache_hit_rate_pct": None, "cost_usd": 0.0,
        "avg_cost_per_call_usd": None,
    }


async def daily(days: int = 30) -> List[Dict[str, Any]]:
    """День → {calls, total_tokens, cost_usd}. Самые свежие — последними."""
    pool = get_pool()
    if pool is None:
        return []
    days = max(1, min(365, int(days)))
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT date_trunc('day', created_at)::date AS day,
                       COUNT(*)                              AS calls,
                       COALESCE(SUM(total_tokens), 0)        AS total_tokens,
                       COALESCE(SUM(cost_usd), 0)            AS cost_usd
                FROM deepseek_usage
                WHERE created_at >= $1
                GROUP BY day
                ORDER BY day
                """,
                since,
            )
        return [
            {
                "day":          r["day"].isoformat() if r["day"] else None,
                "calls":        int(r["calls"]),
                "total_tokens": int(r["total_tokens"]),
                "cost_usd":     float(r["cost_usd"]),
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        return []


async def by_model(days: int = 30) -> List[Dict[str, Any]]:
    """Расход в разрезе моделей."""
    pool = get_pool()
    if pool is None:
        return []
    days = max(1, min(365, int(days)))
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT model,
                       COUNT(*)                                  AS calls,
                       COALESCE(SUM(prompt_tokens), 0)           AS prompt_tokens,
                       COALESCE(SUM(completion_tokens), 0)       AS completion_tokens,
                       COALESCE(SUM(prompt_cache_hit_tokens), 0) AS cache_hit_tokens,
                       COALESCE(SUM(cost_usd), 0)                AS cost_usd
                FROM deepseek_usage
                WHERE created_at >= $1
                GROUP BY model
                ORDER BY cost_usd DESC
                """,
                since,
            )
        return [
            {
                "model":             r["model"],
                "calls":             int(r["calls"]),
                "prompt_tokens":     int(r["prompt_tokens"]),
                "completion_tokens": int(r["completion_tokens"]),
                "cache_hit_tokens":  int(r["cache_hit_tokens"]),
                "cost_usd":          float(r["cost_usd"]),
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        return []
