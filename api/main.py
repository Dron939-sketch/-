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
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from db import init_pool, close_pool
from db.seed import run_migrations, seed_cities

from .admin_stats_routes import router as admin_stats_router
from .auth_routes import router as auth_router
from .routes import router
from .usage_middleware import UsageLoggingMiddleware

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
    # Usage-analytics middleware runs AFTER endpoints so it can capture
    # response status + elapsed time. Registered here so it wraps every
    # route the app serves (including auth). Skips /health prefixes inside.
    app.add_middleware(UsageLoggingMiddleware)

    app.include_router(auth_router)
    app.include_router(admin_stats_router)
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

    # /favicon.ico → dashboard/favicon.svg (browsers запрашивают .ico по умолчанию).
    # Mount route explicitly так что static files fallback не перехватит его
    # с 404 до того, как достигнет ICO-файла (которого у нас нет).
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        svg = dashboard_dir / "favicon.svg"
        if svg.exists():
            return FileResponse(str(svg), media_type="image/svg+xml")
        return Response(status_code=204)

    if dashboard_dir.exists():
        app.mount("/", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")
    else:
        logger.warning("Dashboard directory %s missing — static UI not mounted", dashboard_dir)
    return app


app = create_app()
