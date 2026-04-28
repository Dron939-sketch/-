"""Unit tests for the deep-forecast adapter."""

from __future__ import annotations

import pytest

from analytics.deep_forecast import forecast


def test_empty_history_attaches_note_and_uses_flat_baseline():
    r = forecast().to_dict()
    assert r["note"] is not None
    assert len(r["vectors"]) == 4
    for v in r["vectors"]:
        assert v["method"] == "insufficient_data"
        # Flat baseline at 3.5 ± wide band.
        assert v["forecasts"]["7"]["point"] == pytest.approx(3.5, abs=0.01)


def test_flat_method_when_single_sample():
    r = forecast({"safety": [4.0]}).to_dict()
    safety = next(v for v in r["vectors"] if v["key"] == "safety")
    assert safety["method"] == "flat"
    assert safety["samples_used"] == 1
    assert safety["forecasts"]["7"]["point"] == pytest.approx(4.0, abs=0.01)


def test_trend_method_when_few_samples():
    r = forecast({"safety": [3.0, 3.5, 4.0]}).to_dict()
    safety = next(v for v in r["vectors"] if v["key"] == "safety")
    assert safety["method"] == "trend"
    # Upward trend → 7-day forecast should be above the last observed value.
    assert safety["forecasts"]["7"]["point"] > 4.0


def test_holt_method_when_enough_samples():
    series = [3.0, 3.1, 3.3, 3.5, 3.7, 4.0, 4.2]
    r = forecast({"safety": series}).to_dict()
    safety = next(v for v in r["vectors"] if v["key"] == "safety")
    assert safety["method"] == "holt"
    assert safety["samples_used"] == 7


def test_lower_is_less_than_upper_and_both_clamp_to_scale():
    series = [5.0] * 20   # stable at 5.0
    r = forecast({"safety": series}).to_dict()
    safety = next(v for v in r["vectors"] if v["key"] == "safety")
    for horizon in ("7", "30", "90"):
        f = safety["forecasts"][horizon]
        assert f["lower"] <= f["point"] <= f["upper"]
        assert 1.0 <= f["lower"] <= 6.0
        assert 1.0 <= f["upper"] <= 6.0


def test_band_widens_with_horizon():
    # Use noisy series so residual_std is large enough that band scales
    # beyond the 0.2 floor → monotone growth with horizon is visible.
    series = [3.5, 2.5, 4.5, 3.0, 4.0, 2.8, 4.2, 3.1, 4.1, 3.3]
    r = forecast({"safety": series}).to_dict()
    safety = next(v for v in r["vectors"] if v["key"] == "safety")
    b7  = safety["forecasts"]["7"]["upper"]  - safety["forecasts"]["7"]["lower"]
    b30 = safety["forecasts"]["30"]["upper"] - safety["forecasts"]["30"]["lower"]
    # 30d band strictly wider than 7d band (use tolerance for float arithmetic).
    assert b30 > b7 - 0.01


def test_accepts_db_column_keys():
    # Provide history keyed by db columns (sb / tf), not vector keys.
    r = forecast({
        "sb":  [3.0, 3.1, 3.2],
        "tf":  [4.0, 4.0, 4.0],
        "ub":  [5.0, 5.1, 5.2],
        "chv": [2.5, 2.5, 2.5],
    }).to_dict()
    by_key = {v["key"]: v for v in r["vectors"]}
    assert by_key["safety"]["current"] == pytest.approx(3.2, abs=0.01)
    assert by_key["quality"]["current"] == pytest.approx(5.2, abs=0.01)
    assert by_key["social"]["method"] == "trend"


def test_accepts_tuple_history_entries():
    # metrics_history returns (ts, value) tuples.
    r = forecast({"safety": [("2024-01-01", 3.0), ("2024-01-02", 3.5), ("2024-01-03", 4.0)]}).to_dict()
    safety = next(v for v in r["vectors"] if v["key"] == "safety")
    assert safety["samples_used"] == 3
    assert safety["current"] == pytest.approx(4.0, abs=0.01)


def test_garbage_values_skipped():
    r = forecast({"safety": ["bad", 4.0, None, 4.5, "nope"]}).to_dict()
    safety = next(v for v in r["vectors"] if v["key"] == "safety")
    assert safety["samples_used"] == 2
    assert safety["current"] == pytest.approx(4.5, abs=0.01)


def test_forecast_confidence_ladder():
    low = forecast({"safety": [4.0, 4.0]}).to_dict()
    mid = forecast({"safety": [4.0, 4.1, 4.2]}).to_dict()
    high = forecast({"safety": [4.0 + 0.05 * i for i in range(15)]}).to_dict()
    assert next(v for v in low["vectors"] if v["key"] == "safety")["confidence"] == "low"
    assert next(v for v in mid["vectors"] if v["key"] == "safety")["confidence"] == "medium"
    assert next(v for v in high["vectors"] if v["key"] == "safety")["confidence"] == "high"


def test_output_includes_all_four_vectors_even_when_history_missing_some():
    r = forecast({"safety": [4.0] * 7}).to_dict()
    keys = {v["key"] for v in r["vectors"]}
    assert keys == {"safety", "economy", "quality", "social"}


def test_point_stays_in_scale_for_strong_trends():
    # Strong upward trend — 90-day projection would blow past 6 but should clamp.
    series = [1.0 + 0.3 * i for i in range(10)]
    r = forecast({"safety": series}).to_dict()
    safety = next(v for v in r["vectors"] if v["key"] == "safety")
    assert 1.0 <= safety["forecasts"]["90"]["point"] <= 6.0


def test_horizons_shape_stable():
    r = forecast({"safety": [4.0] * 7}).to_dict()
    assert r["horizons_days"] == [7, 30, 90]
    safety = next(v for v in r["vectors"] if v["key"] == "safety")
    assert set(safety["forecasts"].keys()) == {"7", "30", "90"}
