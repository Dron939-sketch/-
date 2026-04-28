"""Тесты pure-функции генератора тем для депутатов.

Без БД, без сети — только проверяем логику кластеризации жалоб + порогов
по метрикам.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from analytics.deputy_topic_generator import (
    METRIC_CRITICAL_THRESHOLD,
    METRIC_LOW_THRESHOLD,
    MIN_COMPLAINTS_FOR_TOPIC,
    auto_assign_deputies,
    generate_topics_from_signals,
)
from collectors.base import CollectedItem


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc)


def _make_item(category: str, title: str, *, sentiment: float | None = None) -> CollectedItem:
    enrichment = {"sentiment": sentiment} if sentiment is not None else None
    return CollectedItem(
        source_kind="vk",
        source_handle="kolomna_tut",
        title=title,
        content=title,
        published_at=_NOW - timedelta(hours=2),
        category=category,
        enrichment=enrichment,
    )


def _deputies(*specs: dict) -> List[dict]:
    """specs — список {"id": int, "role": str, "sectors": [...]} с разумными default'ами."""
    return [
        {
            "id": s["id"],
            "role": s.get("role", "district_rep"),
            "sectors": s.get("sectors", []),
            "district": s.get("district", "Округ №1"),
            "enabled": s.get("enabled", True),
        }
        for s in specs
    ]


# ---------------------------------------------------------------------------
# Кластеры жалоб
# ---------------------------------------------------------------------------

def test_no_signals_returns_empty():
    out = generate_topics_from_signals(news=[], metrics=None, now=_NOW)
    assert out == []


def test_single_complaint_below_threshold_returns_no_topic():
    items = [_make_item("utilities", "Прорыв трубы")]
    assert MIN_COMPLAINTS_FOR_TOPIC > 1, "тест предполагает порог >1"
    out = generate_topics_from_signals(news=items, metrics=None, now=_NOW)
    assert out == []


def test_three_utilities_complaints_yield_topic():
    items = [
        _make_item("utilities", "Прорыв трубы на Ленина"),
        _make_item("utilities", "Нет горячей воды в Колычёво"),
        _make_item("utilities", "Перебои с отоплением"),
    ]
    out = generate_topics_from_signals(news=items, metrics=None, now=_NOW)
    assert len(out) == 1
    t = out[0]
    assert "ЖКХ" in t["title"]
    assert t["source"] == "auto_complaints"
    assert "ЖКХ" in t["target_sectors"]
    assert t["priority"] == "medium"
    assert t["status"] == "active"
    assert len(t["talking_points"]) >= 1


def test_six_complaints_promote_to_high_priority():
    items = [_make_item("utilities", f"Жалоба #{i}") for i in range(6)]
    out = generate_topics_from_signals(news=items, metrics=None, now=_NOW)
    assert len(out) == 1
    assert out[0]["priority"] == "high"


def test_negative_sentiment_counts_even_without_complaint_category():
    # Категория "news" обычно нейтральная, но при сильном negative sentiment'е
    # _is_negative() должна засчитывать → попадёт в bucket "complaints" по умолчанию.
    items = [_make_item("complaints", f"News #{i}", sentiment=-0.7) for i in range(3)]
    out = generate_topics_from_signals(news=items, metrics=None, now=_NOW)
    assert len(out) == 1


def test_positive_news_does_not_create_topic():
    items = [_make_item("culture", f"Открытие выставки #{i}", sentiment=0.6) for i in range(5)]
    out = generate_topics_from_signals(news=items, metrics=None, now=_NOW)
    assert out == []


def test_unknown_category_falls_back_to_complaints_bucket():
    items = [_make_item("garbage_category", f"Жалоба #{i}", sentiment=-0.5) for i in range(3)]
    out = generate_topics_from_signals(news=items, metrics=None, now=_NOW)
    assert len(out) == 1
    assert "благоустройство" in out[0]["target_sectors"] or "общая_повестка" in out[0]["target_sectors"]


# ---------------------------------------------------------------------------
# Метрики
# ---------------------------------------------------------------------------

