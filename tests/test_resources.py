"""Unit tests for the resource planner."""

from __future__ import annotations

import pytest

from analytics.resources import plan


def test_empty_input_uses_baseline_and_attaches_note():
    p = plan().to_dict()
    # 4 × 22.5% + 10% = 100% sanity check.
    shares = sum(a["recommended_share"] for a in p["allocations"])
    assert shares == pytest.approx(0.9, abs=0.001)
    assert p["reserve_share"] == pytest.approx(0.1)
    assert p["note"] is not None  # no metrics


def test_shares_and_reserve_sum_to_one():
    p = plan(
        current_metrics={"sb": 4.0, "tf": 4.0, "ub": 4.0, "chv": 4.0},
    ).to_dict()
    total = sum(a["recommended_share"] for a in p["allocations"]) + p["reserve_share"]
    assert total == pytest.approx(1.0, abs=0.001)


def test_low_score_vector_gets_bigger_share_than_high_score():
    # sb is weakest, chv strongest — sb should win more share than chv.
    p = plan(
        current_metrics={"sb": 2.0, "tf": 4.0, "ub": 4.0, "chv": 5.5},
    ).to_dict()
    by_key = {a["key"]: a for a in p["allocations"]}
    assert by_key["safety"]["recommended_share"] > by_key["social"]["recommended_share"]


def test_crisis_alert_boosts_affected_vector():
    # Without crisis.
    clean = plan(
        current_metrics={"sb": 4.0, "tf": 4.0, "ub": 4.0, "chv": 4.0},
    ).to_dict()
    # With crisis on safety.
    crisis = plan(
        current_metrics={"sb": 4.0, "tf": 4.0, "ub": 4.0, "chv": 4.0},
        crisis_alerts=[{"vector": "safety", "level": "high"}],
    ).to_dict()
    clean_safety  = next(a["recommended_share"] for a in clean["allocations"]  if a["key"] == "safety")
    crisis_safety = next(a["recommended_share"] for a in crisis["allocations"] if a["key"] == "safety")
    assert crisis_safety > clean_safety
    crisis_alloc = next(a for a in crisis["allocations"] if a["key"] == "safety")
    assert crisis_alloc["has_crisis"] is True
    assert crisis_alloc["priority"] == "critical"


def test_priority_buckets():
    p = plan(current_metrics={"sb": 2.0, "tf": 3.0, "ub": 4.0, "chv": 5.5}).to_dict()
    by_key = {a["key"]: a for a in p["allocations"]}
    assert by_key["safety"]["priority"]  == "critical"  # score ≤ 2.5
    assert by_key["economy"]["priority"] == "high"      # score ≤ 3.5
    assert by_key["quality"]["priority"] == "medium"    # score ≤ 4.5
    assert by_key["social"]["priority"]  == "low"       # score > 4.5


def test_total_budget_uses_population_times_per_capita():
    p = plan(population=100_000, per_capita_rub=30_000).to_dict()
    assert p["total_budget_rub"] == 100_000 * 30_000
    assert p["population"] == 100_000
    assert p["per_capita_rub"] == 30_000


def test_missing_population_falls_back_to_default():
    p = plan().to_dict()
    assert p["population"] == 50_000   # default town-size fallback
    assert p["total_budget_rub"] > 0


def test_reserve_rub_equals_reserve_share_times_total():
    p = plan(population=200_000, per_capita_rub=30_000).to_dict()
    expected = round(p["reserve_share"] * p["total_budget_rub"])
    assert abs(p["reserve_rub"] - expected) <= 1  # integer rounding slack


def test_sum_of_rub_plus_reserve_equals_total_within_rounding():
    p = plan(population=140_000, per_capita_rub=30_000).to_dict()
    alloc_sum = sum(a["recommended_rub"] for a in p["allocations"])
    total = alloc_sum + p["reserve_rub"]
    # Integer rounding errors up to 4 rub total (4 vectors + reserve rounded).
    assert abs(total - p["total_budget_rub"]) <= 5


def test_vector_without_data_uses_baseline_share():
    # Only sb is provided — other vectors should get their 22.5% × scale.
    p = plan(current_metrics={"sb": 4.0}).to_dict()
    by_key = {a["key"]: a for a in p["allocations"]}
    # Economy/quality/social have score=None → no adjustments. After
    # renormalisation they still equal each other.
    assert by_key["economy"]["recommended_share"] == pytest.approx(by_key["quality"]["recommended_share"], abs=0.0001)
    assert by_key["economy"]["recommended_share"] == pytest.approx(by_key["social"]["recommended_share"], abs=0.0001)


def test_extreme_low_score_does_not_exceed_total_budget():
    p = plan(current_metrics={"sb": 1.0, "tf": 1.0, "ub": 1.0, "chv": 1.0}).to_dict()
    # Even with all vectors screaming, their shares should still sum to (1 - reserve).
    shares = sum(a["recommended_share"] for a in p["allocations"])
    assert shares == pytest.approx(0.9, abs=0.001)


def test_garbage_values_do_not_crash():
    p = plan(
        current_metrics={"sb": "oops", "tf": None, "ub": 4.0, "chv": "nope"},
        crisis_alerts=[
            "not a dict",
            {"vector": "unknown"},
            {"vector": "safety"},  # valid
        ],
        population="big",
    ).to_dict()
    assert len(p["allocations"]) == 4
    safety = next(a for a in p["allocations"] if a["key"] == "safety")
    assert safety["has_crisis"] is True


def test_no_vector_is_dropped_below_5_percent():
    # Artificially high scores would trim shares — floor of 5% per vector
    # should kick in before the renormalisation step.
    p = plan(current_metrics={"sb": 6.0, "tf": 6.0, "ub": 6.0, "chv": 6.0}).to_dict()
    for a in p["allocations"]:
        assert a["recommended_share"] >= 0.04   # ≥5% raw, post-scale slightly lower but > 4%
