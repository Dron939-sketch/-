"""Citizen appeals collector.

The real Gosuslugi endpoint is not publicly documented; this collector is a
stub with a clearly-marked contract so the real integration can land once
we receive credentials from the administration (TZ 6.2, P2).

For now it returns an empty list unless pointed at a local JSON fixture via
`GOSUSLUGI_FIXTURE_PATH` — useful for tests and demos.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

from .base import BaseCollector, CollectedItem

logger = logging.getLogger(__name__)


class AppealsCollector(BaseCollector):
    def __init__(self, city_name: str, fixture_path: Optional[str] = None):
        super().__init__(city_name)
        self.fixture_path = fixture_path or os.getenv("GOSUSLUGI_FIXTURE_PATH")

    async def collect(self, since: Optional[datetime] = None) -> List[CollectedItem]:
        if not self.fixture_path:
            logger.info("AppealsCollector: no Gosuslugi credentials / fixture — skipping")
            return []
        try:
            with open(self.fixture_path, "r", encoding="utf-8") as fh:
                records = json.load(fh)
        except OSError:
            logger.exception("Cannot read appeals fixture %s", self.fixture_path)
            return []

        out: List[CollectedItem] = []
        for rec in records:
            published_raw = rec.get("published_at")
            published = (
                datetime.fromisoformat(published_raw)
                if published_raw
                else datetime.now(tz=timezone.utc)
            )
            if since and published < since:
                continue
            out.append(
                CollectedItem(
                    source_kind="gosuslugi",
                    source_handle=rec.get("handle", self.city_name),
                    title=rec.get("title", "Обращение гражданина"),
                    content=rec.get("content", ""),
                    published_at=published,
                    url=rec.get("url"),
                    author=rec.get("author"),
                    category=rec.get("category", "appeals"),
                )
            )
        return out
