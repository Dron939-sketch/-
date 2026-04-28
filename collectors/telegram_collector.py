"""Telegram collector built on Telethon.

If the Telegram API credentials are not configured the collector runs in a
safe "stub" mode and returns an empty list — this is useful for local dev
and CI. Production needs `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` set in
`.env`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from config.settings import settings
from config.sources import get_sources_for_city, Source

from .base import BaseCollector, CollectedItem

logger = logging.getLogger(__name__)


class TelegramCollector(BaseCollector):
    def __init__(self, city_name: str, limit_per_channel: int = 25):
        super().__init__(city_name)
        self.limit_per_channel = limit_per_channel
        self._client = None  # lazily initialised Telethon client

    async def _ensure_client(self):
        if self._client is not None:
            return self._client
        if not (settings.telegram_api_id and settings.telegram_api_hash):
            logger.warning(
                "Telegram credentials not set — TelegramCollector running in stub mode"
            )
            return None
        try:
            from telethon import TelegramClient  # type: ignore
        except ImportError:
            logger.warning("telethon is not installed — TelegramCollector disabled")
            return None
        client = TelegramClient(
            settings.telegram_session,
            int(settings.telegram_api_id),
            settings.telegram_api_hash,
        )
        await client.start()
        self._client = client
        return client

    async def collect(self, since: Optional[datetime] = None) -> List[CollectedItem]:
        sources = get_sources_for_city(self.city_name).telegram
        if not sources:
            return []
        client = await self._ensure_client()
        if client is None:
            return []
        since = since or (datetime.now(tz=timezone.utc) - timedelta(hours=settings.news_lookback_hours))
        items: List[CollectedItem] = []
        for src in sources:
            try:
                items.extend(await self._collect_channel(client, src, since))
            except Exception:  # noqa: BLE001 — keep crawling other channels
                logger.exception("Telegram collection failed for %s", src.handle)
        return items

    async def _collect_channel(
        self, client, src: Source, since: datetime
    ) -> List[CollectedItem]:
        items: List[CollectedItem] = []
        async for msg in client.iter_messages(src.handle, limit=self.limit_per_channel):
            if msg.date and msg.date < since:
                break
            text = (msg.message or "").strip()
            if not text:
                continue
            title = text.splitlines()[0][:160]
            items.append(
                CollectedItem(
                    source_kind="telegram",
                    source_handle=src.handle,
                    title=title,
                    content=text,
                    published_at=msg.date or self._now(),
                    url=f"https://t.me/{src.handle}/{msg.id}",
                    category=src.category,
                    raw={"message_id": msg.id, "views": getattr(msg, "views", None)},
                )
            )
        return items

    async def close(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None
