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
from typing import List, Set

from fastapi import APIRouter, HTTPException

from agenda.daily_agenda import DailyAgendaBuilder
from agenda.roadmap_planner import RoadmapPlanner
from ai import NewsEnricher
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
    """Aggregated metric snapshot consumed by the mayor dashboard."""
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
    slow upstream cannot block the whole response.
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

    Collects fresh news, runs them through the DeepSeek-backed enricher
    (sentiment / category / severity / summary) and feeds the result into
    `DailyAgendaBuilder`. If the enricher is disabled or fails, the builder
    falls back to source-level categories and still produces a valid report.
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
            enrichment=None,
        )
        for n in news_response.items
    ]

    enricher = NewsEnricher()
    if enricher.enabled:
        try:
            await asyncio.wait_for(enricher.enrich(news_items), timeout=30)
        except asyncio.TimeoutError:
            logger.warning("enricher timed out — proceeding without enrichment")

    city_metrics = {"СБ": 4.0, "ТФ": 3.5, "УБ": 3.8, "ЧВ": 4.2}
    trust = {
        "index": 0.58,
        "top_complaints": _pick_titles(
            news_items, {"complaints", "utilities", "incidents"}, 3, negative_only=True
        ),
        "top_praises": _pick_titles(
            news_items, {"culture", "sport", "official"}, 3, positive_only=True
        ),
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

    # If we have enrichment data, override the headline with the highest
    # severity story — more reliable than the source-based heuristic.
    top_severe = _top_by_severity(news_items)
    if top_severe is not None:
        agenda.headline = (
            top_severe.enrichment.get("summary") or top_severe.title
        )
        agenda.description = top_severe.content[:400]

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


# ----- helpers -----


def _pick_titles(
    items: List[CollectedItem],
    categories: Set[str],
    limit: int,
    *,
    negative_only: bool = False,
    positive_only: bool = False,
) -> List[str]:
    """Pick short summaries/titles matching a set of categories.

    Prefers the AI-generated `summary` when the enricher has tagged the
    item; falls back to the raw title. Optionally filters by sentiment sign.
    """
    out: List[str] = []
    for it in items:
        enr = it.enrichment or {}
        cat = (enr.get("category") or it.category or "other")
        if cat not in categories:
            continue
        sent = enr.get("sentiment")
        if negative_only and (sent is None or sent > -0.1):
            # Without sentiment data, keep the item — better a non-negative
            # complaint than an empty list.
            if sent is not None:
                continue
        if positive_only and (sent is None or sent < 0.1):
            if sent is not None:
                continue
        text = enr.get("summary") or it.title
        if text:
            out.append(text)
            if len(out) >= limit:
                break
    return out


def _top_by_severity(items: List[CollectedItem]) -> CollectedItem | None:
    """Return the item with the highest AI-scored severity, if any."""
    scored = [
        (it, it.enrichment.get("severity"))
        for it in items
        if it.enrichment and it.enrichment.get("severity") is not None
    ]
    if not scored:
        return None
    scored.sort(key=lambda pair: pair[1], reverse=True)
    top_item, top_sev = scored[0]
    # Only override when the model actually flagged something notable.
    if top_sev is None or top_sev < 0.5:
        return None
    return top_item
