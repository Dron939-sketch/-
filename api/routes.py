"""HTTP routes for the CityMind API.

Endpoints:
  GET  /health
  GET  /api/cities
  GET  /api/city/{name}
  GET  /api/city/{name}/news
  GET  /api/city/{name}/all_metrics  (compatible with app.py stub)
  GET  /api/city/{name}/agenda
  POST /api/city/{name}/roadmap
"""

from __future__ import annotations

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


@router.get("/api/city/{name}/news", response_model=schemas.NewsResponse)
async def collect_news(name: str, limit: int = 100) -> schemas.NewsResponse:
    """Run all configured collectors for a city and return a merged feed.

    The call is synchronous and may take several seconds if upstream APIs
    are slow. In production it is usually invoked by a Celery worker on a
    schedule and the stored rows are served from Postgres instead.
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
            items.extend(await coll.collect())
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

    This endpoint pulls a fresh news window and pairs it with whatever
    cached metrics are currently known for the city. If the metrics store
    is empty we fall back to placeholders that still produce a valid report.
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

    # Placeholder metric snapshot. When the TimescaleDB `metrics` table is
    # wired up this will be replaced by a SELECT of the latest row.
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
