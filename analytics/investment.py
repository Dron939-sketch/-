"""Investment attractiveness index (ТЗ §22, MVP adapter).

Lightweight rollup that converts the signals we already collect into an
investment-attractiveness score with factor breakdown, strengths /
weaknesses, and a letter grade — in the same pure-function style as
the other analytics bridges (benchmark, crisis, reputation).

Signals (all optional):
  - latest_metrics: sb / tf / ub / chv (1..6) + trust_index / happiness_index (0..1)
  - business_news_positive  : count of positive business-category news in 7 days
  - business_news_negative  : count of negative business-category news in 7 days
  - population              : from config
  - peer_rank               : dict {position: 1-based, total: int, leader_slug: str}
  - crisis_status           : "ok" | "watch" | "attention"

Factors (0..1 each), weighted into `overall_index` (0..100):
  economic_climate   0.25 — tf + business-news polarity
  safety             0.15 — sb
  quality_of_life    0.15 — ub + happiness_index
  social_capital     0.15 — chv + trust_index
  market_access      0.15 — log10(population) scaled + peer composite rank
  stability          0.15 — inverse of crisis_status

Grades (stable bands on the 0..100 scale):
  ≥ 85  A+
  ≥ 75  A
  ≥ 65  B+
  ≥ 55  B
  ≥ 45  C+
  ≥ 35  C
  < 35  D

The legacy `investment_attractiveness.py` ships a 9-factor enum + pandas
clustering over peer cities. That's overkill for a 6-city pilot without
per-factor survey data; the adapter here uses the indirect signals we
do have and stays transparent about the formula in the API response.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


_METRIC_DIVISOR = 6.0   # 1..6 scale → 0..1
_POP_MIN = 20_000       # saturation floor for the log-scaled market-access factor
_POP_MAX = 300_000      # saturation cap above which the factor plateaus at 1.0


_FACTOR_META: List[Dict[str, Any]] = [
    {
        "key": "economic_climate",
        "label": "Экономика",
        "weight": 0.25,
        "description": "ТФ + новостной фон бизнеса за 7 дней.",
    },
    {
        "key": "safety",
        "label": "Безопасность",
        "weight": 0.15,
        "description": "СБ — прямой вектор.",
    },
    {
        "key": "quality_of_life",
        "label": "Качество жизни",
        "weight": 0.15,
        "description": "УБ + индекс счастья.",
    },
    {
        "key": "social_capital",
        "label": "Социальный капитал",
        "weight": 0.15,
        "description": "ЧВ + доверие к власти.",
    },
    {
        "key": "market_access",
        "label": "Доступ к рынку",
        "weight": 0.15,
        "description": "Логарифм населения + позиция в бенчмарке.",
    },
    {
        "key": "stability",
        "label": "Стабильность",
        "weight": 0.15,
        "description": "Обратная величина от уровня кризисных сигналов.",
    },
]


@dataclass
class Factor:
    key: str
    label: str
    value: float                # 0..1
    weight: float               # sums to 1.0 across factors
    contribution: float         # weight × value × 100
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "value": round(self.value, 3),
            "weight": round(self.weight, 3),
            "contribution": round(self.contribution, 2),
            "description": self.description,
        }


@dataclass
class InvestmentProfile:
    overall_index: float                        # 0..100
    grade: str                                   # A+..D
    factors: List[Factor]
    strengths: List[str]
    weaknesses: List[str]
    peer_rank: Optional[Dict[str, Any]] = None
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_index": round(self.overall_index, 1),
            "grade": self.grade,
            "factors": [f.to_dict() for f in self.factors],
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "peer_rank": self.peer_rank,
            "note": self.note,
        }


def compute(signals: Optional[Dict[str, Any]] = None) -> InvestmentProfile:
    """Compute the investment attractiveness profile from available signals.

    Missing signals neutralise their factor (contribution = 0.5) so a brand-new
    city without data shows up as "mid-pack" rather than blowing up the formula.
    """
    s = signals or {}
    factor_values: Dict[str, float] = {}

    factor_values["economic_climate"] = _economic_climate(s)
    factor_values["safety"]           = _vector_to_unit(s.get("sb"))
    factor_values["quality_of_life"]  = _blend(
        _vector_to_unit(s.get("ub")),
        _coerce_unit(s.get("happiness_index")),
    )
    factor_values["social_capital"]   = _blend(
        _vector_to_unit(s.get("chv")),
        _coerce_unit(s.get("trust_index")),
    )
    factor_values["market_access"]    = _market_access(s)
    factor_values["stability"]        = _stability(s.get("crisis_status"))

    factors: List[Factor] = []
    total = 0.0
    for meta in _FACTOR_META:
        v = factor_values.get(meta["key"], 0.5)
        v = max(0.0, min(1.0, v))
        contribution = meta["weight"] * v * 100.0
        total += contribution
        factors.append(
            Factor(
                key=meta["key"],
                label=meta["label"],
                value=v,
                weight=meta["weight"],
                contribution=contribution,
                description=meta["description"],
            )
        )

    overall = max(0.0, min(100.0, total))
    grade = _grade_for(overall)

    # Strengths / weaknesses: take the 2 highest-value factors as strengths,
    # 2 lowest as weaknesses. Ties broken by weight desc then insertion order.
    ranked = sorted(factors, key=lambda f: (f.value, f.weight), reverse=True)
    strengths = [f"{f.label} ({int(f.value * 100)}%)" for f in ranked[:2] if f.value >= 0.5]
    weaknesses = [f"{f.label} ({int(f.value * 100)}%)" for f in ranked[-2:] if f.value < 0.6]

    peer = s.get("peer_rank")
    if isinstance(peer, dict):
        peer = {
            "position": _coerce_int(peer.get("position")),
            "total":    _coerce_int(peer.get("total")),
            "leader_slug": peer.get("leader_slug"),
        }
    else:
        peer = None

    note = None
    if not signals:
        note = "Нет сигналов — показано baseline-значение."

    return InvestmentProfile(
        overall_index=overall,
        grade=grade,
        factors=factors,
        strengths=strengths,
        weaknesses=weaknesses,
        peer_rank=peer,
        note=note,
    )


# ---------------------------------------------------------------------------
# individual factor helpers
# ---------------------------------------------------------------------------

def _vector_to_unit(v: Any) -> float:
    f = _coerce_float(v)
    if f is None:
        return 0.5
    return max(0.0, min(1.0, f / _METRIC_DIVISOR))


def _coerce_unit(v: Any) -> float:
    f = _coerce_float(v)
    if f is None:
        return 0.5
    return max(0.0, min(1.0, f))


def _blend(a: float, b: float, weight_a: float = 0.5) -> float:
    return weight_a * a + (1.0 - weight_a) * b


def _economic_climate(s: Dict[str, Any]) -> float:
    base = _vector_to_unit(s.get("tf"))  # 0..1 from the TF vector
    pos = _coerce_int(s.get("business_news_positive")) or 0
    neg = _coerce_int(s.get("business_news_negative")) or 0
    total = pos + neg
    if total == 0:
        return base
    # Polarity ∈ [-1, 1]; scale to [-0.15, +0.15] adjustment and clamp.
    polarity = (pos - neg) / total
    adjusted = base + 0.15 * polarity
    return max(0.0, min(1.0, adjusted))


def _market_access(s: Dict[str, Any]) -> float:
    pop = _coerce_int(s.get("population"))
    if pop is None:
        pop_unit = 0.5
    else:
        if pop <= _POP_MIN:
            pop_unit = 0.0
        elif pop >= _POP_MAX:
            pop_unit = 1.0
        else:
            # log scale between POP_MIN and POP_MAX → 0..1
            pop_unit = (math.log(pop) - math.log(_POP_MIN)) / (math.log(_POP_MAX) - math.log(_POP_MIN))
            pop_unit = max(0.0, min(1.0, pop_unit))

    peer = s.get("peer_rank")
    if isinstance(peer, dict):
        pos = _coerce_int(peer.get("position"))
        total = _coerce_int(peer.get("total"))
        if pos and total and total > 1:
            # #1 → 1.0, last → 0.0.
            rank_unit = 1.0 - (pos - 1) / (total - 1)
        else:
            rank_unit = 0.5
    else:
        rank_unit = 0.5

    return 0.5 * pop_unit + 0.5 * rank_unit


def _stability(status: Any) -> float:
    if status == "ok":
        return 1.0
    if status == "watch":
        return 0.6
    if status == "attention":
        return 0.2
    return 0.5


def _grade_for(score: float) -> str:
    if score >= 85: return "A+"
    if score >= 75: return "A"
    if score >= 65: return "B+"
    if score >= 55: return "B"
    if score >= 45: return "C+"
    if score >= 35: return "C"
    return "D"


# ---------------------------------------------------------------------------
# utils
# ---------------------------------------------------------------------------

def _coerce_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _coerce_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
