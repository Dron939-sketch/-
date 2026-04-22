"""Typed async query helpers.

Every function is fail-safe: if the pool is missing or the query raises,
it logs and returns `None` / `[]` / `0` so callers can keep serving
placeholder data. That way a dead DB never takes the web tier down.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterable, List, Optional

from collectors.base import CollectedItem

from .pool import get_pool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

_UPSERT_NEWS_SQL = """
INSERT INTO news
    (id, city_id, source_kind, source_handle, title, content, url, author,
     category, published_at, sentiment, severity, summary, enrichment)
VALUES
    ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::jsonb)
ON CONFLICT (id) DO UPDATE SET
    title        = COALESCE(EXCLUDED.title, news.title),
    content      = COALESCE(EXCLUDED.content, news.content),
    url          = COALESCE(EXCLUDED.url, news.url),
    author       = COALESCE(EXCLUDED.author, news.author),
    category     = COALESCE(EXCLUDED.category, news.category),
    published_at = EXCLUDED.published_at,
    sentiment    = COALESCE(EXCLUDED.sentiment, news.sentiment),
    severity     = COALESCE(EXCLUDED.severity, news.severity),
    summary      = COALESCE(EXCLUDED.summary, news.summary),
    enrichment   = COALESCE(EXCLUDED.enrichment, news.enrichment)
"""


async def upsert_news_batch(
    city_id: int, items: Iterable[CollectedItem]
) -> int:
    """Insert/update a batch of news rows for a city. Returns rows written."""
    pool = get_pool()
    items_list = list(items)
    if pool is None or not items_list:
        return 0

    rows: List[tuple] = []
    for it in items_list:
        enr = it.enrichment or {}
        rows.append(
            (
                it.id,
                city_id,
                it.source_kind,
                it.source_handle,
                it.title,
                it.content,
                it.url,
                it.author,
                enr.get("category") or it.category,
                it.published_at,
                enr.get("sentiment"),
                enr.get("severity"),
                enr.get("summary"),
                json.dumps(enr, ensure_ascii=False) if enr else None,
            )
        )

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(_UPSERT_NEWS_SQL, rows)
        return len(rows)
    except Exception:  # noqa: BLE001
        logger.warning("upsert_news_batch failed for city %s", city_id, exc_info=False)
        return 0


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------

_UPSERT_WEATHER_SQL = """
INSERT INTO weather
    (city_id, ts, temperature, feels_like, humidity, wind_speed, condition,
     condition_emoji, comfort_index, raw)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
ON CONFLICT (city_id, ts) DO UPDATE SET
    temperature     = EXCLUDED.temperature,
    feels_like      = EXCLUDED.feels_like,
    humidity        = EXCLUDED.humidity,
    wind_speed      = EXCLUDED.wind_speed,
    condition       = EXCLUDED.condition,
    condition_emoji = EXCLUDED.condition_emoji,
    comfort_index   = EXCLUDED.comfort_index,
    raw             = EXCLUDED.raw
"""


async def upsert_weather(city_id: int, snapshot: Dict[str, Any]) -> bool:
    pool = get_pool()
    if pool is None:
        return False
    ts = snapshot.get("ts") or datetime.now(tz=timezone.utc)
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                _UPSERT_WEATHER_SQL,
                city_id,
                ts,
                snapshot.get("temperature"),
                snapshot.get("feels_like"),
                snapshot.get("humidity"),
                snapshot.get("wind_speed"),
                snapshot.get("condition"),
                snapshot.get("condition_emoji"),
                snapshot.get("comfort_index"),
                json.dumps(snapshot.get("raw") or {}, ensure_ascii=False),
            )
        return True
    except Exception:  # noqa: BLE001
        logger.warning("upsert_weather failed for city %s", city_id, exc_info=False)
        return False


async def latest_weather(city_id: int) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    if pool is None:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT ts, temperature, feels_like, humidity, wind_speed,
                       condition, condition_emoji, comfort_index
                FROM weather WHERE city_id = $1
                ORDER BY ts DESC LIMIT 1
                """,
                city_id,
            )
        if row is None:
            return None
        return dict(row)
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Dashboard aggregates
# ---------------------------------------------------------------------------

_NEGATIVE_CATS = ("complaints", "utilities", "incidents")
_POSITIVE_CATS = ("culture", "sport", "official")


async def news_counts_last_24h(city_id: int) -> Dict[str, int]:
    """Return {negative, positive, total} counts for the last 24h."""
    pool = get_pool()
    if pool is None:
        return {"negative": 0, "positive": 0, "total": 0}
    since = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE category = ANY($2::text[])) AS negative,
                    COUNT(*) FILTER (WHERE category = ANY($3::text[])) AS positive,
                    COUNT(*) AS total
                FROM news
                WHERE city_id = $1 AND published_at >= $4
                """,
                city_id,
                list(_NEGATIVE_CATS),
                list(_POSITIVE_CATS),
                since,
            )
        if row is None:
            return {"negative": 0, "positive": 0, "total": 0}
        return {
            "negative": int(row["negative"] or 0),
            "positive": int(row["positive"] or 0),
            "total": int(row["total"] or 0),
        }
    except Exception:  # noqa: BLE001
        return {"negative": 0, "positive": 0, "total": 0}


async def top_recent_summaries(
    city_id: int,
    *,
    categories: Iterable[str],
    negative: bool = False,
    positive: bool = False,
    limit: int = 3,
) -> List[str]:
    """Return up to `limit` AI-summaries (or titles) for recent rows in the
    given categories. If `negative=True` we only accept rows with
    sentiment < -0.1 (and symmetrically for positive).
    """
    pool = get_pool()
    if pool is None:
        return []
    since = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    conds = ["city_id = $1", "published_at >= $2", "category = ANY($3::text[])"]
    args: List[Any] = [city_id, since, list(categories)]
    if negative:
        conds.append("sentiment IS NOT NULL AND sentiment < -0.1")
    if positive:
        conds.append("sentiment IS NOT NULL AND sentiment > 0.1")
    sql = f"""
        SELECT COALESCE(summary, title) AS text
        FROM news
        WHERE {' AND '.join(conds)} AND COALESCE(summary, title) IS NOT NULL
        ORDER BY severity DESC NULLS LAST, published_at DESC
        LIMIT {int(limit)}
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
        return [r["text"] for r in rows if r["text"]]
    except Exception:  # noqa: BLE001
        return []
