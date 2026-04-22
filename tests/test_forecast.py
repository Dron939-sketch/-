"""Tests for the linear forecast."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from metrics.forecast import build_forecast_block, linear_forecast


def _series(slope_per_day: float, n: int = 14, start: float = 3.0):
    base = datetime(2026, 4, 1, tzinfo=timezone.utc)
    return [(base + timedelta(days=i), start + slope_per_day * i) for i in range(n)]


def test_linear_forecast_requires_three_points():
    assert linear_forecast(_series(0.1, n=2)) is None


def test_linear_forecast_projects_upward_slope():
    fc = linear_forecast(_series(0.05, n=14), days_ahead=30)
    assert fc is not None
    # slope ~0.05/day, last x = 13 → projected at x=43, y = 3 + 0.05 * 43 = 5.15
    assert fc.projected_value == pytest.approx(5.15, abs=0.05)
    assert fc.slope_per_day == pytest.approx(0.05, abs=0.001)
    assert fc.points_used == 14


def test_flat_series_projects_the_same_value():
    fc = linear_forecast(_series(0.0, n=10), days_ahead=90)
    assert fc is not None
    assert fc.projected_value == pytest.approx(3.0, abs=0.01)
    assert abs(fc.slope_per_day) < 1e-6


def test_build_forecast_block_returns_lines_and_recommendation():
    histories = {
        "sb":  _series(-0.03, n=14),  # clearly dropping
        "tf":  _series(0.0, n=14),
        "ub":  _series(0.02, n=14),
        "chv": [],
    }
    block = build_forecast_block(histories, days_ahead=90)
    assert "Безопасность" in block["summary"]
    assert "Экономика" in block["summary"]
    # Worst delta is sb = -0.03 * 90 = -2.7 → critical branch
    assert "Критически" in block["recommendation"] or "Следить" in block["recommendation"]


def test_build_forecast_block_empty_histories_returns_sentinel():
    block = build_forecast_block({"sb": [], "tf": [], "ub": [], "chv": []})
    assert "Недостаточно истории" in block["summary"]
    assert block["recommendation"] == ""


def test_build_forecast_block_stable_trend_recommends_developpement():
    histories = {k: _series(0.001, n=14) for k in ("sb", "tf", "ub", "chv")}
    block = build_forecast_block(histories, days_ahead=90)
    assert "стабильн" in block["recommendation"].lower()
