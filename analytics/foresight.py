"""Foresight — 5-year scenario forecasting (ТЗ §20, MVP adapter).

Three-scenario projection of the 4 Meister vectors plus megatrend impact
assessment, over a 5-year horizon. Inputs are signals we already collect;
the output shape is dashboard-ready.

Scenarios (per ТЗ §20.1):
    pessimistic  — trends extrapolated + -0.5 drag per vector by year 5
    baseline     — current trends extrapolated straight
    optimistic   — trends extrapolated + +0.5 boost per vector by year 5

Probabilities (fixed prior): 25% / 50% / 25%. These can be overridden
later if real expert Delphi data arrives.

Megatrends (per ТЗ §20.2) — 10 global drivers with region-specific
relevance for SE Moscow Oblast. Each exposes:
    impact    — signed -1..+1 net direction for the city
    relevance — 0..1 how strongly the trend applies locally

The legacy `foresight.py` brings Shell-method scenario planning +
Delphi-method expert aggregation + black-swan enumeration. That's out
of scope for an MVP — the bridge keeps the most useful slice
(3 scenarios + megatrend grid) and stays transparent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


_HORIZON_YEARS = 5
_VECTOR_KEYS = ["safety", "economy", "quality", "social"]
_VECTOR_LABELS = {
    "safety":  "Безопасность",
    "economy": "Экономика",
    "quality": "Качество жизни",
    "social":  "Социальный капитал",
}
_METRIC_COLUMN = {"safety": "sb", "economy": "tf", "quality": "ub", "social": "chv"}
_CLAMP_MIN = 1.0
_CLAMP_MAX = 6.0

# Scenario modifiers — cumulative nudge added/subtracted over 5 years,
# linear-spread so year 1 gets 1/5 of the total, year 3 gets 3/5, etc.
_SCENARIO_MOD = {"pessimistic": -0.5, "baseline": 0.0, "optimistic": +0.5}

_SCENARIO_META = [
    {
        "key": "optimistic",
        "label": "Оптимистичный",
        "probability": 0.25,
        "description": "Трансформация + активные инвестиции + благоприятная макроэкономика.",
    },
    {
        "key": "baseline",
        "label": "Базовый",
        "probability": 0.50,
        "description": "Инерционный — текущие тренды экстраполируются без внешних шоков.",
    },
    {
        "key": "pessimistic",
        "label": "Пессимистичный",
        "probability": 0.25,
        "description": "Стагнация, санкционное давление, ухудшение инфраструктуры.",
    },
]

# 10 megatrends per ТЗ §20.2, relevance tuned for SE Moscow Oblast.
# `impact` is the net direction for the city given the trend (positive
# means the trend as-is helps the city, negative means it hurts).
_MEGATRENDS: List[Dict[str, Any]] = [
    {"key": "urbanization",   "label": "Урбанизация",
     "impact": +0.2, "relevance": 0.7,
     "description": "Приток населения из сёл — возможность роста рынка."},
    {"key": "digitalization", "label": "Цифровизация",
     "impact": +0.6, "relevance": 0.9,
     "description": "Госуслуги и удалёнка — ускорение управленческих процессов."},
    {"key": "aging",          "label": "Старение населения",
     "impact": -0.3, "relevance": 0.8,
     "description": "Повышенная нагрузка на здравоохранение и соцзащиту."},
    {"key": "climate",        "label": "Изменение климата",
     "impact": -0.4, "relevance": 0.5,
     "description": "Аномальная жара и паводки — риск ЖКХ и урожая."},
    {"key": "remote_work",    "label": "Удалённая работа",
     "impact": +0.5, "relevance": 0.7,
     "description": "Возможность удерживать специалистов, не мигрирующих в Москву."},
    {"key": "ecology",        "label": "Экологическое сознание",
     "impact": +0.4, "relevance": 0.6,
     "description": "Спрос на зелёные зоны и экологичные производства."},
    {"key": "health",         "label": "Здравоохранение",
     "impact": +0.3, "relevance": 0.6,
     "description": "Цифровые медуслуги повышают доступность."},
    {"key": "education",      "label": "Образование",
     "impact": +0.3, "relevance": 0.5,
     "description": "Онлайн-обучение уменьшает разрыв с мегаполисами."},
    {"key": "mobility",       "label": "Новая мобильность",
     "impact": +0.3, "relevance": 0.6,
     "description": "Электротранспорт, каршеринг — снижение нагрузки на дороги."},
    {"key": "localization",   "label": "Локализация производства",
     "impact": +0.5, "relevance": 0.7,
     "description": "Импортозамещение открывает ниши для малого бизнеса."},
]


@dataclass
class VectorProjection:
    key: str
    label: str
    current: Optional[float]
    year_1: Optional[float]
    year_3: Optional[float]
    year_5: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        def _r(v: Optional[float]) -> Optional[float]:
            return round(v, 2) if v is not None else None

        return {
            "key": self.key,
            "label": self.label,
            "current": _r(self.current),
            "year_1":  _r(self.year_1),
            "year_3":  _r(self.year_3),
            "year_5":  _r(self.year_5),
        }


@dataclass
class Scenario:
    key: str
    label: str
    probability: float
    description: str
    composite_current: Optional[float]
    composite_year_5: Optional[float]
    vectors: List[VectorProjection] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        def _r(v: Optional[float]) -> Optional[float]:
            return round(v, 2) if v is not None else None

        return {
            "key": self.key,
            "label": self.label,
            "probability": round(self.probability, 3),
            "description": self.description,
            "composite_current": _r(self.composite_current),
            "composite_year_5": _r(self.composite_year_5),
            "vectors": [v.to_dict() for v in self.vectors],
        }


@dataclass
class MegatrendRow:
    key: str
    label: str
    impact: float           # -1..+1
    relevance: float        # 0..1
    weighted: float         # impact × relevance (signed)
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "impact": round(self.impact, 2),
            "relevance": round(self.relevance, 2),
            "weighted": round(self.weighted, 2),
            "direction": "up" if self.weighted > 0.05 else "down" if self.weighted < -0.05 else "flat",
            "description": self.description,
        }


@dataclass
class ForesightReport:
    horizon_years: int
    scenarios: List[Scenario]
    megatrends: List[MegatrendRow]
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "horizon_years": self.horizon_years,
            "scenarios": [s.to_dict() for s in self.scenarios],
            "megatrends": [m.to_dict() for m in self.megatrends],
            "note": self.note,
        }


def forecast(
    current_metrics: Optional[Dict[str, float]] = None,
    trend_per_vector: Optional[Dict[str, float]] = None,
) -> ForesightReport:
    """Project the 4 vectors 5 years forward across 3 scenarios.

    `current_metrics` keys: sb / tf / ub / chv (1..6 scale).
    `trend_per_vector` keys: safety / economy / quality / social — the
        per-year slope in the same 1..6 scale (e.g. +0.1 means +0.1 per year).
        If missing or zero, projections extrapolate only the scenario
        modifier (0 for baseline, ±0.5 for the bounding scenarios).

    Any vector without a current value is returned with `current=None` and
    all-None projections.
    """
    current = dict(current_metrics or {})
    trends = dict(trend_per_vector or {})

    scenarios: List[Scenario] = []
    for meta in _SCENARIO_META:
        modifier = _SCENARIO_MOD[meta["key"]]
        scenario_vectors: List[VectorProjection] = []
        for vkey in _VECTOR_KEYS:
            col = _METRIC_COLUMN[vkey]
            cur = _coerce_float(current.get(col))
            slope = _coerce_float(trends.get(vkey)) or 0.0
            if cur is None:
                scenario_vectors.append(
                    VectorProjection(key=vkey, label=_VECTOR_LABELS[vkey],
                                     current=None, year_1=None, year_3=None, year_5=None)
                )
                continue
            y1 = _clamp(cur + slope * 1.0 + modifier * 1.0 / _HORIZON_YEARS)
            y3 = _clamp(cur + slope * 3.0 + modifier * 3.0 / _HORIZON_YEARS)
            y5 = _clamp(cur + slope * 5.0 + modifier)
            scenario_vectors.append(
                VectorProjection(
                    key=vkey, label=_VECTOR_LABELS[vkey],
                    current=cur, year_1=y1, year_3=y3, year_5=y5,
                )
            )

        # Composite = mean across vectors that have data.
        present_cur = [v.current for v in scenario_vectors if v.current is not None]
        present_y5 = [v.year_5 for v in scenario_vectors if v.year_5 is not None]
        composite_current = sum(present_cur) / len(present_cur) if present_cur else None
        composite_year_5 = sum(present_y5) / len(present_y5) if present_y5 else None

        scenarios.append(
            Scenario(
                key=meta["key"],
                label=meta["label"],
                probability=meta["probability"],
                description=meta["description"],
                composite_current=composite_current,
                composite_year_5=composite_year_5,
                vectors=scenario_vectors,
            )
        )

    megatrends = [
        MegatrendRow(
            key=m["key"], label=m["label"],
            impact=m["impact"], relevance=m["relevance"],
            weighted=m["impact"] * m["relevance"],
            description=m["description"],
        )
        for m in _MEGATRENDS
    ]

    note = None if current else "Нет текущих метрик — показаны только сценарные модификаторы."
    return ForesightReport(
        horizon_years=_HORIZON_YEARS,
        scenarios=scenarios,
        megatrends=megatrends,
        note=note,
    )


def _clamp(v: float) -> float:
    return max(_CLAMP_MIN, min(_CLAMP_MAX, float(v)))


def _coerce_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
