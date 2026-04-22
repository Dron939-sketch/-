"""FastAPI application factory.

Startup order:
1. Initialise asyncpg pool from DATABASE_URL (optional — no-op if missing).
2. Apply migrations/init_db.sql (idempotent; safe on plain Postgres).
3. Seed the `cities` table from config/cities.py.
4. Start background loops (`tasks.scheduler.start`) for periodic
   collection + weather refresh.

Every step is fail-safe: if the DB is unreachable, the web tier boots
anyway and endpoints fall back to placeholder data.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from db import init_pool, close_pool
from db.seed import run_migrations, seed_cities

from . import tasks_wiring  # noqa: F401  (imports registered on app bind)
from .routes import router

logger = logging.getLogger(__name__)

_MIGRATION_PATH = Path(__file__).resolve().parent.parent / "migrations" / "init_db.sql"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Городской Разум API",
        version="0.3.0",
        description=(
            "Прогнозное управление городом: сбор новостей, погода, метрики, "
            "повестка, roadmap."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.on_event("startup")
    async def _on_startup() -> None:
        from tasks import scheduler  # local import to avoid cycles

        pool = await init_pool()
        if pool is not None:
            await run_migrations(str(_MIGRATION_PATH))
            await seed_cities()
        scheduler.start()

    @app.on_event("shutdown")
    async def _on_shutdown() -> None:
        from tasks import scheduler

        await scheduler.stop()
        await close_pool()

    dashboard_dir = Path(__file__).resolve().parent.parent / "dashboard"
    if dashboard_dir.exists():
        app.mount("/", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")
    else:
        logger.warning("Dashboard directory %s missing — static UI not mounted", dashboard_dir)
    return app


app = create_app()
