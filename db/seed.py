"""Seed the `cities` table from `config/cities.py`.

Run once on FastAPI startup. Idempotent: ON CONFLICT (name) updates the
row so fixing a typo in config/cities.py is a redeploy away.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Tuple

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


_SEGMENT_MARKER = re.compile(r"^\s*--\s*@SEGMENT\s+(\S+)\s*$", re.MULTILINE)


def _split_segments(sql: str) -> List[Tuple[str, str]]:
    """Split SQL on `-- @SEGMENT <name>` marker lines.

    Returns a list of `(segment_name, sql_body)` pairs in order. A file
    without any marker is returned as a single `("default", sql)` tuple
    so legacy scripts keep working.
    """
    matches = list(_SEGMENT_MARKER.finditer(sql))
    if not matches:
        return [("default", sql)]

    segments: List[Tuple[str, str]] = []
    # Everything before the first marker is the implicit "preamble" —
    # run it first so top-of-file comments aren't lost.
    preamble = sql[: matches[0].start()].strip()
    if preamble:
        segments.append(("preamble", preamble))

    for i, match in enumerate(matches):
        name = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(sql)
        body = sql[start:end].strip()
        if body:
            segments.append((name, body))
    return segments


async def run_migrations(sql_path: str) -> bool:
    """Apply init_db.sql segment-by-segment.

    Each `-- @SEGMENT <name>` block runs in its own transaction. When a
    segment fails we log the error and move on to the next one — this
    keeps non-critical pieces (TimescaleDB hypertables, retention
    policies, pg_trgm indexes) from taking out the whole migration on
    managed databases with limited extensions.

    Returns True when every segment succeeded, False if any failed or
    the pool wasn't available.
    """
    pool = get_pool()
    if pool is None:
        return False
    try:
        with open(sql_path, "r", encoding="utf-8") as fh:
            sql = fh.read()
    except FileNotFoundError:
        logger.warning("migrations file %s not found", sql_path)
        return False

    segments = _split_segments(sql)
    failed: List[str] = []
    for name, body in segments:
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(body)
            logger.info("migration segment '%s' applied", name)
        except Exception as exc:  # noqa: BLE001
            failed.append(name)
            logger.warning(
                "migration segment '%s' failed (%s) — continuing",
                name, exc,
            )
    if failed:
        logger.warning("migration segments failed: %s", ", ".join(failed))
        return False
    logger.info("all %d migration segments applied", len(segments))
    return True
