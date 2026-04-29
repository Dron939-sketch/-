"""Snapshot истории рейтинга депутата.

Раз в неделю записываем композит-рейтинг и метрики, чтобы депутат видел
динамику «было/стало». Идемпотентный UPSERT по (external_id, week_iso).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .pool import get_pool

logger = logging.getLogger(__name__)


def _current_week_iso() -> str:
    """ISO неделя в формате YYYY-Wnn. Для группировки snapshot'ов."""
    today = datetime.utcnow().date()
    iso = today.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


async def upsert_snapshot(
    external_id: str, *,
    composite_rating: Optional[float],
    alignment_pct:    Optional[float],
    posts_per_week:   Optional[float],
    avg_likes:        Optional[float],
    posts_count:      Optional[int],
) -> bool:
    if not external_id:
        return False
    pool = get_pool()
    if pool is None:
        return False
    week = _current_week_iso()
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO deputy_rating_history
                  (external_id, week_iso, composite_rating, alignment_pct,
                   posts_per_week, avg_likes, posts_count)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (external_id, week_iso) DO UPDATE SET
                  composite_rating = EXCLUDED.composite_rating,
                  alignment_pct    = EXCLUDED.alignment_pct,
                  posts_per_week   = EXCLUDED.posts_per_week,
                  avg_likes        = EXCLUDED.avg_likes,
                  posts_count      = EXCLUDED.posts_count,
                  taken_at         = NOW()
                """,
                external_id, week,
                composite_rating, alignment_pct,
                posts_per_week, avg_likes, posts_count,
            )
        return True
    except Exception:  # noqa: BLE001
        logger.warning("rating snapshot upsert failed for %s", external_id, exc_info=False)
        return False


async def fetch_history(external_id: str, weeks: int = 12) -> List[Dict[str, Any]]:
    """Последние N снимков по неделям, в хронологическом порядке (старые первыми)."""
    if not external_id:
        return []
    pool = get_pool()
    if pool is None:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT week_iso, composite_rating, alignment_pct,
                       posts_per_week, avg_likes, posts_count, taken_at
                FROM deputy_rating_history
                WHERE external_id = $1
                ORDER BY taken_at DESC
                LIMIT $2
                """,
                external_id, max(1, min(52, weeks)),
            )
        out = []
        for r in rows:
            out.append({
                "week":             r["week_iso"],
                "composite_rating": _f(r["composite_rating"]),
                "alignment_pct":    _f(r["alignment_pct"]),
                "posts_per_week":   _f(r["posts_per_week"]),
                "avg_likes":        _f(r["avg_likes"]),
                "posts_count":      r["posts_count"],
                "taken_at":         r["taken_at"].isoformat() if r["taken_at"] else None,
            })
        out.reverse()  # старые первыми, последний — текущая неделя
        return out
    except Exception:  # noqa: BLE001
        return []


def _f(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
