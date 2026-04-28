"""Async-helpers для долговременной памяти Джарвиса.

Identity — случайный UUID, выдаётся фронтом при первом обращении.
Никаких PII, только тематические интересы и недавние вопросы.

Все функции fail-safe: если pool отсутствует или запрос падает —
возвращают пустой результат и не бросают, чтобы голосовой UI
никогда не зависел от состояния этой таблицы.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from .pool import get_pool

logger = logging.getLogger(__name__)


_INSERT_SQL = """
INSERT INTO jarvis_memory (identity, kind, payload, weight, last_seen_at)
VALUES ($1, $2, $3, 1, NOW())
ON CONFLICT (identity, kind, payload) DO UPDATE SET
    weight       = jarvis_memory.weight + 1,
    last_seen_at = NOW()
"""


async def upsert(identity: str, kind: str, payload: str) -> None:
    """Upsert одного факта. Невалидные значения тихо игнорятся."""
    if not identity or not kind or not payload:
        return
    if len(identity) > 80 or len(payload) > 240:
        return
    pool = get_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(_INSERT_SQL, identity, kind, payload[:240])
    except Exception:  # noqa: BLE001
        logger.debug("jarvis_memory upsert failed", exc_info=False)


async def list_recent(identity: str, *, limit: int = 12) -> List[Dict[str, Any]]:
    """Последние N фактов всех типов, с весом и временем."""
    if not identity:
        return []
    pool = get_pool()
    if pool is None:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT kind, payload, weight,
                       last_seen_at AT TIME ZONE 'UTC' AS last_seen_at
                FROM jarvis_memory
                WHERE identity = $1
                ORDER BY last_seen_at DESC
                LIMIT $2
                """,
                identity, int(max(1, min(limit, 50))),
            )
        return [
            {
                "kind":    r["kind"],
                "payload": r["payload"],
                "weight":  int(r["weight"]),
                "last_seen_at": (
                    r["last_seen_at"].isoformat() if r["last_seen_at"] else None
                ),
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        return []


async def top_topics(identity: str, *, limit: int = 5) -> List[Dict[str, Any]]:
    """Самые «весомые» (часто упоминаемые) темы пользователя."""
    if not identity:
        return []
    pool = get_pool()
    if pool is None:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT payload, weight
                FROM jarvis_memory
                WHERE identity = $1 AND kind = 'topic'
                ORDER BY weight DESC, last_seen_at DESC
                LIMIT $2
                """,
                identity, int(max(1, min(limit, 20))),
            )
        return [
            {"topic": r["payload"], "weight": int(r["weight"])}
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        return []


async def last_questions(identity: str, *, limit: int = 3) -> List[str]:
    """Последние вопросы пользователя (kind=recent_q), новейший первым."""
    if not identity:
        return []
    pool = get_pool()
    if pool is None:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT payload
                FROM jarvis_memory
                WHERE identity = $1 AND kind = 'recent_q'
                ORDER BY last_seen_at DESC
                LIMIT $2
                """,
                identity, int(max(1, min(limit, 10))),
            )
        return [r["payload"] for r in rows]
    except Exception:  # noqa: BLE001
        return []


async def forget_all(identity: str) -> None:
    """Полная очистка памяти по identity (приходит при clear-history)."""
    if not identity:
        return
    pool = get_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM jarvis_memory WHERE identity = $1", identity,
            )
    except Exception:  # noqa: BLE001
        pass
