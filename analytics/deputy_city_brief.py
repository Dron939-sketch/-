"""Городской контекст для депутата.

2 виджета внутри кабинета:
- Ключевые показатели города (4 вектора Мейстера + trust + happiness +
  crisis-status). Что важно: сектора депутата подсвечиваем как
  «важно для тебя» — депутат с приоритетом ЖКХ видит, как «УБ»
  стоит сейчас.
- Новости, которые заслуживают её внимания — top-3-5 свежих сюжетов
  отфильтрованных по её sectors (через categories, маппинг ниже).

Все вызовы fail-safe: на null pool возвращаем пустые блоки, чтобы
кабинет работал и без БД.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


# Маппинг sector → news.category (как в категоризаторе collectors)
_SECTOR_TO_CATEGORY = {
    "ЖКХ":             ["utilities", "complaints"],
    "благоустройство": ["complaints", "incidents"],
    "соцзащита":       ["social", "official"],
    "здравоохранение": ["health", "incidents"],
    "молодёжь":        ["culture", "sport"],
    "образование":     ["education", "official"],
    "транспорт":       ["transport", "incidents"],
    "ТКО":             ["utilities", "complaints"],
    "общая_повестка":  ["official", "complaints"],
    "экономика":       ["economy", "official"],
    "культура":        ["culture", "official"],
}


# Маппинг sector → ключевой вектор Мейстера для подсветки «это твой вектор»
_SECTOR_TO_VECTOR = {
    "ЖКХ":             "ub",   # условия-благополучие
    "благоустройство": "ub",
    "соцзащита":       "chv",  # человеческие чувства
    "здравоохранение": "chv",
    "молодёжь":        "chv",
    "образование":     "chv",
    "транспорт":       "ub",
    "ТКО":             "ub",
    "экономика":       "tf",   # технологии-финансы
    "общая_повестка":  "sb",   # стабильность-безопасность
    "культура":        "chv",
}


# Лейблы 4 векторов
_VECTOR_LABELS = {
    "sb":  {"name": "Безопасность",   "code": "СБ"},
    "tf":  {"name": "Технологии · Финансы", "code": "ТФ"},
    "ub":  {"name": "Условия · Быт",  "code": "УБ"},
    "chv": {"name": "Человеческие чувства", "code": "ЧВ"},
}


async def build_city_brief(deputy: Dict[str, Any], city: str = "Коломна") -> Dict[str, Any]:
    """Возвращает {kpi: [...], news_for_me: [...]}."""
    kpi: List[Dict[str, Any]] = []
    news_for_me: List[Dict[str, Any]] = []

    # Сектора депутата → важные для неё векторы
    sectors = list(deputy.get("sectors") or [])
    important_axes = {_SECTOR_TO_VECTOR.get(s) for s in sectors}
    important_axes.discard(None)

    try:
        from db.queries import (
            latest_metrics, news_counts_last_24h, top_recent_summaries,
        )
        from db.seed import city_id_by_name
    except Exception:  # noqa: BLE001
        return {"kpi": kpi, "news_for_me": news_for_me, "state": "no_db"}

    try:
        city_id = await city_id_by_name(city)
    except Exception:  # noqa: BLE001
        return {"kpi": kpi, "news_for_me": news_for_me, "state": "no_db"}

    if city_id is None:
        return {"kpi": kpi, "news_for_me": news_for_me, "state": "no_city"}

    # Метрики (4 вектора по шкале Мейстера 1-6)
    try:
        metrics = await latest_metrics(city_id)
    except Exception:  # noqa: BLE001
        metrics = None

    if metrics:
        for axis, label in _VECTOR_LABELS.items():
            raw = metrics.get(axis)
            if raw is None:
                continue
            try:
                v = round(float(raw), 1)
            except (ValueError, TypeError):
                continue
            kpi.append({
                "axis":      axis,
                "code":      label["code"],
                "name":      label["name"],
                "value":     v,
                "max":       6,
                "important": axis in important_axes,
            })

    # Новости по секторам депутата — top-5 за последние 24ч
    cats: List[str] = []
    for s in sectors:
        for c in _SECTOR_TO_CATEGORY.get(s, []):
            if c not in cats:
                cats.append(c)
    if cats:
        try:
            items = await top_recent_summaries(
                city_id, categories=cats, limit=5,
            )
        except Exception:  # noqa: BLE001
            items = []
        news_for_me = [
            {"text": t, "sectors": _detect_sectors(t, sectors)}
            for t in items
        ]

    # 24h-сводка как фон
    try:
        counts = await news_counts_last_24h(city_id)
    except Exception:  # noqa: BLE001
        counts = {"total": 0}

    return {
        "kpi":           kpi,
        "news_for_me":   news_for_me,
        "news_counts":   counts,
        "important_axes": list(important_axes),
        "state":         "ok",
    }


def _detect_sectors(text: str, sectors: List[str]) -> List[str]:
    """Грубо: какие из секторов упоминаются в тексте."""
    if not text or not sectors:
        return []
    low = text.lower()
    out = []
    for s in sectors:
        if s.lower() in low:
            out.append(s)
    return out
