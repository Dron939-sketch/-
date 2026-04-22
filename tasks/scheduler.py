"""In-process asyncio scheduler.

Two loops:
- `collection_loop` every `COLLECTION_INTERVAL_MIN` minutes: for each
  city run the collectors, enrich via DeepSeek, upsert into `news`.
- `weather_loop` every hour: fetch current weather for each city and
  upsert into `weather`.

Every iteration is wrapped in a generous try/except — a failure for
one city never stops the others, and a failure one iteration never
stops the loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from ai.enricher import NewsEnricher
from collectors import (
    AppealsCollector,
    NewsCollector,
    TelegramCollector,
    VKCollector,
)
from collectors.base import CollectedItem
from config.cities import CITIES
from config.settings import settings
from db import get_pool
from db.queries import upsert_news_batch, upsert_weather
from db.seed import city_id_by_name
from metrics.openweather import fetch_current

logger = logging.getLogger(__name__)

_tasks: List[asyncio.Task] = []


# ---------------------------------------------------------------------------
# One-shot jobs (exposed for tests / manual triggers)
# ---------------------------------------------------------------------------

async def collect_city(city_name: str, enricher: Optional[NewsEnricher] = None) -> int:
    """Collect + enrich + persist news for a single city. Returns rows written."""
    pool = get_pool()
    if pool is None:
        return 0
    city_id = await city_id_by_name(city_name)
    if city_id is None:
        logger.warning("collect_city: city %s not seeded yet", city_name)
        return 0

    collectors = [
        TelegramCollector(city_name),
        VKCollector(city_name),
        NewsCollector(city_name),
        AppealsCollector(city_name),
    ]
    items: List[CollectedItem] = []
    for coll in collectors:
        try:
            items.extend(await asyncio.wait_for(coll.collect(), timeout=15))
        except asyncio.TimeoutError:
            logger.warning("collector %s timed out", type(coll).__name__)
        except Exception:  # noqa: BLE001
            logger.warning("collector %s failed", type(coll).__name__, exc_info=False)
        finally:
            await coll.close()

    if not items:
        return 0

    enricher = enricher or NewsEnricher()
    if enricher.enabled:
        try:
            await asyncio.wait_for(enricher.enrich(items), timeout=40)
        except asyncio.TimeoutError:
            logger.warning("enricher timed out for %s — writing without enrichment", city_name)
        except Exception:  # noqa: BLE001
            logger.warning("enricher failed for %s", city_name, exc_info=False)

    written = await upsert_news_batch(city_id, items)
    logger.info("collect_city %s: collected=%d written=%d", city_name, len(items), written)
    return written


async def refresh_weather(city_name: str) -> bool:
    """Fetch current weather and persist it. Returns True on success."""
    cfg = CITIES.get(city_name)
    if cfg is None:
        return False
    city_id = await city_id_by_name(city_name)
    if city_id is None:
        return False
    snapshot = await fetch_current(cfg["coordinates"]["lat"], cfg["coordinates"]["lon"])
    if snapshot is None:
        return False
    return await upsert_weather(city_id, snapshot)


# ---------------------------------------------------------------------------
# Loops
# ---------------------------------------------------------------------------

async def _collection_loop(interval_s: int) -> None:
    # Give the web tier a moment to finish startup before the first cycle.
    await asyncio.sleep(15)
    enricher = NewsEnricher()
    while True:
        for city_name in CITIES:
            try:
                await collect_city(city_name, enricher=enricher)
            except Exception:  # noqa: BLE001
                logger.exception("collection_loop failed for %s", city_name)
        await asyncio.sleep(interval_s)


async def _weather_loop(interval_s: int) -> None:
    await asyncio.sleep(5)
    while True:
        for city_name in CITIES:
            try:
                await refresh_weather(city_name)
            except Exception:  # noqa: BLE001
                logger.exception("weather_loop failed for %s", city_name)
        await asyncio.sleep(interval_s)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start() -> None:
    """Kick off both background loops. Safe to call once at startup.

    Does nothing if no DB pool is available — without a pool we have
    nowhere to write, so running the loops is just wasted work.
    """
    if _tasks:
        return
    if get_pool() is None:
        logger.info("scheduler: no DB pool, not starting background loops")
        return
    if not settings.openweather_api_key:
        logger.info("scheduler: weather loop disabled (no OPENWEATHER_API_KEY)")

    collection_s = max(300, settings.collection_interval_minutes * 60)
    weather_s = 3600

    _tasks.append(asyncio.create_task(_collection_loop(collection_s), name="collection_loop"))
    if settings.openweather_api_key:
        _tasks.append(asyncio.create_task(_weather_loop(weather_s), name="weather_loop"))
    logger.info(
        "scheduler started: collection every %ds, weather every %ds",
        collection_s, weather_s,
    )


async def stop() -> None:
    """Cancel all running loops. Safe to call multiple times."""
    while _tasks:
        t = _tasks.pop()
        t.cancel()
        try:
            await t
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
