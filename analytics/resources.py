"""Resource planner (ТЗ §13, MVP adapter).

Recommends how much of the annual municipal budget each Meister vector
should get this planning cycle, given where the city is weakest and what
crisis signals are active. Pure function + rules:

Base share: equal 22.5% per vector (× 4 = 90%) + 10% fixed reserve.
Adjustments:
  - Low score (< 3.5) → boost share by (3.5 - score) × 4%  per point.
  - Active crisis alert on this vector → +8 pp boost.
  - High score (> 4.5) → trim share by (score - 4.5) × 3%  per point.
Shares are then renormalised so vectors still sum to (1 − reserve).

Priority bucket per vector (for the UI badge):
  critical: score ≤ 2.5  OR crisis_on_vector
  high:     score ≤ 3.5
  medium:   score ≤ 4.5
  low:      otherwise

The default per-capita factor (30 000 ₽/year) is tuned against actual
Russian municipal budgets: typical monocity at 80k-150k population
runs 2.5-5 bn ₽/year total — 30k/person lands squarely in that band.
Override via `per_capita_rub` if you want to model a different scenario.

Legacy `resource_planner.py` brings LP/IP solvers + 5 resource types +
department allocations. Out of scope — the mayor mostly wants "cut/add
here" at the vector level, and we can expose the LP path later once
actual project-level data exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


_VECTOR_KEYS = ["safety", "economy", "quality", "social"]
_VECTOR_LABELS = {
    "safety":  "Безопасность (СБ)",
    "economy": "Экономика (ТФ)",
    "quality": "Качество жизни (УБ)",
    "social":  "Социальный капитал (ЧВ)",
}
_METRIC_COLUMN = {"safety": "sb", "economy": "tf", "quality": "ub", "social": "chv"}

_BASE_SHARE_PER_VECTOR = 0.225   # 4 × 22.5% = 90% → 10% reserve
_RESERVE_SHARE = 0.10
_LOW_BOOST_PER_POINT = 0.04      # +4 pp per point below 3.5
_HIGH_TRIM_PER_POINT = 0.03      # -3 pp per point above 4.5
_CRISIS_BOOST = 0.08             # +8 pp if any crisis alert mentions this vector

_DEFAULT_PER_CAPITA_RUB = 30_000  # annual budget / person


@dataclass
class VectorAllocation:
    key: str
    label: str
    current_score: Optional[float]
    recommended_share: float       # 0..1 (sum across vectors = 1 - reserve)
    recommended_rub: int
    priority: str                   # critical / high / medium / low
    has_crisis: bool
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "current_score": round(self.current_score, 2) if self.current_score is not None else None,
            "recommended_share": round(self.recommended_share, 4),
            "recommended_rub": int(self.recommended_rub),
            "priority": self.priority,
            "has_crisis": self.has_crisis,
            "rationale": self.rationale,
        }


@dataclass
class ResourcePlan:
    total_budget_rub: int
    per_capita_rub: int
    population: Optional[int]
    reserve_share: float
    reserve_rub: int
    allocations: List[VectorAllocation] = field(default_factory=list)
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_budget_rub": int(self.total_budget_rub),
            "per_capita_rub": int(self.per_capita_rub),
            "population": self.population,
            "reserve_share": round(self.reserve_share, 4),
            "reserve_rub": int(self.reserve_rub),
            "allocations": [a.to_dict() for a in self.allocations],
            "note": self.note,
        }


def plan(
    current_metrics: Optional[Dict[str, float]] = None,
    crisis_alerts: Optional[Iterable[Dict[str, Any]]] = None,
    population: Optional[int] = None,
    per_capita_rub: int = _DEFAULT_PER_CAPITA_RUB,
) -> ResourcePlan:
    """Recommend vector-level budget allocation from current signals.

    Missing `population` falls back to 50 000 (small-town scale) so the
    UI always has a concrete total to display. Any invalid metrics /
    alerts are silently ignored.
    """
    current = dict(current_metrics or {})
    alerts = list(crisis_alerts or [])
    pop = _coerce_int(population) or 50_000
    per_capita = max(1000, int(per_capita_rub))
    total_rub = pop * per_capita

    # Step 1: map crisis alerts → vectors they affect.
    crisis_on: Dict[str, bool] = {k: False for k in _VECTOR_KEYS}
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        v = alert.get("vector")
        if v in crisis_on:
            crisis_on[v] = True

    # Step 2: compute raw shares with adjustments.
    raw_shares: Dict[str, float] = {}
    scores: Dict[str, Optional[float]] = {}
    for vkey in _VECTOR_KEYS:
        col = _METRIC_COLUMN[vkey]
        score = _coerce_float(current.get(col))
        scores[vkey] = score
        share = _BASE_SHARE_PER_VECTOR
        if score is not None:
            if score < 3.5:
                share += (3.5 - score) * _LOW_BOOST_PER_POINT
            elif score > 4.5:
                share -= (score - 4.5) * _HIGH_TRIM_PER_POINT
        if crisis_on[vkey]:
            share += _CRISIS_BOOST
        raw_shares[vkey] = max(0.05, share)   # never drop a vector below 5%

    # Step 3: renormalise to sum to (1 - reserve).
    target_sum = 1.0 - _RESERVE_SHARE
    total_raw = sum(raw_shares.values())
    if total_raw <= 0:
        raw_shares = {k: target_sum / len(_VECTOR_KEYS) for k in _VECTOR_KEYS}
        total_raw = target_sum
    scale = target_sum / total_raw
    shares = {k: v * scale for k, v in raw_shares.items()}

    # Step 4: build per-vector allocation objects.
    allocations: List[VectorAllocation] = []
    for vkey in _VECTOR_KEYS:
        share = shares[vkey]
        score = scores[vkey]
        priority = _priority_for(score, crisis_on[vkey])
        rationale = _rationale_for(score, crisis_on[vkey], share)
        allocations.append(
            VectorAllocation(
                key=vkey,
                label=_VECTOR_LABELS[vkey],
                current_score=score,
                recommended_share=share,
                recommended_rub=int(round(share * total_rub)),
                priority=priority,
                has_crisis=crisis_on[vkey],
                rationale=rationale,
            )
        )

    reserve_rub = int(round(_RESERVE_SHARE * total_rub))
    note = None if current else "Нет метрик — показано базовое распределение 22.5% × 4."
    return ResourcePlan(
        total_budget_rub=total_rub,
        per_capita_rub=per_capita,
        population=pop,
        reserve_share=_RESERVE_SHARE,
        reserve_rub=reserve_rub,
        allocations=allocations,
        note=note,
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _priority_for(score: Optional[float], has_crisis: bool) -> str:
    if has_crisis:
        return "critical"
    if score is None:
        return "medium"
    if score <= 2.5:
        return "critical"
    if score <= 3.5:
        return "high"
    if score <= 4.5:
        return "medium"
    return "low"


def _rationale_for(score: Optional[float], has_crisis: bool, share: float) -> str:
    parts: List[str] = []
    if score is not None:
        if score < 3.5:
            parts.append(f"балл {score:.1f} — ниже среднего, усилен")
        elif score > 4.5:
            parts.append(f"балл {score:.1f} — выше среднего, урезан")
        else:
            parts.append(f"балл {score:.1f} — в норме")
    if has_crisis:
        parts.append("активный кризисный сигнал")
    if not parts:
        parts.append("нет данных — базовая доля")
    parts.append(f"итого {share * 100:.1f}%")
    return " · ".join(parts)


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
