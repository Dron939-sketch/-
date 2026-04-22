"""Database layer.

Thin asyncpg pool + typed query helpers. Initialised once on FastAPI
startup via `init_pool()`, closed on shutdown. If DATABASE_URL is
missing or the DB is unreachable, `get_pool()` returns None and all
higher-level helpers degrade to no-ops so the web tier keeps serving
placeholder data.
"""

from .pool import get_pool, init_pool, close_pool

__all__ = ["get_pool", "init_pool", "close_pool"]
