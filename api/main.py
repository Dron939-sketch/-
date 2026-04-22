"""FastAPI application factory.

The dashboard is mounted at `/` as a static bundle so a single container
ships both the API and the UI. For development use `uvicorn api.main:app`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.settings import settings

from .routes import router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="CityMind API",
        version="0.1.0",
        description="AI-ассистент мэра Коломны: сбор новостей, метрики, повестка, roadmap.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    dashboard_dir = Path(__file__).resolve().parent.parent / "dashboard"
    if dashboard_dir.exists():
        app.mount("/", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")
    else:
        logger.warning("Dashboard directory %s missing — static UI not mounted", dashboard_dir)
    return app


app = create_app()
