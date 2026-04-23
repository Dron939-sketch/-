"""HTTP routes for the Городской Разум API.

Endpoints:
  GET  /health
  GET  /api/cities
  GET  /api/city/{name}
  GET  /api/city/by-slug/{slug}
  GET  /api/city/{name}/news
  GET  /api/city/{name}/all_metrics
  GET  /api/city/{name}/history
  GET  /api/city/{name}/model
  POST /api/city/{name}/simulate
  GET  /api/city/{name}/root_cause/{node_id}
  GET  /api/city/{name}/metric/{vector}/breakdown
  GET  /api/city/{name}/crisis
  GET  /api/city/{name}/reputation
  GET  /api/city/{name}/investment
  GET  /api/benchmark
  GET  /api/city/{name}/agenda
  POST /api/city/{name}/roadmap
"""

from __future__ import annotations

import asyncio
import functools
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from agenda.daily_agenda import DailyAgendaBuilder
from agenda.roadmap_planner import RoadmapPlanner
from ai import NewsEnricher
from analytics import benchmark as benchmark_cities
from analytics import breakdown as breakdown_metric
from analytics import build_graph, detect_crises, simulate, trace_root_cause
from analytics import investment_compute, reputation_analyze
from collectors import (
    AppealsCollector,
    NewsCollector,
)
from collectors.base import CollectedItem
from config.cities import CITIES, get_city, get_city_by_slug
from config.settings import settings
from db.loops_queries import latest_loops
from db.queries import (
    appeals_count,
    latest_metrics,
    latest_weather,
    metrics_history,
    metrics_trend_7d,
    news_category_sentiment_counts,
    news_counts_last_24h,
    news_negative_count,
    news_total_count,
    news_window,
    top_recent_summaries,
)
from db.seed import city_id_by_name
from metrics.forecast import build_forecast_block

from . import schemas

logger = logging.getLogger(__name__)
router = APIRouter()

VERSION = "0.10.0"

_AGENDA_ENRICHMENT_TIMEOUT_S = 10

# Vector → the news categories that dominate its signal. Mirrors the
# grouping in `metrics/snapshot.py` so the transparency endpoint and
# the snapshot aggregator agree on which news items count where.
_VECTOR_NEWS_CATEGORIES: Dict[str, Set[str]] = {
    "safety":  {"incidents", "utilities", "complaints"},
    "economy": {"business", "official"},
    "quality": {"transport", "culture", "utilities"},
    "social":  {"culture", "sport"},
}

_VECTOR_METRIC_COLUMN = {
    "safety":  "sb",
    "economy": "tf",
    "quality": "ub",
    "social":  "chv",
}


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

_PLACEHOLDER_VECTORS = {
    "safety": 4.0 / 6.0,
    "economy": 3.5 / 6.0,
    "quality": 3.8 / 6.0,
    "social": 4.2 / 6.0,
}

_PLACEHOLDER_TRENDS = {
    "safety": 0.0,
    "economy": 0.0,
    "quality": 0.0,
    "social": 0.0,
}

_PLACEHOLDER_FORECAST = {
    "summary": "Прогноз появится через несколько дней — система накапливает историю.",
    "recommendation": "",
}

_PLACEHOLDER_LOOPS: List[Dict[str, Any]] = [
    {"name": "Безопасность → Экономика", "level": "critical"},
    {"name": "Качество жизни → Отток",   "level": "warn"},
    {"name": "Институциональная петля",  "level": "info"},
]


