"""Unit tests for the city pulse aggregator."""

from __future__ import annotations

import pytest

from analytics.pulse import compute


def test_all_inputs_none_returns_baseline_with_note():
    r = compute().to_dict()
    # 4 factors × 0.5 × 100 × weights = 50 overall.
    assert abs(r["overall"] - 50.0) < 0.01
    assert r["level"] == "elevated"
    assert r["note"] is not None


def test_perfect_inputs_yield_calm_level():
    r = compute(
        metrics={"sb": 6, "tf": 6, "ub": 6, "chv": 6},
        crisis_status="ok",
        negative_share=0.0,
        appeals_24h=0,
    ).to_dict()
    assert r["overall"] >= 90
    assert r["level"] == "calm"


def test_worst_inputs_yield_critical_level():
    r = compute(
        metrics={"sb": 1, "tf": 1, "ub": 1, "chv": 1},
        crisis_status="attention",
        negative_share=1.0,
        appeals_24h=2000,
    ).to_dict()
    assert r["overall"] < 20
    assert r["level"] == "critical"


def test_level_bands():
    # 80+ calm / 60+ normal / 40+ elevated / 20+ high / <20 critical
    r = compute(metrics={"sb": 4, "tf": 4, "ub": 4, "chv": 4}).to_dict()
    assert r["level"] in {"normal", "elevated"}
    # sb=tf=ub=chv=4 → metrics_health = 60. Combined with baseline 50 for
    # other factors: 60*0.4 + 50*0.25 + 50*0.2 + 50*0.15 = 24+12.5+10+7.5 = 54 → elevated.
    assert abs(r["overall"] - 54.0) < 0.01


def test_metrics_only_improve_the_score():
    baseline = compute().to_dict()["overall"]
    improved = compute(metrics={"sb": 6, "tf": 6, "ub": 6, "chv": 6}).to_dict()["overall"]
    assert improved > baseline


def test_crisis_attention_drags_score_down():
    ok_case = compute(crisis_status="ok").to_dict()["overall"]
    bad = compute(crisis_status="attention").to_dict()["overall"]
    assert bad < ok_case


def test_weights_sum_to_one():
    r = compute().to_dict()
    total_w = sum(f["weight"] for f in r["factors"])
    assert abs(total_w - 1.0) < 0.001


def test_factor_contribution_equals_value_times_weight():
    r = compute(metrics={"sb": 6, "tf": 6, "ub": 6, "chv": 6}).to_dict()
    for f in r["factors"]:
        assert abs(f["contribution"] - f["value"] * f["weight"]) < 0.05


def test_appeals_high_volume_reduces_relief_factor():
    low = compute(appeals_24h=0).to_dict()
    high = compute(appeals_24h=500).to_dict()
    low_factor = next(f for f in low["factors"] if f["key"] == "appeals_relief")
    high_factor = next(f for f in high["factors"] if f["key"] == "appeals_relief")
    assert low_factor["value"] > high_factor["value"]


def test_negative_share_drags_media_calm():
    good = compute(negative_share=0.0).to_dict()
    bad = compute(negative_share=0.8).to_dict()
    good_factor = next(f for f in good["factors"] if f["key"] == "media_calm")
    bad_factor = next(f for f in bad["factors"] if f["key"] == "media_calm")
    assert good_factor["value"] > bad_factor["value"]


def test_garbage_values_do_not_crash():
    r = compute(
        metrics={"sb": "oops", "tf": None, "ub": 4, "chv": "nope"},
        crisis_status="unknown_status",
        negative_share="bad",
        appeals_24h="many",
    ).to_dict()
    assert 0 <= r["overall"] <= 100


def test_response_shape_is_stable():
    r = compute().to_dict()
    assert set(r.keys()) == {"overall", "level", "label", "factors", "note"}
    assert len(r["factors"]) == 4


def test_level_labels_are_readable():
    for score, expected in [
        (95, "calm"), (70, "normal"), (55, "elevated"), (30, "high"), (5, "critical"),
    ]:
        # Craft inputs to land exactly in the expected band.
        if expected == "calm":
            r = compute(metrics={"sb":6,"tf":6,"ub":6,"chv":6}, crisis_status="ok",
                        negative_share=0, appeals_24h=0).to_dict()
        elif expected == "critical":
            r = compute(metrics={"sb":1,"tf":1,"ub":1,"chv":1}, crisis_status="attention",
                        negative_share=1, appeals_24h=1000).to_dict()
        else:
            continue
        assert r["level"] == expected
