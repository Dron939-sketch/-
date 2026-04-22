"""Seed the `cities` table from `config/cities.py`.

Run once on FastAPI startup. Idempotent: ON CONFLICT (name) updates the
row so fixing a typo in config/cities.py is a redeploy away.
"""

from __future__ import annotations

import logging
from typing import Dict, Mapping

from config.cities import CITIES

from .pool import get_pool

logger = logging.getLogger(__name__)


_UPSERT_SQL = """
INSERT INTO cities
    (slug, name, region, population, lat, lon, timezone, emoji,
     accent_color, is_pilot)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
ON CONFLICT (name) DO UPDATE SET
    slug         = EXCLUDED.slug,
    region       = EXCLUDED.region,
    population   = EXCLUDED.population,
    lat          = EXCLUDED.lat,
    lon          = EXCLUDED.lon,
    timezone     = EXCLUDED.timezone,
    emoji        = EXCLUDED.emoji,
    accent_color = EXCLUDED.accent_color,
    is_pilot     = EXCLUDED.is_pilot
RETURNING id, name
"""


async def seed_cities() -> Dict[str, int]:
    """Upsert every city in CITIES. Returns {name: id}. Empty if no pool."""
    pool = get_pool()
    if pool is None:
        return {}

    by_name: Dict[str, int] = {}
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                for cfg in CITIES.values():
                    row = await conn.fetchrow(
                        _UPSERT_SQL,
                        cfg.get("slug"),
                        cfg["name"],
                        cfg["region"],
                        cfg.get("population"),
                        cfg["coordinates"]["lat"],
                        cfg["coordinates"]["lon"],
                        cfg.get("timezone", "Europe/Moscow"),
                        cfg.get("emoji"),
                        cfg.get("accent_color"),
                        bool(cfg.get("is_pilot", False)),
                    )
                    if row is not None:
                        by_name[row["name"]] = row["id"]
    except Exception:  # noqa: BLE001
        logger.exception("city seed failed — continuing without DB seeding")
        return {}

    logger.info("seeded %d cities into DB", len(by_name))
    return by_name


async def city_id_by_name(name: str) -> int | None:
    """Look up a city row id, or None if pool missing / row absent."""
    pool = get_pool()
    if pool is None:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM cities WHERE name = $1", name
            )
            return row["id"] if row else None
    except Exception:  # noqa: BLE001
        logger.warning("city_id_by_name failed for %s", name, exc_info=False)
        return None


async def city_id_by_slug(slug: str) -> int | None:
    pool = get_pool()
    if pool is None:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM cities WHERE slug = $1", slug
            )
            return row["id"] if row else None
    except Exception:  # noqa: BLE001
        return None


async def run_migrations(sql_path: str) -> bool:
    """Apply init_db.sql against the current pool.

    Returns True if the script ran without error, False otherwise.
    Intended for one-shot bootstrap on a fresh DB; safe to call repeatedly
    because every CREATE is guarded with IF NOT EXISTS.
    """
    pool = get_pool()
    if pool is None:
        return False
    try:
        with open(sql_path, "r", encoding="utf-8") as fh:
            sql = fh.read()
        async with pool.acquire() as conn:
            await conn.execute(sql)
        logger.info("migrations applied from %s", sql_path)
        return True
    except FileNotFoundError:
        logger.warning("migrations file %s not found", sql_path)
        return False
    except Exception:  # noqa: BLE001
        logger.exception("migration failed — continuing")
        return False
