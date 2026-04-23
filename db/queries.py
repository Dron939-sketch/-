"""Typed async query helpers.

Every function is fail-safe: if the pool is missing or the query raises,
it logs and returns `None` / `[]` / `0` so callers can keep serving
placeholder data. That way a dead DB never takes the web tier down.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

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


async def news_window(city_id: int, hours: int = 24) -> List[CollectedItem]:
    """Return CollectedItem objects from the last `hours` hours.

    We fully reconstruct the enrichment dict so the pure `snapshot_from_news`
    helper can consume rows straight from the DB the same way it consumes
    freshly-scraped items.
    """
    pool = get_pool()
    if pool is None:
        return []
    since = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT source_kind, source_handle, title, content, url,
                       author, category, published_at, sentiment, severity,
                       summary, enrichment
                FROM news
                WHERE city_id = $1 AND published_at >= $2
                ORDER BY published_at DESC
                LIMIT 500
                """,
                city_id,
                since,
            )
    except Exception:  # noqa: BLE001
        return []

    out: List[CollectedItem] = []
    for r in rows:
        enrichment = r["enrichment"]
        if isinstance(enrichment, str):
            try:
                enrichment = json.loads(enrichment)
            except json.JSONDecodeError:
                enrichment = None
        if enrichment is None and (
            r["sentiment"] is not None or r["summary"] is not None
        ):
            enrichment = {
                "sentiment": r["sentiment"],
                "category": r["category"],
                "severity": r["severity"],
                "summary": r["summary"],
            }
        out.append(
            CollectedItem(
                source_kind=r["source_kind"],
                source_handle=r["source_handle"],
                title=r["title"] or "",
                content=r["content"] or "",
                published_at=r["published_at"],
                url=r["url"],
                author=r["author"],
                category=r["category"],
                enrichment=enrichment,
            )
        )
    return out


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
# Metrics timeseries
# ---------------------------------------------------------------------------

_INSERT_METRICS_SQL = """
INSERT INTO metrics (city_id, ts, sb, tf, ub, chv, trust_index, happiness_index)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (city_id, ts) DO UPDATE SET
    sb = EXCLUDED.sb,
    tf = EXCLUDED.tf,
    ub = EXCLUDED.ub,
    chv = EXCLUDED.chv,
    trust_index = EXCLUDED.trust_index,
    happiness_index = EXCLUDED.happiness_index
"""


async def insert_metrics(city_id: int, values: Dict[str, float],
                         ts: Optional[datetime] = None) -> bool:
    pool = get_pool()
    if pool is None:
        return False
    ts = ts or datetime.now(tz=timezone.utc)
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                _INSERT_METRICS_SQL,
                city_id,
                ts,
                values.get("sb"),
                values.get("tf"),
                values.get("ub"),
                values.get("chv"),
                values.get("trust_index"),
                values.get("happiness_index"),
            )
        return True
    except Exception:  # noqa: BLE001
        logger.warning("insert_metrics failed for city %s", city_id, exc_info=False)
        return False


async def latest_metrics(city_id: int) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    if pool is None:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT ts, sb, tf, ub, chv, trust_index, happiness_index
                FROM metrics WHERE city_id = $1
                ORDER BY ts DESC LIMIT 1
                """,
                city_id,
            )
        return dict(row) if row else None
    except Exception:  # noqa: BLE001
        return None


async def metrics_trend_7d(city_id: int) -> Dict[str, float]:
    """Return 4-vector percentage change: (latest − row_7d_ago) / 6.

    Result keys are `safety / economy / quality / social` so the dashboard
    can drop it straight into the `trends` block. Vectors without history
    get 0.0 (no delta shown).
    """
    pool = get_pool()
    empty = {"safety": 0.0, "economy": 0.0, "quality": 0.0, "social": 0.0}
    if pool is None:
        return empty
    week_ago = datetime.now(tz=timezone.utc) - timedelta(days=7)
    try:
        async with pool.acquire() as conn:
            now_row = await conn.fetchrow(
                "SELECT sb, tf, ub, chv FROM metrics WHERE city_id=$1 "
                "ORDER BY ts DESC LIMIT 1",
                city_id,
            )
            old_row = await conn.fetchrow(
                "SELECT sb, tf, ub, chv FROM metrics "
                "WHERE city_id=$1 AND ts <= $2 "
                "ORDER BY ts DESC LIMIT 1",
                city_id, week_ago,
            )
    except Exception:  # noqa: BLE001
        return empty

    if now_row is None or old_row is None:
        return empty

    def _delta(key: str, col_now: str, col_old: str) -> float:
        a = now_row[col_now]
        b = old_row[col_old]
        if a is None or b is None:
            return 0.0
        return round((a - b) / 6.0, 3)

    return {
        "safety":  _delta("safety", "sb", "sb"),
        "economy": _delta("economy", "tf", "tf"),
        "quality": _delta("quality", "ub", "ub"),
        "social":  _delta("social", "chv", "chv"),
    }


async def metrics_history(
    city_id: int, days: int = 30
) -> Dict[str, List[Tuple[datetime, float]]]:
    """Return `{vector: [(ts, value), …]}` sorted ascending by ts."""
    pool = get_pool()
    empty: Dict[str, List[Tuple[datetime, float]]] = {
        "sb": [], "tf": [], "ub": [], "chv": [],
    }
    if pool is None:
        return empty
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT ts, sb, tf, ub, chv FROM metrics "
                "WHERE city_id=$1 AND ts >= $2 ORDER BY ts ASC",
                city_id, since,
            )
    except Exception:  # noqa: BLE001
        return empty

    out: Dict[str, List[Tuple[datetime, float]]] = {
        "sb": [], "tf": [], "ub": [], "chv": [],
    }
    for r in rows:
        for key in ("sb", "tf", "ub", "chv"):
            v = r[key]
            if v is not None:
                out[key].append((r["ts"], float(v)))
    return out


# ---------------------------------------------------------------------------
# Dashboard aggregates
# ---------------------------------------------------------------------------

_NEGATIVE_CATS = ("complaints", "utilities", "incidents")
_POSITIVE_CATS = ("culture", "sport", "official")


async def news_counts_last_24h(city_id: int) -> Dict[str, int]:
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


async def news_negative_count(city_id: int, hours: int) -> int:
    """Negative-sentiment (< -0.3) news count over the last `hours` hours."""
    pool = get_pool()
    if pool is None:
        return 0
    since = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) AS n FROM news "
                "WHERE city_id=$1 AND published_at >= $2 "
                "AND sentiment IS NOT NULL AND sentiment < -0.3",
                city_id, since,
            )
        return int(row["n"] or 0) if row else 0
    except Exception:  # noqa: BLE001
        return 0


async def appeals_count(city_id: int, hours: int) -> int:
    """Number of citizen appeals collected over the last `hours` hours."""
    pool = get_pool()
    if pool is None:
        return 0
    since = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) AS n FROM appeals "
                "WHERE city_id=$1 AND published_at >= $2",
                city_id, since,
            )
        return int(row["n"] or 0) if row else 0
    except Exception:  # noqa: BLE001
        return 0


async def top_recent_summaries(
    city_id: int,
    *,
    categories: Iterable[str],
    negative: bool = False,
    positive: bool = False,
    limit: int = 3,
) -> List[str]:
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
