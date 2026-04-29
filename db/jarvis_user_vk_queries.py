"""Async-helpers для привязки пользователем своей VK-страницы.

Identity (anon UUID из Джарвиса) → vk_handle (screen_name или owner_id).
Используется для персонального аудита — пользователь привязывает свою
страницу одной кнопкой и запускает аудит из виджета.

Все функции fail-safe: на null pool возвращают None / False.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from .pool import get_pool

logger = logging.getLogger(__name__)


_HANDLE_RE = re.compile(r"^[A-Za-z0-9_.\-]{2,80}$")


def normalize_handle(raw: str) -> Optional[str]:
    """Извлечь VK screen_name из произвольного ввода:
      "ivanov"                       → "ivanov"
      "https://vk.com/ivanov"        → "ivanov"
      "vk.com/id12345"               → "id12345"
      "  ivanov  "                   → "ivanov"
      "https://vk.com/ivanov/feed"   → "ivanov"
      "@ivanov"                      → "ivanov"
    Возвращает None если не парсится."""
    if not raw:
        return None
    s = raw.strip().lstrip("@")
    # vk.com / m.vk.com / https://vk.com
    s = re.sub(r"^https?://", "", s)
    s = re.sub(r"^(m\.)?vk\.com/", "", s)
    # обрезаем хвост "/feed", "?ref=..." и т.д.
    s = s.split("/", 1)[0]
    s = s.split("?", 1)[0]
    s = s.strip()
    if not s:
        return None
    if not _HANDLE_RE.match(s):
        return None
    return s


_UPSERT_SQL = """
INSERT INTO jarvis_user_vk (identity, vk_handle, user_label, archetype)
VALUES ($1, $2, $3, $4)
ON CONFLICT (identity) DO UPDATE SET
    vk_handle  = EXCLUDED.vk_handle,
    user_label = COALESCE(EXCLUDED.user_label, jarvis_user_vk.user_label),
    archetype  = COALESCE(EXCLUDED.archetype, jarvis_user_vk.archetype)
RETURNING identity
"""


async def upsert_link(
    identity: str, vk_handle: str,
    user_label: Optional[str] = None,
    archetype: Optional[str] = None,
) -> bool:
    if not identity or not vk_handle:
        return False
    pool = get_pool()
    if pool is None:
        return False
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                _UPSERT_SQL,
                identity[:80], vk_handle[:80],
                (user_label or "")[:120] or None,
                (archetype or "")[:40] or None,
            )
            return row is not None
    except Exception:  # noqa: BLE001
        logger.warning("upsert_link failed for %s", identity, exc_info=False)
        return False


async def get_link(identity: str) -> Optional[Dict[str, Any]]:
    if not identity:
        return None
    pool = get_pool()
    if pool is None:
        return None
    try:
        async with pool.acquire() as conn:
            r = await conn.fetchrow(
                """
                SELECT identity, vk_handle, user_label, archetype,
                       created_at, last_audit_at
                FROM jarvis_user_vk
                WHERE identity = $1
                """,
                identity,
            )
        if r is None:
            return None
        return {
            "identity":      r["identity"],
            "vk_handle":     r["vk_handle"],
            "user_label":    r["user_label"],
            "archetype":     r["archetype"],
            "created_at":    r["created_at"].isoformat() if r["created_at"] else None,
            "last_audit_at": r["last_audit_at"].isoformat() if r["last_audit_at"] else None,
        }
    except Exception:  # noqa: BLE001
        return None


async def touch_audit(identity: str) -> None:
    """Обновить last_audit_at — отмечаем что недавно делали аудит."""
    if not identity:
        return
    pool = get_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE jarvis_user_vk SET last_audit_at = NOW() "
                "WHERE identity = $1",
                identity,
            )
    except Exception:  # noqa: BLE001
        pass


async def delete_link(identity: str) -> bool:
    if not identity:
        return False
    pool = get_pool()
    if pool is None:
        return False
    try:
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM jarvis_user_vk WHERE identity = $1",
                identity,
            )
        return "1" in result.split(" ")[-1]
    except Exception:  # noqa: BLE001
        return False
