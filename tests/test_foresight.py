"""Unit tests for the 5-year foresight projector."""

from __future__ import annotations

import pytest

from analytics.foresight import forecast


def test_empty_input_returns_three_scenarios_and_ten_megatrends():
    report = forecast().to_dict()
    assert len(report["scenarios"]) == 3
    keys = [s["key"] for s in report["scenarios"]]
    assert keys == ["optimistic", "baseline", "pessimistic"]
    assert len(report["megatrends"]) == 10
    assert report["note"] is not None  # no metrics flag


def test_scenario_probabilities_sum_to_one():
    report = forecast().to_dict()
    total = sum(s["probability"] for s in report["scenarios"])
    assert total == pytest.approx(1.0, abs=0.001)


def test_baseline_year5_equals_current_plus_slope_times_five():
    report = forecast(
        current_metrics={"sb": 3.0, "tf": 4.0, "ub": 4.0, "chv": 4.0},
        trend_per_vector={"safety": 0.2, "economy": 0.0, "quality": 0.0, "social": 0.0},
    ).to_dict()
    baseline = next(s for s in report["scenarios"] if s["key"] == "baseline")
    safety = next(v for v in baseline["vectors"] if v["key"] == "safety")
    # 3.0 + 0.2 × 5 = 4.0 (baseline modifier is 0).
    assert safety["year_5"] == pytest.approx(4.0, abs=0.01)


def test_optimistic_beats_baseline_beats_pessimistic_at_year5():
    current = {"sb": 4.0, "tf": 4.0, "ub": 4.0, "chv": 4.0}
    report = forecast(current_metrics=current).to_dict()
    by_key = {s["key"]: s for s in report["scenarios"]}
    assert by_key["optimistic"]["composite_year_5"] > by_key["baseline"]["composite_year_5"]
    assert by_key["baseline"]["composite_year_5"] > by_key["pessimistic"]["composite_year_5"]


def test_projections_clamped_to_1_6_scale():
    # Strong positive trend should saturate at 6.
    report = forecast(
        current_metrics={"sb": 5.5, "tf": 5.5, "ub": 5.5, "chv": 5.5},
        trend_per_vector={k: 0.5 for k in ("safety", "economy", "quality", "social")},
    ).to_dict()
    for s in report["scenarios"]:
        for v in s["vectors"]:
            assert v["year_5"] <= 6.0

    # Strong negative trend should saturate at 1.
    report = forecast(
        current_metrics={"sb": 1.5, "tf": 1.5, "ub": 1.5, "chv": 1.5},
        trend_per_vector={k: -0.5 for k in ("safety", "economy", "quality", "social")},
    ).to_dict()
    for s in report["scenarios"]:
        for v in s["vectors"]:
            assert v["year_5"] >= 1.0


def test_missing_vector_returns_nulls():
    # Only sb is provided — other vectors come back with null current / projections.
    report = forecast(current_metrics={"sb": 4.0}).to_dict()
    baseline = next(s for s in report["scenarios"] if s["key"] == "baseline")
    by_vector = {v["key"]: v for v in baseline["vectors"]}
    assert by_vector["safety"]["current"] == 4.0
    assert by_vector["economy"]["current"] is None
    assert by_vector["economy"]["year_5"] is None


def test_composite_ignores_missing_vectors():
    report = forecast(current_metrics={"sb": 5.0}).to_dict()
    baseline = next(s for s in report["scenarios"] if s["key"] == "baseline")
    # Only sb present → composite equals sb.
    assert baseline["composite_current"] == pytest.approx(5.0)


def test_megatrends_have_weighted_impact_and_direction():
    report = forecast().to_dict()
    for m in report["megatrends"]:
        # weighted == impact × relevance
        assert m["weighted"] == pytest.approx(m["impact"] * m["relevance"], abs=0.01)
        assert m["direction"] in {"up", "down", "flat"}
        assert -1.0 <= m["impact"] <= 1.0
        assert 0.0 <= m["relevance"] <= 1.0


def test_garbage_values_do_not_crash():
    report = forecast(
        current_metrics={"sb": "oops", "tf": None, "ub": 4.0, "chv": "nope"},
        trend_per_vector={"safety": "bad"},
    ).to_dict()
    baseline = next(s for s in report["scenarios"] if s["key"] == "baseline")
    by_vector = {v["key"]: v for v in baseline["vectors"]}
    assert by_vector["safety"]["current"] is None
    assert by_vector["quality"]["current"] == 4.0


def test_horizon_is_five_years():
    assert forecast().to_dict()["horizon_years"] == 5


def test_positive_trend_moves_year5_higher_than_year1():
    report = forecast(
        current_metrics={"sb": 3.0, "tf": 3.0, "ub": 3.0, "chv": 3.0},
        trend_per_vector={"safety": 0.3, "economy": 0.3, "quality": 0.3, "social": 0.3},
    ).to_dict()
    baseline = next(s for s in report["scenarios"] if s["key"] == "baseline")
    for v in baseline["vectors"]:
        assert v["year_5"] > v["year_3"] > v["year_1"] > v["current"]