def test_metric_above_threshold_is_quiet():
    out = generate_topics_from_signals(
        news=[],
        metrics={"sb": 4.5, "tf": 4.0, "ub": 4.2, "chv": 4.1},
        now=_NOW,
    )
    assert out == []


def test_low_ub_creates_high_priority_topic():
    out = generate_topics_from_signals(
        news=[],
        metrics={"ub": 2.8, "sb": 4.0, "tf": 4.0, "chv": 4.0},
        now=_NOW,
    )
    assert len(out) == 1
    t = out[0]
    assert t["priority"] == "high"
    assert "соцзащита" in t["target_sectors"]
    assert t["source"] == "auto_metrics"
    assert t["target_tone"] == "explanatory"


def test_critical_chv_creates_critical_topic():
    out = generate_topics_from_signals(
        news=[],
        metrics={"chv": 2.0, "sb": 4.0, "tf": 4.0, "ub": 4.0},
        now=_NOW,
    )
    assert len(out) == 1
    t = out[0]
    assert t["priority"] == "critical"
    assert t["target_tone"] == "protective"
    assert "Критическое" in t["title"]


def test_multiple_low_metrics_each_get_topic():
    out = generate_topics_from_signals(
        news=[],
        metrics={"ub": 2.7, "chv": 2.6, "sb": 4.0, "tf": 4.0},
        now=_NOW,
    )
    sources = {t["source"] for t in out}
    assert sources == {"auto_metrics"}
    assert len(out) == 2


def test_none_metrics_in_dict_are_skipped():
    out = generate_topics_from_signals(
        news=[],
        metrics={"ub": None, "chv": 2.0},
        now=_NOW,
    )
    assert len(out) == 1
    assert "Человек-Власть" in out[0]["description"] or "доверия" in out[0]["title"]


def test_threshold_constants_are_sane():
    assert METRIC_CRITICAL_THRESHOLD < METRIC_LOW_THRESHOLD
    assert MIN_COMPLAINTS_FOR_TOPIC >= 1


# ---------------------------------------------------------------------------
# Auto-assign
# ---------------------------------------------------------------------------

def test_auto_assign_picks_speakers_for_high_priority():
    deputies = _deputies(
        {"id": 1, "role": "speaker", "sectors": ["общая_повестка"]},
        {"id": 2, "role": "district_rep", "sectors": ["соцзащита"]},
    )
    cand = {"priority": "high", "target_sectors": ["соцзащита"]}
    chosen = auto_assign_deputies(cand, deputies)
    assert 1 in chosen  # speaker подключён несмотря на отсутствие сектора
    assert 2 in chosen


def test_auto_assign_skips_speakers_for_medium_priority():
    deputies = _deputies(
        {"id": 1, "role": "speaker", "sectors": []},
        {"id": 2, "role": "district_rep", "sectors": ["ЖКХ"]},
    )
    cand = {"priority": "medium", "target_sectors": ["ЖКХ"]}
    chosen = auto_assign_deputies(cand, deputies)
    assert chosen == [2]


def test_auto_assign_respects_max_assignees():
    deputies = _deputies(*[
        {"id": i, "role": "district_rep", "sectors": ["ЖКХ"]} for i in range(1, 11)
    ])
    cand = {"priority": "medium", "target_sectors": ["ЖКХ"]}
    chosen = auto_assign_deputies(cand, deputies, max_assignees=3)
    assert len(chosen) == 3


def test_auto_assign_skips_disabled_deputies():
    deputies = _deputies(
        {"id": 1, "role": "district_rep", "sectors": ["ЖКХ"], "enabled": False},
        {"id": 2, "role": "district_rep", "sectors": ["ЖКХ"]},
    )
    cand = {"priority": "medium", "target_sectors": ["ЖКХ"]}
    chosen = auto_assign_deputies(cand, deputies)
    assert chosen == [2]


def test_auto_assign_with_no_target_sectors_returns_empty_for_low_priority():
    deputies = _deputies(
        {"id": 1, "role": "district_rep", "sectors": ["ЖКХ"]},
    )
    cand = {"priority": "medium", "target_sectors": []}
    chosen = auto_assign_deputies(cand, deputies)
    assert chosen == []
