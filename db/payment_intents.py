"""Заявки на подписку — collect leads пока нет реальной оплаты.

Сохраняем в БД payment_intents и опционально оповещаем админа через
Max bot (если настроен подписчик с ролью admin).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .pool import get_pool

logger = logging.getLogger(__name__)


async def insert_intent(
    *,
    role:    Optional[str],
    party:   Optional[str],
    contact: Optional[str] = None,
    note:    Optional[str] = None,
    user_agent: Optional[str] = None,
    ip:      Optional[str] = None,
) -> Optional[int]:
    pool = get_pool()
    if pool is None:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO payment_intents
                  (role, party, contact, note, user_agent, ip)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                role, party, contact, note, user_agent, ip,
            )
            return int(row["id"]) if row else None
    except Exception:  # noqa: BLE001
        logger.warning("payment_intents.insert failed", exc_info=False)
        return None


async def list_recent(limit: int = 50) -> list:
    """Для админ-просмотра — последние заявки."""
    pool = get_pool()
    if pool is None:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, role, party, contact, note, status,
                       user_agent, ip, created_at
                FROM payment_intents
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
        return [
            {
                "id":          r["id"],
                "role":        r["role"],
                "party":       r["party"],
                "contact":     r["contact"],
                "note":        r["note"],
                "status":      r["status"],
                "user_agent":  r["user_agent"],
                "ip":          r["ip"],
                "created_at":  r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        return []
