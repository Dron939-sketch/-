"""Loops-specific DB helpers.

Kept separate from `db.queries` so `queries.py` doesn't grow unboundedly.
Every helper is fail-safe in the same way — if the pool is missing or a
query raises, we log a warning and return an empty collection.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterable, List

from .pool import get_pool

logger = logging.getLogger(__name__)


_INSERT_LOOP_SQL = """
INSERT INTO loops (city_id, detected_at, name, description, strength, break_points)
VALUES ($1, $2, $3, $4, $5, $6::jsonb)
"""

_DELETE_STALE_SQL = """
DELETE FROM loops
WHERE city_id = $1 AND detected_at < $2
"""


async def replace_loops(
    city_id: int, loops: Iterable[Dict[str, Any]]
) -> int:
    """Insert a fresh batch of loops for a city.

    We append new rows rather than replacing existing ones, so the `loops`
    table keeps a history for audit. Stale rows (older than 7 days) are
    pruned on each call to keep the table bounded. Returns the number of
    inserted rows.
    """
    pool = get_pool()
    loops_list = list(loops)
    if pool is None or not loops_list:
        return 0

    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(days=7)

    rows: List[tuple] = []
    for loop in loops_list:
        rows.append(
            (
                city_id,
                now,
                str(loop.get("name") or "Петля")[:200],
                loop.get("description"),
                float(loop.get("strength") or 0.0),
                json.dumps(loop.get("break_points") or {}, ensure_ascii=False),
            )
        )

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(_DELETE_STALE_SQL, city_id, cutoff)
                await conn.executemany(_INSERT_LOOP_SQL, rows)
        return len(rows)
    except Exception:  # noqa: BLE001
        logger.warning("replace_loops failed for city %s", city_id, exc_info=False)
        return 0


async def latest_loops(city_id: int, limit: int = 3) -> List[Dict[str, Any]]:
    """Return the `limit` strongest loops from the most recent detection.

    We pick all rows tied to the latest `detected_at` for the city, then
    sort by `strength` descending and truncate. This gives the dashboard
    the current active top-N without showing historical rows.
    """
    pool = get_pool()
    if pool is None:
        return []
    try:
        async with pool.acquire() as conn:
            latest_ts = await conn.fetchval(
                "SELECT MAX(detected_at) FROM loops WHERE city_id = $1",
                city_id,
            )
            if latest_ts is None:
                return []
            rows = await conn.fetch(
                """
                SELECT name, description, strength, break_points, detected_at
                FROM loops
                WHERE city_id = $1 AND detected_at = $2
                ORDER BY strength DESC NULLS LAST
                LIMIT $3
                """,
                city_id, latest_ts, int(limit),
            )
    except Exception:  # noqa: BLE001
        return []

    out: List[Dict[str, Any]] = []
    for r in rows:
        bp = r["break_points"]
        if isinstance(bp, str):
            try:
                bp = json.loads(bp)
            except json.JSONDecodeError:
                bp = {}
        out.append(
            {
                "name": r["name"],
                "description": r["description"],
                "strength": float(r["strength"] or 0.0),
                "level": _level_from_strength(float(r["strength"] or 0.0)),
                "break_points": bp or {},
            }
        )
    return out


def _level_from_strength(strength: float) -> str:
    if strength >= 0.6:
        return "critical"
    if strength >= 0.3:
        return "warn"
    return "info"
