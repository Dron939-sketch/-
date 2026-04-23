"""Probabilistic near-term forecast (ТЗ §18, MVP adapter).

Per-vector point forecast + confidence band at 7 / 30 / 90 days ahead,
computed from the recent metrics history. Uses a Holt-style additive
trend smoothing with residual-based uncertainty bands — no TensorFlow,
no sklearn, no training. Pure and testable.

Method ladder (picked per vector based on available history):

  holt    ≥ 6 samples: trend + level via double exponential smoothing.
  trend   ≥ 3 samples: naive linear regression on sample index.
  flat    < 3 samples: constant at the last known value + wide band.

The legacy `deep_forecast.py` (LSTM + Transformer from TensorFlow) needs
a trained model + ~1000+ labelled samples — the 6 pilot cities in their
first weeks have nowhere near that. When a real corpus accumulates, the
Holt path can be swapped for a learned model without changing the API.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


_CLAMP_MIN = 1.0
_CLAMP_MAX = 6.0
_VECTORS = ("safety", "economy", "quality", "social")
_METRIC_COLUMN = {"safety": "sb", "economy": "tf", "quality": "ub", "social": "chv"}

_HOLT_ALPHA = 0.5     # level smoothing
_HOLT_BETA  = 0.3     # trend smoothing

# Horizons (days) we emit.
_HORIZONS = (7, 30, 90)


@dataclass
class VectorForecast:
    key: str
    current: Optional[float]
    method: str                     # holt | trend | flat | insufficient_data
    confidence: str                 # high | medium | low
    samples_used: int
    forecasts: Dict[int, Dict[str, float]]   # {days: {point, lower, upper}}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "current": round(self.current, 2) if self.current is not None else None,
            "method": self.method,
            "confidence": self.confidence,
            "samples_used": int(self.samples_used),
            "forecasts": {
                str(d): {
                    "point": round(v["point"], 2),
                    "lower": round(v["lower"], 2),
                    "upper": round(v["upper"], 2),
                }
                for d, v in self.forecasts.items()
            },
        }


@dataclass
class DeepForecastReport:
    horizons_days: List[int]
    vectors: List[VectorForecast]
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "horizons_days": list(self.horizons_days),
            "vectors": [v.to_dict() for v in self.vectors],
            "note": self.note,
        }


def forecast(
    history: Optional[Dict[str, List[float]]] = None,
) -> DeepForecastReport:
    """Build per-vector forecasts from metric history.

    `history` keys are vector keys (safety / economy / quality / social)
    OR db columns (sb / tf / ub / chv) — both are accepted. Values are
    lists of scalar metrics in chronological order.
    """
    history = history or {}
    vectors_out: List[VectorForecast] = []

    for vkey in _VECTORS:
        series = _pick_series(history, vkey)
        vectors_out.append(_forecast_one(vkey, series))

    note = None
    if not any(v.samples_used for v in vectors_out):
        note = "Исторических данных нет — показан flat-прогноз baseline 3.5."

    return DeepForecastReport(
        horizons_days=list(_HORIZONS),
        vectors=vectors_out,
        note=note,
    )


# ---------------------------------------------------------------------------
# per-vector forecasting
# ---------------------------------------------------------------------------

def _forecast_one(key: str, series: List[float]) -> VectorForecast:
    n = len(series)
    current = series[-1] if series else None

    if n >= 6:
        point_fn, residual_std = _holt(series)
        method, confidence = "holt", ("high" if n >= 14 else "medium")
    elif n >= 3:
        point_fn, residual_std = _trend(series)
        method, confidence = "trend", "medium"
    elif n >= 1:
        point_fn, residual_std = _flat(series)
        method, confidence = "flat", "low"
    else:
        point_fn, residual_std = (lambda _d: 3.5), 0.8
        method, confidence = "insufficient_data", "low"

    forecasts: Dict[int, Dict[str, float]] = {}
    for h in _HORIZONS:
        point = _clamp(point_fn(h))
        # Band widens with sqrt(horizon) — typical for random-walk style bounds.
        band = max(0.2, residual_std * math.sqrt(max(1, h / 7.0)))
        forecasts[h] = {
            "point": point,
            "lower": _clamp(point - band),
            "upper": _clamp(point + band),
        }

    return VectorForecast(
        key=key,
        current=current,
        method=method,
        confidence=confidence,
        samples_used=n,
        forecasts=forecasts,
    )


def _holt(series: List[float]) -> Tuple[Any, float]:
    """Double exponential smoothing. Returns (predict_fn, residual_std)."""
    level = series[0]
    trend = series[1] - series[0] if len(series) > 1 else 0.0
    fitted: List[float] = [level]
    for value in series[1:]:
        prev_level = level
        level = _HOLT_ALPHA * value + (1 - _HOLT_ALPHA) * (level + trend)
        trend = _HOLT_BETA * (level - prev_level) + (1 - _HOLT_BETA) * trend
        fitted.append(level)

    residuals = [series[i] - fitted[i] for i in range(len(series))]
    residual_std = _stdev(residuals) or 0.15

    # Day-ahead forecast: level + trend × days (trend is per-sample ≈ per-day).
    def _predict(days: int) -> float:
        return level + trend * days

    return _predict, residual_std


def _trend(series: List[float]) -> Tuple[Any, float]:
    """Simple linear regression on sample index."""
    n = len(series)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(series) / n
    num = sum((xs[i] - mean_x) * (series[i] - mean_y) for i in range(n))
    den = sum((x - mean_x) ** 2 for x in xs) or 1.0
    slope = num / den
    intercept = mean_y - slope * mean_x
    last_index = n - 1

    residuals = [series[i] - (intercept + slope * xs[i]) for i in range(n)]
    residual_std = _stdev(residuals) or 0.2

    def _predict(days: int) -> float:
        return intercept + slope * (last_index + days)

    return _predict, residual_std


def _flat(series: List[float]) -> Tuple[Any, float]:
    """No trend information — return the last value with a wide band."""
    last = series[-1]

    def _predict(_days: int) -> float:
        return last

    return _predict, 0.6


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _pick_series(history: Dict[str, Any], vkey: str) -> List[float]:
    """Accept either vector-key or db-column keying in the history dict."""
    raw = history.get(vkey)
    if raw is None:
        raw = history.get(_METRIC_COLUMN.get(vkey, ""))
    if raw is None:
        return []
    out: List[float] = []
    for item in raw:
        # Accept plain floats, tuples (ts, value) — we only need the numbers.
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            item = item[1]
        try:
            out.append(float(item))
        except (TypeError, ValueError):
            continue
    return out


def _stdev(values: Iterable[float]) -> float:
    xs = list(values)
    n = len(xs)
    if n < 2:
        return 0.0
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    return math.sqrt(max(0.0, var))


def _clamp(v: float) -> float:
    try:
        return max(_CLAMP_MIN, min(_CLAMP_MAX, float(v)))
    except (TypeError, ValueError):
        return 3.5
