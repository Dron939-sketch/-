"""City pulse (ТЗ §12, MVP adapter).

«Пульс города» — композитный индекс 0..100 здоровья города, собранный
из четырёх независимых подфакторов, каждый со своим весом. Отличие от
остальных блоков: это единое число для мэра, чтобы ответить на вопрос
«как дела в целом» за 5 секунд.

Факторы (вес → что меряют):
    metrics_health  0.40  — среднее по 4 векторам Мейстера (сб/тф/уб/чв),
                            нормализовано на шкалу 0..100.
    crisis_calm     0.25  — обратно от состояния кризис-детектора:
                            ok=100, watch=55, attention=15, else 70.
    media_calm      0.20  — 100 * (1 - negative_share) от репутации.
    appeals_relief  0.15  — clamp(100 - 8*log10(max(1,appeals_24h)), 0, 100).

Итоговый индекс (чем выше = тем спокойнее):
    ≥ 80  calm      "Спокойно"
    ≥ 60  normal    "В норме"
    ≥ 40  elevated  "Повышенное внимание"
    ≥ 20  high      "Высокая температура"
    < 20  critical  "Критическая лихорадка"

Легаси `city_pulse.py` строит тепловые карты по районам (их у нас нет)
и подключает >=50 источников. Адаптер ужат до honest-агрегатора над
сигналами, которые уже есть в БД.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


_FACTOR_META: List[Dict[str, Any]] = [
    {"key": "metrics_health",
     "label": "Здоровье векторов",
     "weight": 0.40,
     "description": "Среднее значение СБ / ТФ / УБ / ЧВ, нормализовано на 0–100."},
    {"key": "crisis_calm",
     "label": "Отсутствие кризисов",
     "weight": 0.25,
     "description": "Обратная величина от состояния детектора ранних сигналов."},
    {"key": "media_calm",
     "label": "Спокойствие в медиа",
     "weight": 0.20,
     "description": "100 − доля негативных упоминаний за 24 часа."},
    {"key": "appeals_relief",
     "label": "Нагрузка обращений",
     "weight": 0.15,
     "description": "Чем меньше обращений за сутки, тем выше значение."},
]


_LEVELS = [
    (80, "calm",     "Спокойно"),
    (60, "normal",   "В норме"),
    (40, "elevated", "Повышенное внимание"),
    (20, "high",     "Высокая температура"),
    (0,  "critical", "Критическая лихорадка"),
]


@dataclass
class PulseFactor:
    key: str
    label: str
    value: float          # 0..100
    weight: float
    contribution: float   # value × weight
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "value": round(self.value, 1),
            "weight": round(self.weight, 3),
            "contribution": round(self.contribution, 2),
            "description": self.description,
        }


@dataclass
class PulseReport:
    overall: float                # 0..100
    level: str                    # calm | normal | elevated | high | critical
    label: str
    factors: List[PulseFactor] = field(default_factory=list)
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": round(self.overall, 1),
            "level": self.level,
            "label": self.label,
            "factors": [f.to_dict() for f in self.factors],
            "note": self.note,
        }


def compute(
    metrics: Optional[Dict[str, float]] = None,
    crisis_status: Optional[str] = None,
    negative_share: Optional[float] = None,
    appeals_24h: Optional[int] = None,
) -> PulseReport:
    """Combine signals into a single 0..100 pulse.

    Any missing signal neutralises its factor at 50 (mid-band) so an
    empty-fresh install reports as «повышенное внимание» rather than
    collapsing to zero or full-score.
    """
    values = {
        "metrics_health":  _metrics_health(metrics),
        "crisis_calm":     _crisis_calm(crisis_status),
        "media_calm":      _media_calm(negative_share),
        "appeals_relief":  _appeals_relief(appeals_24h),
    }

    factors: List[PulseFactor] = []
    overall = 0.0
    for meta in _FACTOR_META:
        v = values[meta["key"]]
        weight = meta["weight"]
        contribution = v * weight
        overall += contribution
        factors.append(PulseFactor(
            key=meta["key"], label=meta["label"],
            value=v, weight=weight, contribution=contribution,
            description=meta["description"],
        ))

    overall = max(0.0, min(100.0, overall))
    level, label = _level_for(overall)

    note = None
    signals_present = any([
        metrics is not None, crisis_status is not None,
        negative_share is not None, appeals_24h is not None,
    ])
    if not signals_present:
        note = "Сигналов нет — показан baseline пульс 50."

    return PulseReport(
        overall=overall, level=level, label=label, factors=factors, note=note,
    )


# ---------------------------------------------------------------------------
# factor helpers
# ---------------------------------------------------------------------------

def _metrics_health(metrics: Optional[Dict[str, float]]) -> float:
    if not metrics:
        return 50.0
    values: List[float] = []
    for key in ("sb", "tf", "ub", "chv"):
        v = metrics.get(key)
        try:
            if v is not None:
                values.append(max(1.0, min(6.0, float(v))))
        except (TypeError, ValueError):
            continue
    if not values:
        return 50.0
    avg = sum(values) / len(values)  # 1..6
    return max(0.0, min(100.0, (avg - 1.0) / 5.0 * 100.0))


def _crisis_calm(status: Optional[str]) -> float:
    if status is None:
        return 50.0
    s = str(status).strip().lower()
    return {
        "ok":        100.0,
        "watch":     55.0,
        "attention": 15.0,
    }.get(s, 50.0)


def _media_calm(neg_share: Optional[float]) -> float:
    if neg_share is None:
        return 50.0
    try:
        share = max(0.0, min(1.0, float(neg_share)))
    except (TypeError, ValueError):
        return 50.0
    return (1.0 - share) * 100.0


def _appeals_relief(count: Optional[int]) -> float:
    if count is None:
        return 50.0
    try:
        n = max(0, int(count))
    except (TypeError, ValueError):
        return 50.0
    if n <= 0:
        return 100.0
    # Log-scale: 1→98, 10→92, 50→86, 100→84, 500→78, 1000→76. Clamped.
    return max(0.0, min(100.0, 100.0 - 8.0 * math.log10(n + 1)))


def _level_for(score: float) -> tuple:
    for threshold, key, label in _LEVELS:
        if score >= threshold:
            return key, label
    return "critical", "Критическая лихорадка"
