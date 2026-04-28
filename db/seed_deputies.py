"""Seed the `deputies` table from `config/deputies.py`.

Run once on FastAPI startup, after `seed_cities()`. Idempotent:
`upsert_deputy()` does ON CONFLICT (city_id, external_id) DO UPDATE,
so правки в config/deputies.py применяются обычным редеплоем без
ручных миграций.

Возвращает dict {city_name: rows_written}, пустой если нет пула.
"""

from __future__ import annotations

import logging
from typing import Dict

from config.deputies import DEPUTIES_BY_CITY

from .deputy_queries import upsert_deputy
from .pool import get_pool
from .seed import city_id_by_name

logger = logging.getLogger(__name__)


async def seed_deputies() -> Dict[str, int]:
    """Upsert каждый депутат для каждого сконфигурированного города."""
    pool = get_pool()
    if pool is None:
        return {}

    written: Dict[str, int] = {}
    for city_name, roster in DEPUTIES_BY_CITY.items():
        if not roster:
            continue
        city_id = await city_id_by_name(city_name)
        if city_id is None:
            logger.warning(
                "seed_deputies: city %s not seeded yet — skipping %d deputies",
                city_name, len(roster),
            )
            continue
        ok = 0
        for cfg in roster:
            row_id = await upsert_deputy(city_id, dict(cfg))
            if row_id is not None:
                ok += 1
        written[city_name] = ok
        logger.info("seeded %d/%d deputies for %s", ok, len(roster), city_name)

    return written
