"""Linear forecast over a metric timeseries.

Given points like [(ts, 3.5), (ts+1d, 3.7), …] fits an ordinary least
squares line and projects it `days_ahead` days forward. Pure, no I/O.

We deliberately use the simplest model: 14–30 days of history can't
support a seasonal or ARIMA fit without overfitting. Once we have a
year of data the plan is to swap this for Prophet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence, Tuple


Point = Tuple[datetime, float]


@dataclass
class ForecastResult:
    horizon_days: int
    projected_value: float
    slope_per_day: float
    points_used: int


def _to_seconds_axis(points: Sequence[Point]) -> Tuple[List[float], List[float], datetime]:
    anchor = points[0][0]
    xs = [(p[0] - anchor).total_seconds() / 86400.0 for p in points]
    ys = [float(p[1]) for p in points]
    return xs, ys, anchor


def linear_forecast(points: Sequence[Point], days_ahead: int = 90) -> Optional[ForecastResult]:
    """Fit OLS on `points` and return the projected value. None if input
    doesn't support a fit (too short, zero x-variance)."""
    if len(points) < 3:
        return None
    xs, ys, _ = _to_seconds_axis(points)
    n = len(points)
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n))
    den = sum((xs[i] - x_mean) ** 2 for i in range(n))
    if den == 0:
        return None
    slope = num / den
    intercept = y_mean - slope * x_mean
    t_future = xs[-1] + days_ahead
    projected = intercept + slope * t_future
    return ForecastResult(
        horizon_days=days_ahead,
        projected_value=round(projected, 2),
        slope_per_day=round(slope, 4),
        points_used=n,
    )


def summarise(
    vector_label: str,
    current: float,
    forecast: Optional[ForecastResult],
) -> str:
    """Compact human-readable summary line for a single vector."""
    if forecast is None:
        return f"{vector_label}: недостаточно истории для прогноза"
    delta = forecast.projected_value - current
    direction = "вырастет" if delta > 0.1 else ("снизится" if delta < -0.1 else "останется стабильной")
    return (
        f"{vector_label}: через {forecast.horizon_days} дней {direction} "
        f"до {forecast.projected_value:.1f}/6 (тренд {forecast.slope_per_day:+.2f}/день)"
    )


def build_forecast_block(
    vector_histories: dict,
    days_ahead: int = 90,
) -> dict:
    """Turn a `{vector: [(ts, value), …]}` dict into the forecast_3m block.

    Output shape matches what `/all_metrics` serves today:
        {"summary": "...", "recommendation": "..."}

    Recommendation is a simple rule-of-thumb from the biggest projected
    drop across vectors; if nothing is forecast to drop materially we
    recommend staying the course.
    """
    labels = {"sb": "Безопасность", "tf": "Экономика", "ub": "Качество жизни", "chv": "Соц. капитал"}
    lines: List[str] = []
    deltas: dict = {}

    for key, pts in vector_histories.items():
        if not pts:
            continue
        current = pts[-1][1]
        forecast = linear_forecast(pts, days_ahead=days_ahead)
        lines.append(summarise(labels.get(key, key), current, forecast))
        if forecast is not None:
            deltas[key] = forecast.projected_value - current

    if not lines:
        return {
            "summary": "Недостаточно истории для прогноза — соберите ещё несколько дней данных.",
            "recommendation": "",
        }

    worst_key = min(deltas, key=deltas.get) if deltas else None
    worst_delta = deltas.get(worst_key, 0) if worst_key else 0
    if worst_key and worst_delta < -0.3:
        recommendation = (
            f"Критически: вектор «{labels.get(worst_key, worst_key)}» теряет "
            f"{abs(worst_delta):.1f} пунктов за квартал — требуются точечные интервенции."
        )
    elif worst_key and worst_delta < -0.1:
        recommendation = (
            f"Следить за вектором «{labels.get(worst_key, worst_key)}» — умеренный спад."
        )
    else:
        recommendation = "Траектория стабильна, можно концентрироваться на развитии, а не на стабилизации."

    return {"summary": " · ".join(lines), "recommendation": recommendation}
