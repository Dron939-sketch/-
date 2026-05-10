"""Fetch profile data from VK для одного пользователя.

Получаем avatar, status, about, city, followers — для блока «Образ
депутата» в кабинете. Best-effort: если API недоступно или handle
неверный — возвращаем None, кабинет работает без этих данных.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


async def fetch_profile(handle: str) -> Optional[Dict[str, Any]]:
    """Через users.get берём расширенный профиль одного пользователя.
    handle может быть screen_name (ivanov) или owner_id (id12345).
    """
    if not handle:
        return None
    try:
        import aiohttp
        from config.settings import settings
    except Exception:  # noqa: BLE001
        return None

    if getattr(settings, "demo_mode", False):
        return None

    token = settings.vk_api_token
    if not token:
        return None

    # users.get принимает user_ids — там и screen_name и числовой id работают
    fields = "photo_200,status,about,counters,city,verified"
    params: Dict[str, Any] = {
        "user_ids":     handle,
        "fields":       fields,
        "access_token": token,
        "v":            "5.199",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.vk.com/method/users.get",
                params=params, timeout=10,
            ) as resp:
                data = await resp.json()
    except Exception:  # noqa: BLE001
        logger.debug("VK users.get failed for %s", handle, exc_info=False)
        return None

    if "error" in data:
        return None
    items = data.get("response") or []
    if not items:
        return None
    p = items[0]
    counters = p.get("counters") or {}
    city = (p.get("city") or {}).get("title")
    return {
        "first_name":  p.get("first_name"),
        "last_name":   p.get("last_name"),
        "photo":       p.get("photo_200"),
        "status":      p.get("status"),
        "about":       p.get("about"),
        "city":        city,
        "followers":   counters.get("followers"),
        "friends":     counters.get("friends"),
        "verified":    bool(p.get("verified")),
    }
