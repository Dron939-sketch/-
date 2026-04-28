"""VK groups discovery via groups.search API.

Helper for admins to find all VK communities matching a query (e.g.
"Коломна", "ЖКХ Коломна", "ДТП Коломна") so they can pick relevant
ones to register in `config/sources.py` instead of guessing handles.

Returns enriched info per group: screen_name (the handle to use in
config), name, member count, description first 200 chars, group type
(group / event / page), and a direct vk.com URL for human review.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import aiohttp

from config.settings import settings

logger = logging.getLogger(__name__)

_VK_API_VERSION = "5.199"
_VK_SEARCH_URL = "https://api.vk.com/method/groups.search"


async def search_groups(query: str, *, limit: int = 50,
                        sort: int = 6) -> List[Dict[str, Any]]:
    """Search VK groups matching `query`.

    sort modes:
        0 — default (relevance)
        1 — growth speed
        2 — daily activity
        3 — visits/day
        6 — members count desc (наш default — крупные сообщества важнее)

    Returns a list of dicts ready for human review, sorted as the API
    returned. Empty list when token missing or API error.
    """
    token = settings.vk_api_token
    if not token:
        return []
    params = {
        "q": query,
        "count": max(1, min(1000, int(limit))),
        "sort": int(sort),
        "access_token": token,
        "v": _VK_API_VERSION,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(_VK_SEARCH_URL, params=params, timeout=20) as resp:
                data = await resp.json()
    except Exception:  # noqa: BLE001
        logger.warning("VK groups.search failed for %r", query, exc_info=False)
        return []

    if "error" in data:
        logger.warning("VK groups.search error for %r: %s", query, data["error"])
        return []

    items = data.get("response", {}).get("items", [])
    out: List[Dict[str, Any]] = []
    for g in items:
        screen = g.get("screen_name")
        if not screen:
            continue
        out.append({
            "screen_name": screen,
            "name": g.get("name", ""),
            "members_count": g.get("members_count"),
            "description": (g.get("description") or "")[:200],
            "type": g.get("type", "group"),
            "is_closed": g.get("is_closed", 0),
            "url": f"https://vk.com/{screen}",
            "config_line": (
                f'Source("vk", "{(g.get("name") or "").replace(chr(34), chr(39))[:60]}", '
                f'"{screen}", "news", "P2"),'
            ),
        })
    return out


async def search_multi(queries: List[str], *, per_query: int = 30) -> List[Dict[str, Any]]:
    """Run multiple search queries and dedupe by screen_name.

    Useful when a city has several keyword angles ("Коломна", "Kolomna",
    "Коломенский район") — gathers everything in one shot for review.
    """
    seen: Dict[str, Dict[str, Any]] = {}
    for q in queries:
        for g in await search_groups(q, limit=per_query):
            screen = g["screen_name"]
            if screen in seen:
                # keep the one with higher member count
                if (g.get("members_count") or 0) > (seen[screen].get("members_count") or 0):
                    seen[screen] = g
            else:
                seen[screen] = g
    return sorted(
        seen.values(),
        key=lambda g: (g.get("members_count") or 0),
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Users search (через users.search)
# ---------------------------------------------------------------------------

_VK_USERS_SEARCH_URL = "https://api.vk.com/method/users.search"


async def search_users(
    query: str, *,
    city_id: int | None = None,   # VK city id (Коломна = 1188)
    age_from: int | None = None,
    age_to: int | None = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Поиск людей в VK по имени/фамилии. Используется Джарвисом для
    запросов вида «найди в VK Иванова из Коломны».

    Возвращает список dict'ов с id, name, photo, city, has_profile_url.
    На отсутствующий токен / ошибку API → [].
    """
    token = settings.vk_api_token
    if not token or not query or len(query.strip()) < 3:
        return []
    params: Dict[str, Any] = {
        "q": query.strip(),
        "count": max(1, min(50, int(limit))),
        "fields": "city,photo_100,domain,bdate",
        "access_token": token,
        "v": _VK_API_VERSION,
    }
    if city_id is not None:
        params["city"] = int(city_id)
    if age_from is not None:
        params["age_from"] = int(age_from)
    if age_to is not None:
        params["age_to"] = int(age_to)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(_VK_USERS_SEARCH_URL, params=params, timeout=20) as resp:
                data = await resp.json()
    except Exception:  # noqa: BLE001
        logger.warning("VK users.search failed for %r", query, exc_info=False)
        return []
    if "error" in data:
        logger.warning("VK users.search error for %r: %s", query, data["error"])
        return []

    items = data.get("response", {}).get("items", [])
    out: List[Dict[str, Any]] = []
    for u in items:
        uid = u.get("id")
        if not uid:
            continue
        first = (u.get("first_name") or "").strip()
        last = (u.get("last_name") or "").strip()
        name = (first + " " + last).strip() or "—"
        domain = u.get("domain") or f"id{uid}"
        out.append({
            "id":     int(uid),
            "name":   name,
            "city":   (u.get("city") or {}).get("title") if isinstance(u.get("city"), dict) else None,
            "bdate":  u.get("bdate"),
            "domain": domain,
            "photo":  u.get("photo_100"),
            "url":    f"https://vk.com/{domain}",
        })
    return out


# ---------------------------------------------------------------------------
# News search (через newsfeed.search) — поиск постов по запросу
# ---------------------------------------------------------------------------

_VK_NEWSFEED_SEARCH_URL = "https://api.vk.com/method/newsfeed.search"


async def search_news(
    query: str, *,
    count: int = 10,
) -> List[Dict[str, Any]]:
    """Поиск свежих постов VK по запросу. Используется Джарвисом для
    «что в VK пишут про X». Возвращает топ-N постов с короткими
    выжимками + ссылкой."""
    token = settings.vk_api_token
    if not token or not query or len(query.strip()) < 3:
        return []
    params = {
        "q": query.strip(),
        "count": max(1, min(50, int(count))),
        "access_token": token,
        "v": _VK_API_VERSION,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(_VK_NEWSFEED_SEARCH_URL, params=params, timeout=20) as resp:
                data = await resp.json()
    except Exception:  # noqa: BLE001
        logger.warning("VK newsfeed.search failed for %r", query, exc_info=False)
        return []
    if "error" in data:
        logger.warning("VK newsfeed.search error for %r: %s", query, data["error"])
        return []

    items = data.get("response", {}).get("items", [])
    out: List[Dict[str, Any]] = []
    for p in items:
        text = (p.get("text") or "").strip()
        if not text:
            continue
        owner_id = p.get("owner_id") or p.get("from_id")
        post_id = p.get("id") or p.get("post_id")
        url = (
            f"https://vk.com/wall{owner_id}_{post_id}"
            if owner_id and post_id else None
        )
        out.append({
            "text":    text[:240],
            "likes":   (p.get("likes") or {}).get("count"),
            "reposts": (p.get("reposts") or {}).get("count"),
            "views":   (p.get("views") or {}).get("count"),
            "date":    p.get("date"),
            "url":     url,
        })
    return out
