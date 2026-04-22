"""VK public wall collector using the public `wall.get` method.

The collector is best-effort: it respects the official rate limit of ~3
RPS by sleeping between requests and tolerates transient errors without
failing the whole run. Without `VK_API_TOKEN` set it returns an empty list.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import aiohttp

from config.settings import settings
from config.sources import get_sources_for_city, Source

from .base import BaseCollector, CollectedItem

logger = logging.getLogger(__name__)

_VK_API_VERSION = "5.199"
_VK_API_URL = "https://api.vk.com/method/wall.get"


class VKCollector(BaseCollector):
    def __init__(self, city_name: str, count: int = 50):
        super().__init__(city_name)
        self.count = count

    async def collect(self, since: Optional[datetime] = None) -> List[CollectedItem]:
        token = settings.vk_api_token
        if not token:
            logger.warning("VK_API_TOKEN not set — VKCollector running in stub mode")
            return []
        sources = get_sources_for_city(self.city_name).vk
        if not sources:
            return []
        since_ts = int(
            (
                since
                or (
                    datetime.now(tz=timezone.utc)
                    - timedelta(hours=settings.news_lookback_hours)
                )
            ).timestamp()
        )
        items: List[CollectedItem] = []
        async with aiohttp.ClientSession() as session:
            for src in sources:
                try:
                    items.extend(await self._fetch(session, src, token, since_ts))
                except Exception:  # noqa: BLE001
                    logger.exception("VK collection failed for %s", src.handle)
                await asyncio.sleep(0.35)  # ~3 RPS
        return items

    async def _fetch(
        self,
        session: aiohttp.ClientSession,
        src: Source,
        token: str,
        since_ts: int,
    ) -> List[CollectedItem]:
        params = {
            "domain": src.handle,
            "count": self.count,
            "access_token": token,
            "v": _VK_API_VERSION,
        }
        async with session.get(_VK_API_URL, params=params, timeout=20) as response:
            response.raise_for_status()
            payload: Dict[str, Any] = await response.json()
        if "error" in payload:
            logger.warning("VK API error for %s: %s", src.handle, payload["error"])
            return []
        posts = payload.get("response", {}).get("items", [])
        out: List[CollectedItem] = []
        for post in posts:
            ts = int(post.get("date", 0))
            if ts < since_ts:
                continue
            text = (post.get("text") or "").strip()
            if not text:
                continue
            published = datetime.fromtimestamp(ts, tz=timezone.utc)
            post_id = post.get("id")
            owner_id = post.get("owner_id")
            out.append(
                CollectedItem(
                    source_kind="vk",
                    source_handle=src.handle,
                    title=text.splitlines()[0][:160],
                    content=text,
                    published_at=published,
                    url=f"https://vk.com/wall{owner_id}_{post_id}",
                    category=src.category,
                    raw={
                        "likes": post.get("likes", {}).get("count"),
                        "reposts": post.get("reposts", {}).get("count"),
                        "views": post.get("views", {}).get("count"),
                    },
                )
            )
        return out
