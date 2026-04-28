"""Тесты проактивных алертов Джарвиса.

Pure-логика порогов в `tasks.jarvis_proactive` через мок upsert_alert
+ моков city_crisis / latest_metrics / metrics_trend_7d.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# fail-safe behavior без БД
# ---------------------------------------------------------------------------

def test_check_city_no_db_returns_empty():
    from tasks.jarvis_proactive import check_city
    out = asyncio.run(check_city("Коломна"))
    assert out == []


# ---------------------------------------------------------------------------
# С полными моками
# ---------------------------------------------------------------------------

def _patch_pipeline(crisis=None, metrics=None, trend=None):
    """Контекст-менеджер: ставит моки на city_id_by_name + city_crisis +
    latest_metrics + metrics_trend_7d + upsert_alert. Возвращает список
    upsert'ов, которые были сделаны."""
    inserted: List[Dict[str, Any]] = []

    async def fake_cid(_): return 42
    async def fake_crisis(_): return crisis
    async def fake_metrics(_): return metrics
    async def fake_trend(_):   return trend

    async def fake_upsert(**kw):
        inserted.append(kw)
        return len(inserted)  # фейковый id

    p_cid     = patch("db.seed.city_id_by_name", fake_cid)
    p_crisis  = patch("api.routes.city_crisis", fake_crisis)
    p_metrics = patch("db.queries.latest_metrics", fake_metrics)
    p_trend   = patch("db.queries.metrics_trend_7d", fake_trend)
    p_upsert  = patch("db.jarvis_alerts_queries.upsert_alert", fake_upsert)
    return p_cid, p_crisis, p_metrics, p_trend, p_upsert, inserted


def test_check_city_emits_crisis_alert():
    p_cid, p_crisis, p_metrics, p_trend, p_upsert, inserted = _patch_pipeline(
        crisis={"level": "high", "alerts": [{"title": "прорыв трубы"}]},
        metrics=None, trend=None,
    )
    from tasks.jarvis_proactive import check_city
    with p_cid, p_crisis, p_metrics, p_trend, p_upsert:
        asyncio.run(check_city("Коломна"))
    keys = [i["key"] for i in inserted]
    assert "crisis_high" in keys


def test_check_city_emits_metric_low_alert():
    p_cid, p_crisis, p_metrics, p_trend, p_upsert, inserted = _patch_pipeline(
        crisis=None,
        metrics={"sb": 4.0, "tf": 4.5, "ub": 2.7, "chv": 4.0},  # ub просел
        trend=None,
    )
    from tasks.jarvis_proactive import check_city
    with p_cid, p_crisis, p_metrics, p_trend, p_upsert:
        asyncio.run(check_city("Коломна"))
    keys = [i["key"] for i in inserted]
    assert "metric_ub_low" in keys
    levels = [i["level"] for i in inserted if i["key"] == "metric_ub_low"]
    assert levels == ["warning"]   # 2.7 < 3.0 но >= 2.5 → warning


def test_check_city_emits_metric_critical_alert():
    p_cid, p_crisis, p_metrics, p_trend, p_upsert, inserted = _patch_pipeline(
        crisis=None,
        metrics={"sb": 4.0, "tf": 4.5, "ub": 2.0, "chv": 4.0},  # ub critical
        trend=None,
    )
    from tasks.jarvis_proactive import check_city
    with p_cid, p_crisis, p_metrics, p_trend, p_upsert:
        asyncio.run(check_city("Коломна"))
    levels = [i["level"] for i in inserted if i["key"] == "metric_ub_low"]
    assert levels == ["critical"]   # 2.0 < 2.5 → critical


def test_check_city_silent_when_metrics_normal():
    p_cid, p_crisis, p_metrics, p_trend, p_upsert, inserted = _patch_pipeline(
        crisis=None,
        metrics={"sb": 4.0, "tf": 4.5, "ub": 4.2, "chv": 4.0},  # всё хорошо
        trend=None,
    )
    from tasks.jarvis_proactive import check_city
    with p_cid, p_crisis, p_metrics, p_trend, p_upsert:
        asyncio.run(check_city("Коломна"))
    assert inserted == []


def test_check_city_emits_trend_drop():
    p_cid, p_crisis, p_metrics, p_trend, p_upsert, inserted = _patch_pipeline(
        crisis=None, metrics=None,
        trend={"sb": -0.9, "tf": 0.1, "ub": -0.3, "chv": 0.0},  # sb падает
    )
    from tasks.jarvis_proactive import check_city
    with p_cid, p_crisis, p_metrics, p_trend, p_upsert:
        asyncio.run(check_city("Коломна"))
    keys = [i["key"] for i in inserted]
    assert "trend_sb_drop" in keys
    assert "trend_ub_drop" not in keys   # -0.3 не критично


def test_check_city_combines_signals():
    p_cid, p_crisis, p_metrics, p_trend, p_upsert, inserted = _patch_pipeline(
        crisis={"level": "high", "alerts": [{"title": "alert"}]},
        metrics={"sb": 2.4, "tf": 4.0, "ub": 4.0, "chv": 4.0},
        trend={"sb": -1.5, "tf": 0.0, "ub": 0.2, "chv": 0.0},
    )
    from tasks.jarvis_proactive import check_city
    with p_cid, p_crisis, p_metrics, p_trend, p_upsert:
        asyncio.run(check_city("Коломна"))
    keys = {i["key"] for i in inserted}
    assert "crisis_high" in keys
    assert "metric_sb_low" in keys
    assert "trend_sb_drop" in keys
