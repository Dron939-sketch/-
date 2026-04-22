"""HTTP routes for the CityMind API.

Endpoints:
  GET  /health
  GET  /api/cities
  GET  /api/city/{name}
  GET  /api/city/{name}/news
  GET  /api/city/{name}/all_metrics
  GET  /api/city/{name}/agenda
  POST /api/city/{name}/roadmap
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException

from agenda.daily_agenda import DailyAgendaBuilder
from agenda.roadmap_planner import RoadmapPlanner
from collectors import (
    AppealsCollector,
    NewsCollector,
    TelegramCollector,
    VKCollector,
)
from collectors.base import CollectedItem
from config.cities import CITIES, get_city
from config.settings import settings

from . import schemas

logger = logging.getLogger(__name__)
router = APIRouter()

VERSION = "0.1.0"


@router.get("/health", response_model=schemas.HealthResponse)
async def health() -> schemas.HealthResponse:
    return schemas.HealthResponse(
        status="ok", version=VERSION, default_city=settings.default_city
    )


@router.get("/api/cities", response_model=List[schemas.CityBrief])
async def list_cities() -> List[schemas.CityBrief]:
    return [schemas.CityBrief(**cfg) for cfg in CITIES.values()]


@router.get("/api/city/{name}", response_model=schemas.CityBrief)
async def city_detail(name: str) -> schemas.CityBrief:
    try:
        cfg = get_city(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return schemas.CityBrief(**cfg)


@router.get("/api/city/{name}/all_metrics")
async def all_metrics(name: str) -> dict:
    """Aggregated metric snapshot consumed by the mayor dashboard.

    Shape matches `dashboard/dashboard.js` expectations (weather, 4-vector
    city_metrics, trust, happiness, 8 composite indices). While the
    TimescaleDB `metrics` table is empty we serve deterministic placeholders
    so the UI renders — real values land here once the Celery collection
    loop is running and writing to Postgres.
    """
    try:
        get_city(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {
        "city": name,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "weather": {
            "temperature": 12.0,
            "feels_like": 10.0,
            "condition": "Облачно",
            "condition_emoji": "☁️",
            "humidity": 78,
            "wind_speed": 3.5,
            "comfort_index": 0.6,
        },
        "city_metrics": {
            "safety": 4.0 / 6.0,
            "economy": 3.5 / 6.0,
            "quality": 3.8 / 6.0,
            "social": 4.2 / 6.0,
        },
        "trust": {
            "index": 0.58,
            "positive_mentions": 0,
            "negative_mentions": 0,
            "top_complaints": [
                "Дороги в центре требуют ремонта",
                "Перебои в работе транспорта утром",
                "Недостаток детских площадок в новых районах",
            ],
            "top_praises": [],
            "trend": "stable",
        },
        "happiness": {
            "overall": 0.62,
            "life_satisfaction": 0.64,
            "emotional_state": 0.60,
            "social_connection": 0.65,
            "top_factors": ["погода", "культурные события", "зарплаты"],
        },
        "composite_indices": {
            "quality_of_life": 0.63,
            "economic_development": 0.55,
            "social_cohesion": 0.68,
            "environmental": 0.72,
            "infrastructure": 0.58,
            "mayoral_performance": 0.60,
            "city_attractiveness": 0.66,
            "future_outlook": 0.62,
            "overall_color": "warn",
        },
    }


@router.get("/api/city/{name}/news", response_model=schemas.NewsResponse)
async def collect_news(name: str, limit: int = 100) -> schemas.NewsResponse:
    """Run all configured collectors for a city and return a merged feed.

    Each collector has a hard 15 s wall clock via `asyncio.wait_for` so one
    slow upstream cannot block the whole response. In production the heavy
    lifting is done by a Celery worker on a schedule and this endpoint
    serves rows from Postgres instead.
    """
    try:
        get_city(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    collectors = [
        TelegramCollector(name),
        VKCollector(name),
        NewsCollector(name),
        AppealsCollector(name),
    ]
    items: List[CollectedItem] = []
    for coll in collectors:
        try:
            items.extend(await asyncio.wait_for(coll.collect(), timeout=15))
        except asyncio.TimeoutError:
            logger.warning("collector timed out: %s", type(coll).__name__)
        except Exception:  # noqa: BLE001
            logger.exception("collector failure: %s", type(coll).__name__)
        finally:
            await coll.close()

    items.sort(key=lambda it: it.published_at, reverse=True)
    payload = [schemas.NewsItem(**it.to_dict()) for it in items[:limit]]
    return schemas.NewsResponse(city=name, collected=len(payload), items=payload)


@router.get("/api/city/{name}/agenda", response_model=schemas.AgendaResponse)
async def daily_agenda(name: str) -> schemas.AgendaResponse:
    """Compose the morning briefing.

    Pulls a fresh news window (time-capped above) and pairs it with
    placeholder metrics. When the TimescaleDB store is online the metrics
    come from a SELECT of the latest row.
    """
    try:
        get_city(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    news_response = await collect_news(name, limit=200)
    news_items = [
        CollectedItem(
            source_kind=n.source_kind,
            source_handle=n.source_handle,
            title=n.title,
            content=n.content,
            published_at=n.published_at,
            url=n.url,
            category=n.category,
        )
        for n in news_response.items
    ]

    city_metrics = {"СБ": 4.0, "ТФ": 3.5, "УБ": 3.8, "ЧВ": 4.2}
    trust = {
        "index": 0.58,
        "top_complaints": _top_titles_by_category(news_items, {"complaints", "utilities"}, 3),
        "top_praises": _top_titles_by_category(news_items, {"culture", "sport"}, 3),
    }
    happiness = {"overall": 0.62}
    weather = {"temperature": 12.0, "condition": "Облачно", "condition_emoji": "☁️"}

    builder = DailyAgendaBuilder(city_name=name)
    agenda = builder.build(
        date=datetime.now(tz=timezone.utc),
        city_metrics=city_metrics,
        trust=trust,
        happiness=happiness,
        weather=weather,
        news=news_items,
    )

    return schemas.AgendaResponse(
        city=agenda.city,
        date=agenda.date,
        headline=agenda.headline,
        description=agenda.description,
        actions=agenda.actions,
        top_complaints=agenda.top_complaints,
        top_praises=agenda.top_praises,
        vectors=agenda.vectors,
        weather_line=agenda.weather_line,
        happiness=agenda.happiness,
        trust=agenda.trust,
        markdown=agenda.to_markdown(),
    )


@router.post("/api/city/{name}/roadmap", response_model=schemas.RoadmapResponse)
async def roadmap(name: str, req: schemas.RoadmapRequest) -> schemas.RoadmapResponse:
    try:
        get_city(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    planner = RoadmapPlanner(name)
    try:
        plan = planner.plan(
            vector=req.vector,
            start_level=req.start_level,
            target_level=req.target_level,
            deadline=req.deadline,
            scenario=req.scenario,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return schemas.RoadmapResponse(city=name, roadmap=plan.to_dict())


def _top_titles_by_category(
    items: List[CollectedItem], categories: set, limit: int
) -> List[str]:
    picked: List[str] = []
    for it in items:
        if it.category in categories and it.title:
            picked.append(it.title)
            if len(picked) >= limit:
                break
    return picked
