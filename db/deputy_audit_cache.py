"""Кэш аудита/кабинета депутата в БД.

Запись по external_id из config/deputies.py. TTL 12 часов — за это
время рейтинг и метрики не успевают сильно измениться. Force-refresh
делается явным вызовом upsert (UPSERT перетирает payload).

На null pool возвращаем None — тогда вызывающий код спокойно
работает без кэша (расчёт каждый раз).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from .pool import get_pool

logger = logging.getLogger(__name__)


_TTL_HOURS = 12

# Версия структуры payload. При каждом добавлении нового топ-уровневого
# поля в _build_deputy_cabinet (briefing / meister / trends_now / …)
# инкрементить — это инвалидирует все старые записи в БД и заставляет
# пересчитать кабинет с актуальной структурой.
_CACHE_VERSION = 8


async def get_cached(external_id: str) -> Optional[Dict[str, Any]]:
    """Вернуть payload или None если кэша нет / он устарел."""
    if not external_id:
        return None
    pool = get_pool()
    if pool is None:
        return None
    try:
        async with pool.acquire() as conn:
            r = await conn.fetchrow(
                """
                SELECT payload, computed_at
                FROM deputy_audit_cache
                WHERE external_id = $1
                """,
                external_id,
            )
        if r is None:
            return None
        computed_at = r["computed_at"]
        if computed_at and (
            datetime.now(tz=timezone.utc) - computed_at > timedelta(hours=_TTL_HOURS)
        ):
            return None
        payload = r["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if isinstance(payload, dict):
            # Версия не совпадает — кэш устарел структурно, нужно пересчитать
            if payload.get("_cache_version") != _CACHE_VERSION:
                return None
            payload = dict(payload)
            payload["_cache"] = {
                "computed_at": computed_at.isoformat() if computed_at else None,
                "fresh": True,
            }
            return payload
        return None
    except Exception:  # noqa: BLE001
        logger.debug("deputy_audit_cache.get failed", exc_info=False)
        return None


async def upsert_cache(external_id: str, payload: Dict[str, Any]) -> bool:
    """Перезаписать кэш. Возвращает True при успехе."""
    if not external_id or not isinstance(payload, dict):
        return False
    pool = get_pool()
    if pool is None:
        return False
    try:
        # Не сериализуем _cache-метаданные — они только для UI
        clean = {k: v for k, v in payload.items() if k != "_cache"}
        clean["_cache_version"] = _CACHE_VERSION
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO deputy_audit_cache (external_id, payload, computed_at)
                VALUES ($1, $2::jsonb, NOW())
                ON CONFLICT (external_id) DO UPDATE SET
                    payload     = EXCLUDED.payload,
                    computed_at = NOW()
                """,
                external_id, json.dumps(clean, ensure_ascii=False, default=str),
            )
        return True
    except Exception:  # noqa: BLE001
        logger.warning("deputy_audit_cache.upsert failed for %s", external_id, exc_info=False)
        return False


async def invalidate(external_id: str) -> None:
    """Удалить кэш для одного депутата (для будущей кнопки Refresh)."""
    if not external_id:
        return
    pool = get_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM deputy_audit_cache WHERE external_id = $1",
                external_id,
            )
    except Exception:  # noqa: BLE001
        pass
