"""Async-helpers для подписок на уведомления через Max.

Identity (anon UUID из localStorage Джарвиса) — стабильная привязка.
max_chat_id — приходит от Max API в webhook bot_started, это
endpoint для отправки сообщений.

prefs — словарь {critical: bool, daily_brief: bool, topics: bool}.
По умолчанию только critical=true (никто не хочет шума, кризис —
другое).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .pool import get_pool

logger = logging.getLogger(__name__)


_DEFAULT_PREFS: Dict[str, bool] = {
    "critical":    True,
    "daily_brief": False,
    "topics":      False,
}


def _loads(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


_UPSERT_BY_IDENTITY_SQL = """
INSERT INTO jarvis_max_subscribers
    (identity, max_chat_id, user_name, prefs, last_seen_at)
VALUES ($1, $2, $3, $4::jsonb, NOW())
ON CONFLICT (identity) DO UPDATE SET
    max_chat_id  = EXCLUDED.max_chat_id,
    user_name    = COALESCE(EXCLUDED.user_name, jarvis_max_subscribers.user_name),
    last_seen_at = NOW()
RETURNING id
"""


async def upsert_subscription(
    identity: str, max_chat_id: str,
    user_name: Optional[str] = None,
    prefs: Optional[Dict[str, bool]] = None,
) -> Optional[int]:
    """Привязать identity к max_chat_id. На повторе обновляет chat_id
    (если пользователь сменил аккаунт Max) и last_seen_at."""
    if not identity or not max_chat_id:
        return None
    pool = get_pool()
    if pool is None:
        return None
    p = dict(_DEFAULT_PREFS)
    if prefs:
        p.update({k: bool(v) for k, v in prefs.items() if k in p})
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                _UPSERT_BY_IDENTITY_SQL,
                identity[:80], str(max_chat_id)[:80],
                (user_name or "")[:120],
                json.dumps(p, ensure_ascii=False),
            )
            return int(row["id"]) if row else None
    except Exception:  # noqa: BLE001
        logger.warning("upsert_subscription failed for %s", identity, exc_info=False)
        return None


async def get_by_identity(identity: str) -> Optional[Dict[str, Any]]:
    if not identity:
        return None
    pool = get_pool()
    if pool is None:
        return None
    try:
        async with pool.acquire() as conn:
            r = await conn.fetchrow(
                """
                SELECT id, identity, max_chat_id, user_name, prefs,
                       created_at, last_seen_at
                FROM jarvis_max_subscribers
                WHERE identity = $1
                """,
                identity,
            )
        if r is None:
            return None
        return {
            "id":          int(r["id"]),
            "identity":    r["identity"],
            "max_chat_id": r["max_chat_id"],
            "user_name":   r["user_name"],
            "prefs":       _loads(r["prefs"], dict(_DEFAULT_PREFS)),
            "created_at":  r["created_at"].isoformat() if r["created_at"] else None,
            "last_seen_at": r["last_seen_at"].isoformat() if r["last_seen_at"] else None,
        }
    except Exception:  # noqa: BLE001
        return None


async def update_prefs(identity: str, prefs: Dict[str, bool]) -> bool:
    if not identity or not isinstance(prefs, dict):
        return False
    pool = get_pool()
    if pool is None:
        return False
    cleaned = {k: bool(v) for k, v in prefs.items() if k in _DEFAULT_PREFS}
    if not cleaned:
        return False
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE jarvis_max_subscribers
                SET prefs = COALESCE(prefs, '{}'::jsonb) || $2::jsonb
                WHERE identity = $1
                """,
                identity, json.dumps(cleaned, ensure_ascii=False),
            )
        try:
            n = int(result.split(" ")[-1])
        except Exception:  # noqa: BLE001
            n = 0
        return n > 0
    except Exception:  # noqa: BLE001
        return False


async def delete_subscription(identity: str) -> bool:
    pool = get_pool()
    if pool is None:
        return False
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM jarvis_max_subscribers WHERE identity = $1",
                identity,
            )
        return "1" in result.split(" ")[-1]
    except Exception:  # noqa: BLE001
        return False


async def list_chat_ids_for_pref(pref_key: str) -> List[str]:
    """Список max_chat_id всех подписчиков с включённым флагом pref_key.
    Используется broadcast'ом — proactivity loop, daily brief и т.п."""
    if pref_key not in _DEFAULT_PREFS:
        return []
    pool = get_pool()
    if pool is None:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT max_chat_id
                FROM jarvis_max_subscribers
                WHERE COALESCE((prefs ->> $1)::boolean, FALSE) = TRUE
                """,
                pref_key,
            )
        return [r["max_chat_id"] for r in rows if r["max_chat_id"]]
    except Exception:  # noqa: BLE001
        return []
