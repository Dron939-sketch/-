"""Helpers для отметки прочитанных / отвеченных комментариев.

Реактивный трекер хранит state по comment_id, чтобы депутат не видел
тот же комментарий дважды. Fail-safe: на null pool возвращаем пустые
наборы.
"""

from __future__ import annotations

import logging
from typing import Iterable, Set

from .pool import get_pool

logger = logging.getLogger(__name__)


async def get_seen_ids(external_id: str) -> Set[str]:
    if not external_id:
        return set()
    pool = get_pool()
    if pool is None:
        return set()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT comment_id FROM deputy_comments_seen WHERE external_id = $1",
                external_id,
            )
        return {r["comment_id"] for r in rows}
    except Exception:  # noqa: BLE001
        return set()


async def mark_seen(external_id: str, comment_ids: Iterable[str], state: str = "seen") -> bool:
    ids = [str(c) for c in (comment_ids or []) if c]
    if not external_id or not ids:
        return False
    pool = get_pool()
    if pool is None:
        return False
    try:
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO deputy_comments_seen (external_id, comment_id, state)
                VALUES ($1, $2, $3)
                ON CONFLICT (external_id, comment_id) DO UPDATE
                  SET state = EXCLUDED.state,
                      seen_at = NOW()
                """,
                [(external_id, cid, state) for cid in ids],
            )
        return True
    except Exception:  # noqa: BLE001
        logger.warning("mark_seen failed for %s", external_id, exc_info=False)
        return False
