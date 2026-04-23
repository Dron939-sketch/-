"""Metric transparency breakdown (ТЗ §3.1, §3.7).

For each of the 4 vectors (СБ / ТФ / УБ / ЧВ) we expose the internal
formula the dashboard shows in the «откуда взялась эта цифра?» panel:

    final = baseline + Σ(weight_i × source_i)

Sources and weights come from ТЗ §3.1:
- СБ:  news 0.4 + appeals 0.3 + forecast 0.3
- ТФ:  news 0.4 + business 0.4 + forecast 0.2
- УБ:  news 0.3 + happiness 0.4 + forecast 0.3
- ЧВ:  news 0.3 + trust 0.5 + forecast 0.2

The module is pure: the caller passes already-prepared metric /
news / trust figures. Real data gathering lives in `db.queries`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ТЗ §3.1. Weights intentionally sum to 1.0 for each vector.
_WEIGHTS: Dict[str, Dict[str, float]] = {
    "safety":  {"news": 0.4, "appeals":   0.3, "forecast": 0.3},
    "economy": {"news": 0.4, "business":  0.4, "forecast": 0.2},
    "quality": {"news": 0.3, "happiness": 0.4, "forecast": 0.3},
    "social":  {"news": 0.3, "trust":     0.5, "forecast": 0.2},
}

# Human labels for the dashboard (keeps bits of UI copy in one place).
_SOURCE_LABELS: Dict[str, str] = {
    "news":      "Новости",
    "appeals":   "Обращения граждан",
    "business":  "Бизнес-показатели",
    "happiness": "Индекс счастья",
    "trust":     "Доверие к власти",
    "forecast":  "Прогноз Мейстера",
}

_VECTOR_LABELS: Dict[str, str] = {
    "safety":  "Безопасность (СБ)",
    "economy": "Экономика (ТФ)",
    "quality": "Качество жизни (УБ)",
    "social":  "Социальный капитал (ЧВ)",
}

_BASELINE = 3.5  # Mid-point on the 1..6 scale
_MIN_VAL = 1.0
_MAX_VAL = 6.0


@dataclass
class Component:
    source: str
    label: str
    weight: float
    raw: float          # signal value in the 1..6 scale (delta from baseline)
    contribution: float  # weight × raw, rounded
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "label": self.label,
            "weight": round(self.weight, 3),
            "raw": round(self.raw, 3),
            "contribution": round(self.contribution, 3),
            "detail": self.detail,
        }


@dataclass
class Breakdown:
    vector: str
    vector_label: str
    baseline: float
    final: float
    components: List[Component]
    formula: str
    missing_sources: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vector": self.vector,
            "vector_label": self.vector_label,
            "baseline": round(self.baseline, 2),
            "final": round(self.final, 2),
            "components": [c.to_dict() for c in self.components],
            "formula": self.formula,
            "missing_sources": self.missing_sources,
        }


def breakdown(vector: str, context: Dict[str, Any]) -> Breakdown:
    """Compute the formula breakdown for one vector.

    `context` keys that can appear (all optional):
      - `news_avg_sentiment`: float in [-1, 1], latest window
      - `news_count`:         int, total items in the window
      - `news_negative`:      int
      - `news_positive`:      int
      - `appeals_count`:      int
      - `appeals_negative_share`: float in [0, 1]
      - `business_delta`:     float in [-2, 2] (optional economic signal)
      - `happiness_index`:    float in [0, 1]
      - `trust_index`:        float in [0, 1]
      - `forecast_signal`:    float in [-1, 1], output of Meister prediction

    Anything missing is treated as "no signal" (contribution 0, but the
    source is listed in `missing_sources` so the UI can badge it).
    """
    if vector not in _WEIGHTS:
        raise ValueError(f"unknown vector {vector!r}")

    weights = _WEIGHTS[vector]
    components: List[Component] = []
    missing: List[str] = []

    for source, weight in weights.items():
        raw, detail = _signal_for(vector, source, context)
        if raw is None:
            missing.append(source)
            raw = 0.0
            detail = "нет данных"
        contribution = weight * raw
        components.append(
            Component(
                source=source,
                label=_SOURCE_LABELS.get(source, source),
                weight=weight,
                raw=raw,
                contribution=contribution,
                detail=detail,
            )
        )

    final = _BASELINE + sum(c.contribution for c in components)
    final = max(_MIN_VAL, min(_MAX_VAL, final))

    formula = " + ".join(
        f"{c.weight:.1f}×{c.label}" for c in components
    )
    formula = f"{_BASELINE:.1f} (базовая) + {formula}"

    return Breakdown(
        vector=vector,
        vector_label=_VECTOR_LABELS[vector],
        baseline=_BASELINE,
        final=final,
        components=components,
        formula=formula,
        missing_sources=missing,
    )


# ---------------------------------------------------------------------------
# per-source signal extraction — pure, context-in/float-out
# ---------------------------------------------------------------------------

def _signal_for(
    vector: str, source: str, ctx: Dict[str, Any]
) -> tuple[Optional[float], str]:
    """Return `(raw_signal, human_detail)` for a (vector, source) pair.

    `raw_signal` is delta in the 1..6 scale (e.g. +0.5 means a source
    pushes the metric half a point above baseline). `None` if the
    context lacks the data to compute this source.
    """
    if source == "news":
        avg = _safe_float(ctx.get("news_avg_sentiment"))
        count = _safe_int(ctx.get("news_count"))
        if avg is None:
            return None, ""
        # Map sentiment ∈ [-1, +1] to ±1.5 range on the 1..6 scale.
        raw = avg * 1.5
        neg = _safe_int(ctx.get("news_negative")) or 0
        pos = _safe_int(ctx.get("news_positive")) or 0
        return raw, (
            f"тональность {avg:+.2f}, всего {count or 0} новостей "
            f"(негативных {neg}, позитивных {pos})"
        )

    if source == "appeals":
        count = _safe_int(ctx.get("appeals_count"))
        share = _safe_float(ctx.get("appeals_negative_share"))
        if share is None or count == 0 or count is None:
            return None, ""
        # share ∈ [0, 1]; at 0 → +0.4, at 1 → -1.0, linear.
        raw = (0.5 - share) * 2.0 * 0.7
        return raw, (
            f"{count} обращений, {int(share * 100)}% негативных"
        )

    if source == "business":
        delta = _safe_float(ctx.get("business_delta"))
        if delta is None:
            return None, ""
        return max(-2.0, min(2.0, delta)), "показатель бизнес-активности"

    if source == "happiness":
        idx = _safe_float(ctx.get("happiness_index"))
        if idx is None:
            return None, ""
        raw = (idx - 0.5) * 3.0  # 0.5 → 0, 1.0 → +1.5, 0 → -1.5
        return raw, f"индекс счастья {int(idx * 100)}%"

    if source == "trust":
        idx = _safe_float(ctx.get("trust_index"))
        if idx is None:
            return None, ""
        raw = (idx - 0.5) * 3.0
        return raw, f"индекс доверия {int(idx * 100)}%"

    if source == "forecast":
        sig = _safe_float(ctx.get("forecast_signal"))
        if sig is None:
            return None, ""
        raw = sig * 1.2
        return raw, f"прогноз Мейстера {sig:+.2f}"

    return None, ""


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
