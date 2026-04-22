"""News RSS collector (Google News / other feeds).

Parses the public RSS feeds configured in `config/sources.py`. Works
without any API key and has no rate-limit concerns beyond basic HTTP
politeness.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional

import aiohttp

from config.settings import settings
from config.sources import get_sources_for_city, Source

from .base import BaseCollector, CollectedItem

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_FETCH_TIMEOUT = aiohttp.ClientTimeout(total=8, connect=5)


def _strip_tags(html: str) -> str:
    return _TAG_RE.sub("", html or "").strip()


class NewsCollector(BaseCollector):
    async def collect(self, since: Optional[datetime] = None) -> List[CollectedItem]:
        sources = get_sources_for_city(self.city_name).news_rss
        if not sources:
            return []
        since = since or (
            datetime.now(tz=timezone.utc)
            - timedelta(hours=settings.news_lookback_hours)
        )
        items: List[CollectedItem] = []
        async with aiohttp.ClientSession(timeout=_FETCH_TIMEOUT) as session:
            for src in sources:
                try:
                    items.extend(await self._fetch(session, src, since))
                except Exception:  # noqa: BLE001
                    logger.warning("RSS fetch failed for %s", src.handle, exc_info=False)
        return items

    async def _fetch(
        self,
        session: aiohttp.ClientSession,
        src: Source,
        since: datetime,
    ) -> List[CollectedItem]:
        # Defer feedparser import so it's optional in CI.
        try:
            import feedparser  # type: ignore
        except ImportError:
            logger.warning("feedparser not installed — NewsCollector disabled")
            return []
        async with session.get(src.handle) as response:
            response.raise_for_status()
            body = await response.read()
        parsed = feedparser.parse(body)
        out: List[CollectedItem] = []
        for entry in parsed.entries:
            published = self._parse_date(entry)
            if published < since:
                continue
            title = (entry.get("title") or "").strip()
            content = _strip_tags(entry.get("summary") or entry.get("description") or "")
            if not (title or content):
                continue
            out.append(
                CollectedItem(
                    source_kind="news_rss",
                    source_handle=src.handle,
                    title=title,
                    content=content or title,
                    published_at=published,
                    url=entry.get("link"),
                    author=entry.get("author"),
                    category=src.category,
                )
            )
        return out

    @staticmethod
    def _parse_date(entry) -> datetime:
        for key in ("published", "updated", "pubDate"):
            raw = entry.get(key)
            if not raw:
                continue
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (TypeError, ValueError):
                continue
        return datetime.now(tz=timezone.utc)
