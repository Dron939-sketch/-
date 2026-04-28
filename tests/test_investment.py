"""Unit tests for the investment-attractiveness analyzer."""

from __future__ import annotations

import pytest

from analytics.investment import compute


def test_empty_signals_returns_baseline_with_note():
    p = compute().to_dict()
    # Each factor defaults to 0.5, so overall ≈ 50.
    assert 45 <= p["overall_index"] <= 55
    assert p["grade"] in {"C+", "C", "B"}
    assert p["note"] is not None
    assert len(p["factors"]) == 6


def test_perfect_city_gets_a_plus_grade():
    p = compute({
        "sb": 6.0, "tf": 6.0, "ub": 6.0, "chv": 6.0,
        "trust_index": 1.0, "happiness_index": 1.0,
        "population": 250_000,
        "peer_rank": {"position": 1, "total": 6, "leader_slug": "a"},
        "crisis_status": "ok",
        "business_news_positive": 10, "business_news_negative": 0,
    }).to_dict()
    assert p["overall_index"] >= 85
    assert p["grade"] == "A+"


def test_crisis_drops_stability_factor():
    base = compute({
        "sb": 4.0, "tf": 4.0, "ub": 4.0, "chv": 4.0,
        "crisis_status": "ok",
    }).to_dict()
    crisis = compute({
        "sb": 4.0, "tf": 4.0, "ub": 4.0, "chv": 4.0,
        "crisis_status": "attention",
    }).to_dict()
    assert crisis["overall_index"] < base["overall_index"]
    # Stability factor value should be much lower in crisis.
    b = {f["key"]: f for f in base["factors"]}
    c = {f["key"]: f for f in crisis["factors"]}
    assert c["stability"]["value"] < b["stability"]["value"]


def test_peer_rank_leader_boosts_market_access():
    leader = compute({
        "population": 150_000,
        "peer_rank": {"position": 1, "total": 6},
    }).to_dict()
    laggard = compute({
        "population": 150_000,
        "peer_rank": {"position": 6, "total": 6},
    }).to_dict()
    leader_ma = next(f for f in leader["factors"] if f["key"] == "market_access")
    laggard_ma = next(f for f in laggard["factors"] if f["key"] == "market_access")
    assert leader_ma["value"] > laggard_ma["value"]


def test_small_population_lowers_market_access():
    big = compute({"population": 250_000}).to_dict()
    small = compute({"population": 20_000}).to_dict()
    big_ma = next(f for f in big["factors"] if f["key"] == "market_access")
    small_ma = next(f for f in small["factors"] if f["key"] == "market_access")
    assert big_ma["value"] > small_ma["value"]


def test_business_news_polarity_tweaks_economy_factor():
    positive = compute({
        "tf": 4.0,
        "business_news_positive": 10, "business_news_negative": 0,
    }).to_dict()
    negative = compute({
        "tf": 4.0,
        "business_news_positive": 0, "business_news_negative": 10,
    }).to_dict()
    pos_econ = next(f for f in positive["factors"] if f["key"] == "economic_climate")
    neg_econ = next(f for f in negative["factors"] if f["key"] == "economic_climate")
    assert pos_econ["value"] > neg_econ["value"]


def test_strengths_list_only_factors_above_50_percent():
    p = compute({
        "sb": 6.0, "tf": 2.0, "ub": 6.0, "chv": 2.0,
        "trust_index": 0.2, "happiness_index": 0.9,
        "population": 150_000,
        "peer_rank": {"position": 1, "total": 6},
        "crisis_status": "ok",
    }).to_dict()
    # Strengths should be present, weaknesses too (TF is low).
    assert len(p["strengths"]) >= 1
    assert len(p["weaknesses"]) >= 1
    # Strengths show factor label + percentage format.
    assert "%" in p["strengths"][0]


def test_weights_sum_to_one():
    p = compute({"sb": 4.0}).to_dict()
    total_weight = sum(f["weight"] for f in p["factors"])
    assert total_weight == pytest.approx(1.0, abs=0.001)


def test_garbage_values_do_not_crash():
    p = compute({
        "sb": "oops",
        "tf": None,
        "happiness_index": "nope",
        "population": "big",
        "peer_rank": "broken",
    }).to_dict()
    assert 0 <= p["overall_index"] <= 100
    assert p["grade"] in {"A+", "A", "B+", "B", "C+", "C", "D"}


def test_contribution_equals_weight_times_value_times_hundred():
    p = compute({"sb": 6.0, "tf": 3.0, "ub": 3.0, "chv": 3.0}).to_dict()
    for f in p["factors"]:
        expected = f["weight"] * f["value"] * 100.0
        assert f["contribution"] == pytest.approx(expected, abs=0.01)


def test_grade_thresholds():
    # Low everything, no bonuses → should be in the C/D band.
    low = compute({
        "sb": 1.0, "tf": 1.0, "ub": 1.0, "chv": 1.0,
        "trust_index": 0.0, "happiness_index": 0.0,
        "population": 15_000,
        "peer_rank": {"position": 6, "total": 6},
        "crisis_status": "attention",
    }).to_dict()
    assert low["grade"] in {"D", "C"}
    assert low["overall_index"] < 40
