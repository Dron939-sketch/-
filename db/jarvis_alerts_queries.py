"""Async-helpers для проактивных алертов Джарвиса.

Идея: scheduler пишет сюда триггеры (кризис, провал метрик), фронт
polling'ит и показывает toast'ом. Дедупликация — по (city_id, key),
чтобы один и тот же алерт не плодился каждые 15 минут.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .pool import get_pool

logger = logging.getLogger(__name__)


_UPSERT_SQL = """
INSERT INTO jarvis_alerts
    (city_id, key, level, title, summary, payload, expires_at)
VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
ON CONFLICT (city_id, key) DO UPDATE SET
    level             = EXCLUDED.level,
    title             = EXCLUDED.title,
    summary           = EXCLUDED.summary,
    payload           = EXCLUDED.payload,
    last_triggered_at = NOW(),
    expires_at        = EXCLUDED.expires_at
RETURNING id
"""


async def upsert_alert(
    *,
    city_id: int,
    key: str,
    title: str,
    level: str = "info",
    summary: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    ttl_hours: int = 24,
) -> Optional[int]:
    """Вставить/обновить один алерт. Возвращает id строки или None."""
    if not city_id or not key or not title:
        return None
    pool = get_pool()
    if pool is None:
        return None
    expires = datetime.now(tz=timezone.utc) + timedelta(hours=int(ttl_hours))
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                _UPSERT_SQL,
                int(city_id), key[:80], level[:30], title[:200],
                (summary or "")[:500],
                json.dumps(payload or {}, ensure_ascii=False),
                expires,
            )
            return int(row["id"]) if row else None
    except Exception:  # noqa: BLE001
        logger.warning("upsert_alert failed for city %s key %s", city_id, key, exc_info=False)
        return None


async def list_active_for_city(
    city_id: int, *, since_id: int = 0, limit: int = 20,
) -> List[Dict[str, Any]]:
    """Активные (не expires_at < now) алерты для города. since_id —
    клиентский last_seen_id, чтобы возвращать только новые."""
    pool = get_pool()
    if pool is None:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, key, level, title, summary, payload,
                       created_at, last_triggered_at
                FROM jarvis_alerts
                WHERE city_id = $1
                  AND id > $2
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY last_triggered_at DESC
                LIMIT $3
                """,
                int(city_id), int(since_id), int(max(1, min(limit, 100))),
            )
        out: List[Dict[str, Any]] = []
        for r in rows:
            payload = r["payload"]
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    payload = {}
            out.append({
                "id":                int(r["id"]),
                "key":               r["key"],
                "level":             r["level"],
                "title":             r["title"],
                "summary":           r["summary"],
                "payload":           payload or {},
                "created_at":        r["created_at"].isoformat() if r["created_at"] else None,
                "last_triggered_at": r["last_triggered_at"].isoformat() if r["last_triggered_at"] else None,
            })
        return out
    except Exception:  # noqa: BLE001
        return []


async def cleanup_expired() -> int:
    """Удалить просроченные. Вызывается scheduler-ом."""
    pool = get_pool()
    if pool is None:
        return 0
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM jarvis_alerts WHERE expires_at IS NOT NULL AND expires_at < NOW()",
            )
        try:
            return int(result.split(" ")[-1])
        except Exception:  # noqa: BLE001
            return 0
    except Exception:  # noqa: BLE001
        return 0