@router.get("/api/city/{name}/all_metrics")
async def all_metrics(name: str) -> dict:
    """Aggregated metric snapshot consumed by the mayor dashboard."""
    cfg = _resolve_city(name)

    city_id = await city_id_by_name(cfg["name"])
    weather: Dict[str, Any] = dict(_PLACEHOLDER_WEATHER)
    top_complaints: List[str] = list(_PLACEHOLDER_COMPLAINTS)
    top_praises: List[str] = []
    news_counts = {"negative": 0, "positive": 0, "total": 0}
    trust_index = 0.58
    happiness_overall = 0.62
    city_metrics = dict(_PLACEHOLDER_VECTORS)
    trends = dict(_PLACEHOLDER_TRENDS)
    forecast = dict(_PLACEHOLDER_FORECAST)
    loops_block: List[Dict[str, Any]] = list(_PLACEHOLDER_LOOPS)

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

        metric_row = await latest_metrics(city_id)
        if metric_row is not None:
            def _to_unit(v: Any) -> float | None:
                return None if v is None else round(float(v) / 6.0, 3)

            live = {
                "safety":  _to_unit(metric_row.get("sb")),
                "economy": _to_unit(metric_row.get("tf")),
                "quality": _to_unit(metric_row.get("ub")),
                "social":  _to_unit(metric_row.get("chv")),
            }
            for k, v in live.items():
                if v is not None:
                    city_metrics[k] = v
            if metric_row.get("trust_index") is not None:
                trust_index = round(float(metric_row["trust_index"]), 2)
            if metric_row.get("happiness_index") is not None:
                happiness_overall = round(float(metric_row["happiness_index"]), 2)

            trend_row = await metrics_trend_7d(city_id)
            if any(abs(v) > 0 for v in trend_row.values()):
                trends = trend_row

            history = await metrics_history(city_id, days=30)
            forecast = build_forecast_block(history, days_ahead=90)

        stored_loops = await latest_loops(city_id, limit=3)
        if stored_loops:
            loops_block = [
                {
                    "name": loop["name"],
                    "level": loop.get("level") or "info",
                    "description": loop.get("description"),
                    "strength": loop.get("strength"),
                    "break_points": loop.get("break_points") or {},
                }
                for loop in stored_loops
            ]

    return {
        "city": cfg["name"],
        "slug": cfg.get("slug"),
        "emoji": cfg.get("emoji"),
        "accent_color": cfg.get("accent_color"),
        "region": cfg.get("region"),
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "weather": weather,
        "city_metrics": city_metrics,
        "trends": trends,
        "trust": {
            "index": trust_index,
            "positive_mentions": news_counts["positive"],
            "negative_mentions": news_counts["negative"],
            "top_complaints": top_complaints,
            "top_praises": top_praises,
            "trend": "stable",
        },
        "happiness": {
            "overall": happiness_overall,
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
        "loops": loops_block,
        "forecast_3m": forecast,
    }


@router.get("/api/city/{name}/history")
async def city_history(
    name: str,
    days: int = Query(default=30, ge=1, le=365),
) -> dict:
    """Raw 4-vector history for sparklines."""
    cfg = _resolve_city(name)
    empty: Dict[str, List[List[Any]]] = {"sb": [], "tf": [], "ub": [], "chv": []}

    city_id = await city_id_by_name(cfg["name"])
    if city_id is None:
        return {"city": cfg["name"], "days": days, "series": empty}

    hist = await metrics_history(city_id, days=days)
    series = {
        key: [[ts.isoformat(), value] for ts, value in points]
        for key, points in hist.items()
    }
    return {"city": cfg["name"], "days": days, "series": series}


async def _build_city_graph(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Shared helper: pull the latest snapshot and build the graph."""
    snapshot: Dict[str, float] = {"sb": 3.5, "tf": 3.5, "ub": 3.5, "chv": 3.5}
    city_id = await city_id_by_name(cfg["name"])
    if city_id is not None:
        metric_row = await latest_metrics(city_id)
        if metric_row is not None:
            for key in ("sb", "tf", "ub", "chv"):
                val = metric_row.get(key)
                if val is not None:
                    snapshot[key] = float(val)

    loop = asyncio.get_running_loop()
    # city_id is keyword-only on build_graph — wrap in a partial so the
    # executor call doesn't pass it positionally (raises TypeError).
    graph = await loop.run_in_executor(
        None,
        functools.partial(build_graph, cfg["name"], snapshot, city_id=city_id),
    )
    graph["slug"] = cfg.get("slug")
    graph["snapshot"] = snapshot
    return graph


@router.get("/api/city/{name}/model")
async def city_model(name: str) -> dict:
    """9-element Meister graph for the dashboard's Cytoscape widget."""
    cfg = _resolve_city(name)
    return await _build_city_graph(cfg)


class SimulateRequest(BaseModel):
    source_node_id: str = Field(..., description="Node id (1..9) the mayor turns the dial on")
    delta: float = Field(..., ge=-6.0, le=6.0, description="Absolute change in 1..6 scale")


@router.post("/api/city/{name}/simulate")
async def city_simulate(name: str, req: SimulateRequest) -> dict:
    """Butterfly-effect simulator."""
    cfg = _resolve_city(name)
    graph = await _build_city_graph(cfg)
    if graph.get("disabled"):
        raise HTTPException(
            status_code=503,
            detail=f"confinement graph unavailable ({graph.get('reason')})",
        )

    sim = simulate(graph, req.source_node_id, req.delta)
    return {
        "city": cfg["name"],
        "slug": cfg.get("slug"),
        **sim.to_dict(),
    }


@router.get("/api/city/{name}/root_cause/{node_id}")
async def city_root_cause(
    name: str,
    node_id: str,
    max_depth: int = Query(default=5, ge=1, le=10),
) -> dict:
    """Root-cause trace backward from the problem node."""
    cfg = _resolve_city(name)
    graph = await _build_city_graph(cfg)
    if graph.get("disabled"):
        raise HTTPException(
            status_code=503,
            detail=f"confinement graph unavailable ({graph.get('reason')})",
        )
    result = trace_root_cause(graph, node_id, max_depth=max_depth)
    return {
        "city": cfg["name"],
        "slug": cfg.get("slug"),
        **result.to_dict(),
    }


@router.get("/api/city/{name}/metric/{vector}/breakdown")
async def city_metric_breakdown(name: str, vector: str) -> dict:
    """Transparency breakdown: where each piece of the metric came from.

    Gathers live signals from the DB (news window, latest snapshot) and
    pipes them into the pure `analytics.breakdown` function, which knows
    the source weights from TZ §3.1. When the DB has no data we still
    return a well-formed response where every component is marked as
    missing — the UI renders "нет данных" badges instead of crashing.
    """
    cfg = _resolve_city(name)
    if vector not in _VECTOR_NEWS_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail="vector must be one of safety / economy / quality / social",
        )

    context: Dict[str, Any] = {}
    city_id = await city_id_by_name(cfg["name"])
    if city_id is not None:
        # News stats for this vector in the last 24h.
        items = await news_window(city_id, hours=24)
        cats = _VECTOR_NEWS_CATEGORIES[vector]
        sentiments: List[float] = []
        neg = pos = 0
        for it in items:
            enr = it.enrichment or {}
            cat = enr.get("category") or it.category
            if cat not in cats:
                continue
            sent = enr.get("sentiment") or it.raw.get("sentiment") if isinstance(getattr(it, "raw", None), dict) else enr.get("sentiment")
            if sent is None:
                continue
            try:
                sent_f = float(sent)
            except (TypeError, ValueError):
                continue
            sentiments.append(sent_f)
            if sent_f < -0.1:
                neg += 1
            elif sent_f > 0.1:
                pos += 1
        if sentiments:
            context["news_avg_sentiment"] = sum(sentiments) / len(sentiments)
            context["news_count"] = len(sentiments)
            context["news_negative"] = neg
            context["news_positive"] = pos

        # Latest metric snapshot — drives forecast + happiness + trust.
        metric_row = await latest_metrics(city_id)
        if metric_row is not None:
            col = _VECTOR_METRIC_COLUMN[vector]
            val = metric_row.get(col)
            if val is not None:
                # Translate the 1..6 value into a [-1..+1] forecast signal.
                context["forecast_signal"] = (float(val) - 3.5) / 2.5
            if metric_row.get("happiness_index") is not None:
                context["happiness_index"] = float(metric_row["happiness_index"])
            if metric_row.get("trust_index") is not None:
                context["trust_index"] = float(metric_row["trust_index"])

    result = breakdown_metric(vector, context)
    return {
        "city": cfg["name"],
        "slug": cfg.get("slug"),
        **result.to_dict(),
    }


@router.get("/api/city/{name}/crisis")
async def city_crisis(name: str) -> dict:
    """Early-warning report: metric drops + sentiment spike + severity + complaints.

    Runs the pure `analytics.detect_crises` over live signals:
      - latest_metrics + last-7-days history for metric_drop
      - news window (24h + 7d negative baseline) for sentiment_spike
      - same news window for high_severity (reads item.severity directly)
      - appeals_count (24h + 7d baseline) for complaint_surge

    All signals are optional — missing DB / empty window silently skip their
    detector. The returned status is one of ok / watch / attention.
    """
    cfg = _resolve_city(name)
    city_id = await city_id_by_name(cfg["name"])

    current: Dict[str, float] = {}
    history_7d: Dict[str, List[float]] = {}
    news_24h: List[Dict[str, Any]] = []
    neg_7d: Optional[int] = None
    appeals_24h = 0
    appeals_7d_avg = 0.0

    if city_id is not None:
        metric_row = await latest_metrics(city_id)
        if metric_row is not None:
            for col in ("sb", "tf", "ub", "chv"):
                val = metric_row.get(col)
                if val is not None:
                    current[col] = float(val)

        history = await metrics_history(city_id, days=7)
        for col in ("sb", "tf", "ub", "chv"):
            history_7d[col] = [val for _ts, val in history.get(col, [])]

        window = await news_window(city_id, hours=24)
        for item in window:
            enr = item.enrichment or {}
            raw = item.raw if isinstance(getattr(item, "raw", None), dict) else {}
            news_24h.append(
                {
                    "title": item.title,
                    "url": item.url,
                    "sentiment": enr.get("sentiment") or raw.get("sentiment"),
                    "severity":  enr.get("severity")  or raw.get("severity"),
                }
            )

        neg_7d = await news_negative_count(city_id, hours=24 * 7)
        appeals_24h = await appeals_count(city_id, hours=24)
        appeals_7d = await appeals_count(city_id, hours=24 * 7)
        appeals_7d_avg = appeals_7d / 7.0

    report = detect_crises(
        current_metrics=current,
        metrics_history_7d=history_7d,
        news_24h=news_24h,
        news_7d_neg_count=neg_7d,
        appeals_24h=appeals_24h,
        appeals_7d_avg=appeals_7d_avg,
    )
    return {
        "city": cfg["name"],
        "slug": cfg.get("slug"),
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        **report.to_dict(),
    }


@router.get("/api/city/{name}/reputation")
async def city_reputation(name: str) -> dict:
    """Media-reputation rollup: top negative authors + viral posts + risk.

    Reads `news_window(24h)` rows, unpacks sentiment/severity/category from
    either flat columns or the enrichment JSONB, and optionally computes the
    7-day negative-share baseline so the rules can detect a fresh spike.
    Returns the pure `analytics.reputation.analyze` output + a generated_at
    timestamp. Everything is fail-safe: no DB means zero-mentions, risk=low.
    """
    cfg = _resolve_city(name)
    city_id = await city_id_by_name(cfg["name"])

    mentions: List[Dict[str, Any]] = []
    prior_share: Optional[float] = None

    if city_id is not None:
        items = await news_window(city_id, hours=24)
        for item in items:
            enr = item.enrichment or {}
            raw = item.raw if isinstance(getattr(item, "raw", None), dict) else {}
            mentions.append(
                {
                    "author": item.author,
                    "source_kind": item.source_kind,
                    "source_handle": item.source_handle,
                    "title": item.title,
                    "url": item.url,
                    "category": enr.get("category") or item.category,
                    "sentiment": enr.get("sentiment") or raw.get("sentiment"),
                    "severity":  enr.get("severity")  or raw.get("severity"),
                }
            )

        total_7d = await news_total_count(city_id, hours=24 * 7)
        if total_7d > 0:
            neg_7d = await news_negative_count(city_id, hours=24 * 7)
            prior_share = neg_7d / total_7d

    report = reputation_analyze(mentions, prior_negative_share=prior_share)
    return {
        "city": cfg["name"],
        "slug": cfg.get("slug"),
        "window_hours": 24,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        **report.to_dict(),
    }


@router.get("/api/city/{name}/investment")
async def city_investment(name: str) -> dict:
    """Investment-attractiveness profile: 6 factors + overall 0..100 + grade.

    Assembles signals from:
      - latest_metrics (sb / tf / ub / chv / trust / happiness)
      - 7d business-category news sentiment counts
      - population from CITIES config
      - benchmark composite rank across all pilots (peer_rank)
      - crisis_status from the rules-based detector

    All signal fetches are fail-safe — missing ones neutralise their factor
    at 0.5 in the pure analyzer, so a brand-new city reports as "mid-pack".
    """
    cfg = _resolve_city(name)
    city_id = await city_id_by_name(cfg["name"])

    signals: Dict[str, Any] = {
        "population": cfg.get("population"),
    }

    if city_id is not None:
        metric_row = await latest_metrics(city_id)
        if metric_row is not None:
            for col in ("sb", "tf", "ub", "chv", "trust_index", "happiness_index"):
                if metric_row.get(col) is not None:
                    signals[col] = metric_row[col]

        biz = await news_category_sentiment_counts(city_id, "business", hours=24 * 7)
        signals["business_news_positive"] = biz["positive"]
        signals["business_news_negative"] = biz["negative"]

    # Peer rank from the existing benchmark — lightweight, same DB hits we
    # already cache in /api/benchmark so this is effectively free.
    try:
        peer = await _peer_rank_for(cfg.get("slug"))
        if peer is not None:
            signals["peer_rank"] = peer
    except Exception:  # noqa: BLE001
        logger.warning("investment: peer_rank unavailable", exc_info=False)

    # Crisis status: re-use the same data-gathering the /crisis endpoint does,
    # but we only need the headline status (ok/watch/attention).
    try:
        crisis = await city_crisis(cfg["name"])
        signals["crisis_status"] = crisis.get("status")
    except Exception:  # noqa: BLE001
        logger.warning("investment: crisis_status unavailable", exc_info=False)

    profile = investment_compute(signals)
    return {
        "city": cfg["name"],
        "slug": cfg.get("slug"),
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        **profile.to_dict(),
    }


async def _peer_rank_for(slug: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return `{position, total, leader_slug}` for this city vs the 6 pilots."""
    if not slug:
        return None
    data = await cross_city_benchmark()
    cities = data.get("cities") or []
    if not cities:
        return None
    total = len([c for c in cities if c.get("composite") is not None])
    leader = cities[0].get("slug") if cities else None
    position = next(
        (c.get("composite_rank") for c in cities if c.get("slug") == slug),
        None,
    )
    if position is None:
        return None
    return {"position": position, "total": total or len(cities), "leader_slug": leader}


@router.get("/api/benchmark")
async def cross_city_benchmark() -> dict:
    """Rank the 6 pilots by SB / ТФ / УБ / ЧВ + composite.

    Pulls the latest metric snapshot for every pilot city and hands the
    batch to `analytics.benchmark`. Cities without a snapshot yet are
    still included (with null values) so the dashboard can render them
    greyed-out instead of hiding them.
    """
    snapshots: List[Dict[str, Any]] = []
    for cfg in CITIES.values():
        snap: Dict[str, Any] = {
            "slug": cfg.get("slug"),
            "name": cfg.get("name"),
            "emoji": cfg.get("emoji") or "🏙️",
            "population": cfg.get("population"),
        }
        city_id = await city_id_by_name(cfg["name"])
        if city_id is not None:
            row = await latest_metrics(city_id)
            if row is not None:
                for col in ("sb", "tf", "ub", "chv", "trust_index", "happiness_index"):
                    if row.get(col) is not None:
                        snap[col] = row[col]
        snapshots.append(snap)

    result = benchmark_cities(snapshots).to_dict()
    result["generated_at"] = datetime.now(tz=timezone.utc).isoformat()
    return result


# ---------------------------------------------------------------------------
# Live collection + agenda + roadmap
# ---------------------------------------------------------------------------

@router.get("/api/city/{name}/news", response_model=schemas.NewsResponse)
async def collect_news(name: str, limit: int = 100) -> schemas.NewsResponse:
    cfg = _resolve_city(name)

    collectors = [
        # --- re-enable when valid TELEGRAM_API_ID/HASH arrive:
        # TelegramCollector(cfg["name"]),
        # --- re-enable when VK access token is valid:
        # VKCollector(cfg["name"]),
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
            await asyncio.wait_for(
                enricher.enrich(news_items),
                timeout=_AGENDA_ENRICHMENT_TIMEOUT_S,
            )
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
