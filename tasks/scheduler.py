"""In-process asyncio scheduler.

Three loops:
- `collection_loop` every `COLLECTION_INTERVAL_MIN` minutes: run
  collectors, DeepSeek-enrich, upsert into `news`.
- `weather_loop` every hour: fetch current weather and upsert `weather`.
- `snapshot_loop` every hour: aggregate the last 24h of news into a
  `metrics` row AND re-run the confinement loop detector, writing the
  top loops to the `loops` table.

Every iteration is wrapped in a generous try/except — a failure for
one city never stops the others, a failure one iteration never stops
the loop.

Note on disabled collectors + AI replacement
--------------------------------------------
Telegram and VK collectors are intentionally NOT plugged in here — the
VK token returns `error_code=5` (invalid) and the Telegram client would
warn on every cycle without credentials.

Instead, once the real news + appeals pass enrichment, we run an
`AIPulseCollector` that asks DeepSeek to synthesize plausible local
social-pulse posts from the same context. Those items are tagged
`source_kind="ai_pulse"` + `ai_synth=True` so the UI can label them
honestly. Flip the old TG/VK collectors back on by restoring the lines
marked `# --- re-enable ...` below.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from typing import List, Optional

from ai.enricher import NewsEnricher
from analytics.loops import analyze_loops
from collectors import (
    AIPulseCollector,
    AppealsCollector,
    NewsCollector,
)
from collectors.base import CollectedItem
from config.cities import CITIES
from config.settings import settings
from db import get_pool
from db.loops_queries import replace_loops
from db.queries import (
    insert_metrics,
    latest_metrics,
    news_window,
    upsert_news_batch,
    upsert_weather,
)
from db.seed import city_id_by_name
from metrics.openweather import fetch_current
from metrics.snapshot import snapshot_from_news
from ops.status import Heartbeat

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
        # --- re-enable when valid TELEGRAM_API_ID/HASH arrive:
        # TelegramCollector(city_name),
        # --- re-enable when VK access token is valid:
        # VKCollector(city_name),
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

    # AI social-pulse: synthesize 5 plausible local voice posts from the
    # enriched reference. Reuses the NewsEnricher's DeepSeek client, so no
    # extra config. Fail-safe when DeepSeek is disabled or times out.
    if items and enricher.enabled:
        pulse = AIPulseCollector(
            city_name,
            reference_items=items,
            client=enricher.client,
        )
        try:
            synth = await asyncio.wait_for(pulse.collect(), timeout=30)
            items.extend(synth)
            if synth:
                logger.info("ai_pulse %s: synthesized %d posts", city_name, len(synth))
        except asyncio.TimeoutError:
            logger.warning("ai_pulse timed out for %s", city_name)
        except Exception:  # noqa: BLE001
            logger.warning("ai_pulse failed for %s", city_name, exc_info=False)
        finally:
            await pulse.close()

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


async def snapshot_metrics(city_name: str) -> bool:
    """Aggregate the last 24h of news into a `metrics` row."""
    pool = get_pool()
    if pool is None:
        return False
    city_id = await city_id_by_name(city_name)
    if city_id is None:
        return False
    items = await news_window(city_id, hours=24)
    if not items:
        logger.debug("snapshot_metrics %s: no news in last 24h — skipping", city_name)
        return False
    values = snapshot_from_news(items)
    ok = await insert_metrics(city_id, values)
    if ok:
        logger.info(
            "snapshot_metrics %s: %s",
            city_name,
            ", ".join(f"{k}={v}" for k, v in values.items()),
        )
    return ok


async def analyze_loops_for_city(city_name: str) -> int:
    pool = get_pool()
    if pool is None:
        return 0
    city_id = await city_id_by_name(city_name)
    if city_id is None:
        return 0
    metric_row = await latest_metrics(city_id)
    if metric_row is None:
        logger.debug("analyze_loops %s: no metrics yet", city_name)
        return 0

    snapshot = {
        "sb": metric_row.get("sb"),
        "tf": metric_row.get("tf"),
        "ub": metric_row.get("ub"),
        "chv": metric_row.get("chv"),
    }
    # city_id is keyword-only on analyze_loops — wrap in a partial so the
    # executor call doesn't pass it positionally (raises TypeError).
    loops = await asyncio.get_running_loop().run_in_executor(
        None,
        functools.partial(analyze_loops, city_name, snapshot, city_id=city_id),
    )
    if not loops:
        return 0

    written = await replace_loops(city_id, loops)
    if written:
        logger.info(
            "analyze_loops %s: %d loops, top='%s' (strength=%.2f)",
            city_name, written, loops[0]["name"], loops[0]["strength"],
        )
    return written


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
        Heartbeat.tick("collection")
        await asyncio.sleep(interval_s)


async def _weather_loop(interval_s: int) -> None:
    await asyncio.sleep(5)
    while True:
        for city_name in CITIES:
            try:
                await refresh_weather(city_name)
            except Exception:  # noqa: BLE001
                logger.exception("weather_loop failed for %s", city_name)
        Heartbeat.tick("weather")
        await asyncio.sleep(interval_s)


async def _snapshot_loop(interval_s: int) -> None:
    await asyncio.sleep(120)
    while True:
        for city_name in CITIES:
            try:
                wrote = await snapshot_metrics(city_name)
                if wrote:
                    await analyze_loops_for_city(city_name)
            except Exception:  # noqa: BLE001
                logger.exception("snapshot_loop failed for %s", city_name)
        Heartbeat.tick("snapshot")
        await asyncio.sleep(interval_s)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start() -> None:
    if _tasks:
        return
    if get_pool() is None:
        logger.info("scheduler: no DB pool, not starting background loops")
        return
    if not settings.openweather_api_key:
        logger.info("scheduler: weather loop disabled (no OPENWEATHER_API_KEY)")

    collection_s = max(300, settings.collection_interval_minutes * 60)
    weather_s = 3600
    snapshot_s = 3600

    _tasks.append(asyncio.create_task(_collection_loop(collection_s), name="collection_loop"))
    if settings.openweather_api_key:
        _tasks.append(asyncio.create_task(_weather_loop(weather_s), name="weather_loop"))
    _tasks.append(asyncio.create_task(_snapshot_loop(snapshot_s), name="snapshot_loop"))
    logger.info(
        "scheduler started: collection every %ds, weather every %ds, snapshot every %ds",
        collection_s, weather_s, snapshot_s,
    )


async def stop() -> None:
    while _tasks:
        t = _tasks.pop()
        t.cancel()
        try:
            await t
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
