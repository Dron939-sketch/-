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
