"""Async Postgres pool singleton.

`init_pool()` is called from FastAPI's startup event. If the DSN is
missing, unreachable or the driver isn't installed, we log a warning and
`get_pool()` returns None — downstream callers treat that as "no DB
available" and fall back to placeholder data instead of raising.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)

_pool = None  # type: ignore[var-annotated]


def _strip_driver(dsn: str) -> str:
    """asyncpg doesn't understand SQLAlchemy-style `postgresql+asyncpg://`.

    Downgrade any `+driver` suffix to the plain scheme that asyncpg
    accepts. Leave other URL parts alone.
    """
    scheme_sep = "://"
    idx = dsn.find(scheme_sep)
    if idx <= 0:
        return dsn
    scheme = dsn[:idx]
    rest = dsn[idx:]
    if "+" in scheme:
        scheme = scheme.split("+", 1)[0]
    return f"{scheme}{rest}"


async def init_pool(
    *,
    dsn: Optional[str] = None,
    min_size: int = 1,
    max_size: int = 5,
    connect_timeout: float = 5.0,
):
    """Create the global connection pool. Returns the pool or None."""
    global _pool
    if _pool is not None:
        return _pool

    raw_dsn = dsn if dsn is not None else settings.database_url
    if not raw_dsn:
        logger.info("DATABASE_URL not set — DB features disabled")
        return None

    try:
        import asyncpg  # type: ignore
    except ImportError:
        logger.warning("asyncpg not installed — DB features disabled")
        return None

    normalised = _strip_driver(raw_dsn)
    try:
        _pool = await asyncio.wait_for(
            asyncpg.create_pool(
                dsn=normalised,
                min_size=min_size,
                max_size=max_size,
                command_timeout=10.0,
            ),
            timeout=connect_timeout,
        )
        logger.info("DB pool ready (%s)", _host_from_dsn(normalised))
        return _pool
    except Exception:  # noqa: BLE001 — broad because asyncpg raises many types
        logger.exception("Failed to initialise DB pool — continuing without DB")
        _pool = None
        return None


def get_pool():
    """Return the live pool or None if DB is disabled / unavailable."""
    return _pool


async def close_pool() -> None:
    """Close the global pool (idempotent)."""
    global _pool
    if _pool is None:
        return
    try:
        await _pool.close()
    except Exception:  # noqa: BLE001
        logger.warning("error while closing DB pool", exc_info=False)
    finally:
        _pool = None


def _host_from_dsn(dsn: str) -> str:
    """Best-effort log-friendly host extraction (no credentials)."""
    try:
        # postgresql://user:pass@host:port/db -> host:port/db
        after_scheme = dsn.split("://", 1)[1]
        after_at = after_scheme.split("@", 1)[-1]
        return after_at
    except (IndexError, ValueError):
        return "<unknown>"
