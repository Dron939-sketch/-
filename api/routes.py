"""HTTP routes for the Городской Разум API.

Endpoints:
  GET  /health
  GET  /api/cities
  GET  /api/city/{name}
  GET  /api/city/by-slug/{slug}
  GET  /api/city/{name}/news
  GET  /api/city/{name}/all_metrics
  GET  /api/city/{name}/agenda
  POST /api/city/{name}/roadmap
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Set

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
from config.cities import CITIES, get_city, get_city_by_slug
from config.settings import settings
from db.queries import (
    latest_weather,
    news_counts_last_24h,
    top_recent_summaries,
)
from db.seed import city_id_by_name

from . import schemas

logger = logging.getLogger(__name__)
router = APIRouter()

VERSION = "0.3.0"


def _resolve_city(name_or_slug: str):
    try:
        return get_city(name_or_slug)
    except KeyError:
        pass
    try:
        return get_city_by_slug(name_or_slug)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/health", response_model=schemas.HealthResponse)
async def health() -> schemas.HealthResponse:
    return schemas.HealthResponse(
        status="ok", version=VERSION, default_city=settings.default_city
    )


@router.get("/api/cities", response_model=List[schemas.CityBrief])
async def list_cities() -> List[schemas.CityBrief]:
    return [schemas.CityBrief(**cfg) for cfg in CITIES.values()]


@router.get("/api/city/by-slug/{slug}", response_model=schemas.CityBrief)
async def city_by_slug(slug: str) -> schemas.CityBrief:
    try:
        cfg = get_city_by_slug(slug)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return schemas.CityBrief(**cfg)


@router.get("/api/city/{name}", response_model=schemas.CityBrief)
async def city_detail(name: str) -> schemas.CityBrief:
    cfg = _resolve_city(name)
    return schemas.CityBrief(**cfg)


# ---------------------------------------------------------------------------
# Dashboard snapshot
# ---------------------------------------------------------------------------

_PLACEHOLDER_WEATHER: Dict[str, Any] = {
    "temperature": 12.0,
    "feels_like": 10.0,
    "condition": "Облачно",
    "condition_emoji": "☁️",
    "humidity": 78,
    "wind_speed": 3.5,
    "comfort_index": 0.6,
}

_PLACEHOLDER_COMPLAINTS = [
    "Дороги в центре требуют ремонта",
    "Перебои в работе транспорта утром",
    "Недостаток детских площадок в новых районах",
]


@router.get("/api/city/{name}/all_metrics")
async def all_metrics(name: str) -> dict:
    """Aggregated metric snapshot consumed by the mayor dashboard.

    When the DB has data we serve it; otherwise we fall back to
    deterministic placeholders so the UI still renders on a cold deploy.
    """
    cfg = _resolve_city(name)

    city_id = await city_id_by_name(cfg["name"])
    weather: Dict[str, Any] = dict(_PLACEHOLDER_WEATHER)
    top_complaints: List[str] = list(_PLACEHOLDER_COMPLAINTS)
    top_praises: List[str] = []
    news_counts = {"negative": 0, "positive": 0, "total": 0}
    trust_index = 0.58

    if city_id is not None:
        wx = await latest_weather(city_id)
        if wx is not None:
            weather = {
                "temperature": wx.get("temperature"),
                "feels_like": wx.get("feels_like"),
                "condition": wx.get("condition"),
                "condition_emoji": wx.get("condition_emoji"),
                "humidity": wx.get("humidity"),
                "wind_speed": wx.get("wind_speed"),
                "comfort_index": wx.get("comfort_index"),
            }
        counts = await news_counts_last_24h(city_id)
        if counts.get("total", 0) > 0:
            news_counts = counts
            # Derive a cheap trust index: fewer complaints -> higher trust.
            ratio = counts["negative"] / max(counts["total"], 1)
            trust_index = round(max(0.0, min(1.0, 0.8 - ratio * 0.6)), 2)
            complaints_live = await top_recent_summaries(
                city_id,
                categories={"complaints", "utilities", "incidents"},
                negative=True,
                limit=3,
            )
            if complaints_live:
                top_complaints = complaints_live
            praises_live = await top_recent_summaries(
                city_id,
                categories={"culture", "sport", "official"},
                positive=True,
                limit=3,
            )
            if praises_live:
                top_praises = praises_live

    return {
        "city": cfg["name"],
        "slug": cfg.get("slug"),
        "emoji": cfg.get("emoji"),
        "accent_color": cfg.get("accent_color"),
        "region": cfg.get("region"),
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "weather": weather,
        "city_metrics": {
            "safety": 4.0 / 6.0,
            "economy": 3.5 / 6.0,
            "quality": 3.8 / 6.0,
            "social": 4.2 / 6.0,
        },
        "trends": {
            "safety": 0.02,
            "economy": -0.01,
            "quality": 0.05,
            "social": -0.03,
        },
        "trust": {
            "index": trust_index,
            "positive_mentions": news_counts["positive"],
            "negative_mentions": news_counts["negative"],
            "top_complaints": top_complaints,
            "top_praises": top_praises,
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
        "loops": [
            {"name": "Безопасность → Экономика", "level": "critical"},
            {"name": "Качество жизни → Отток", "level": "warn"},
            {"name": "Институциональная петля", "level": "info"},
        ],
        "forecast_3m": {
            "summary": (
                "При текущем сценарии через 3 месяца безопасность снизится "
                "до 3.5/6, а экономика вырастет до 4.1/6. Петля «Безопасность "
                "→ Экономика» усилится на 40%."
            ),
            "recommendation": (
                "Разорвать петлю через инвестиции в безопасность — "
                "окупаемость 4 месяца."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Live collection + agenda + roadmap (unchanged)
# ---------------------------------------------------------------------------

@router.get("/api/city/{name}/news", response_model=schemas.NewsResponse)
async def collect_news(name: str, limit: int = 100) -> schemas.NewsResponse:
    cfg = _resolve_city(name)

    collectors = [
        TelegramCollector(cfg["name"]),
        VKCollector(cfg["name"]),
        NewsCollector(cfg["name"]),
        AppealsCollector(cfg["name"]),
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
    return schemas.NewsResponse(city=cfg["name"], collected=len(payload), items=payload)


@router.get("/api/city/{name}/agenda", response_model=schemas.AgendaResponse)
async def daily_agenda(name: str) -> schemas.AgendaResponse:
    cfg = _resolve_city(name)

    news_response = await collect_news(cfg["name"], limit=200)
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

    builder = DailyAgendaBuilder(city_name=cfg["name"])
    agenda = builder.build(
        date=datetime.now(tz=timezone.utc),
        city_metrics=city_metrics,
        trust=trust,
        happiness=happiness,
        weather=weather,
        news=news_items,
    )

    top_severe = _top_by_severity(news_items)
    if top_severe is not None:
        agenda.headline = top_severe.enrichment.get("summary") or top_severe.title
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
    cfg = _resolve_city(name)
    planner = RoadmapPlanner(cfg["name"])
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
    return schemas.RoadmapResponse(city=cfg["name"], roadmap=plan.to_dict())


# ----- helpers -----


def _pick_titles(
    items: List[CollectedItem],
    categories: Set[str],
    limit: int,
    *,
    negative_only: bool = False,
    positive_only: bool = False,
) -> List[str]:
    out: List[str] = []
    for it in items:
        enr = it.enrichment or {}
        cat = (enr.get("category") or it.category or "other")
        if cat not in categories:
            continue
        sent = enr.get("sentiment")
        if negative_only and sent is not None and sent > -0.1:
            continue
        if positive_only and sent is not None and sent < 0.1:
            continue
        text = enr.get("summary") or it.title
        if text:
            out.append(text)
            if len(out) >= limit:
                break
    return out


def _top_by_severity(items: List[CollectedItem]) -> CollectedItem | None:
    scored = [
        (it, it.enrichment.get("severity"))
        for it in items
        if it.enrichment and it.enrichment.get("severity") is not None
    ]
    if not scored:
        return None
    scored.sort(key=lambda pair: pair[1], reverse=True)
    top_item, top_sev = scored[0]
    if top_sev is None or top_sev < 0.5:
        return None
    return top_item
