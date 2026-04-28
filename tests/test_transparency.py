"""Offline tests for the metric-transparency breakdown."""

from __future__ import annotations

import pytest

from analytics.transparency import _WEIGHTS, breakdown


def test_weights_sum_to_one_for_every_vector():
    """ТЗ §3.1 says weights always sum to 1.0."""
    for vector, ws in _WEIGHTS.items():
        assert abs(sum(ws.values()) - 1.0) < 1e-9, f"{vector} weights don't sum to 1.0"


def test_unknown_vector_raises():
    with pytest.raises(ValueError):
        breakdown("made_up", {})


def test_empty_context_marks_all_sources_missing():
    result = breakdown("safety", {}).to_dict()
    assert result["final"] == 3.5  # baseline
    assert set(result["missing_sources"]) == {"news", "appeals", "forecast"}
    # Every component has zero contribution.
    assert all(c["contribution"] == 0.0 for c in result["components"])


def test_positive_news_pushes_safety_above_baseline():
    ctx = {
        "news_avg_sentiment": 0.6,
        "news_count": 10,
        "news_negative": 1,
        "news_positive": 7,
    }
    result = breakdown("safety", ctx).to_dict()
    news = next(c for c in result["components"] if c["source"] == "news")
    # sentiment 0.6 → raw 0.9 → contribution 0.9 × 0.4 = 0.36
    assert news["raw"] == 0.9
    assert news["contribution"] == 0.36
    assert result["final"] > 3.5


def test_negative_news_and_appeals_both_drag_safety_down():
    ctx = {
        "news_avg_sentiment": -0.4,
        "news_count": 8,
        "news_negative": 5,
        "news_positive": 0,
        "appeals_count": 12,
        "appeals_negative_share": 0.75,
    }
    result = breakdown("safety", ctx).to_dict()
    assert result["final"] < 3.5
    # Appeals at 75% negative: raw = (0.5 - 0.75) × 2 × 0.7 = -0.35
    appeals = next(c for c in result["components"] if c["source"] == "appeals")
    assert appeals["raw"] == pytest.approx(-0.35, abs=0.01)


def test_happiness_signal_feeds_quality_vector():
    ctx = {"happiness_index": 0.8}
    result = breakdown("quality", ctx).to_dict()
    happiness = next(c for c in result["components"] if c["source"] == "happiness")
    # (0.8 - 0.5) × 3.0 = 0.9 × 0.4 = 0.36
    assert happiness["raw"] == pytest.approx(0.9, abs=0.01)
    assert happiness["contribution"] == pytest.approx(0.36, abs=0.01)


def test_trust_signal_feeds_social_vector():
    ctx = {"trust_index": 0.2}
    result = breakdown("social", ctx).to_dict()
    trust = next(c for c in result["components"] if c["source"] == "trust")
    # (0.2 - 0.5) × 3.0 = -0.9 × 0.5 = -0.45
    assert trust["raw"] == pytest.approx(-0.9, abs=0.01)
    assert trust["contribution"] == pytest.approx(-0.45, abs=0.01)


def test_final_is_clamped_to_1_6_range():
    # Maximal positive signals.
    ctx = {
        "news_avg_sentiment": 1.0,
        "news_count": 100,
        "happiness_index": 1.0,
        "forecast_signal": 1.0,
    }
    result = breakdown("quality", ctx).to_dict()
    assert result["final"] <= 6.0
    assert result["final"] > 3.5


def test_forecast_signal_uses_weight_02_for_economy():
    ctx = {"forecast_signal": 0.5}
    result = breakdown("economy", ctx).to_dict()
    forecast = next(c for c in result["components"] if c["source"] == "forecast")
    # raw = 0.5 × 1.2 = 0.6, weight = 0.2 → contribution 0.12
    assert forecast["raw"] == pytest.approx(0.6, abs=0.01)
    assert forecast["weight"] == 0.2
    assert forecast["contribution"] == pytest.approx(0.12, abs=0.01)


def test_each_vector_has_three_components_in_output():
    for vector in ("safety", "economy", "quality", "social"):
        out = breakdown(vector, {}).to_dict()
        assert len(out["components"]) == 3
        # Formula includes the vector's source labels.
        assert "3.5 (базовая)" in out["formula"]


def test_human_detail_shows_news_counts():
    ctx = {
        "news_avg_sentiment": -0.2,
        "news_count": 5,
        "news_negative": 3,
        "news_positive": 1,
    }
    news = next(
        c for c in breakdown("safety", ctx).to_dict()["components"]
        if c["source"] == "news"
    )
    assert "5 новостей" in news["detail"]
    assert "негативных 3" in news["detail"]


def test_vector_labels_use_russian_names():
    for vector, expected in (
        ("safety", "Безопасность"),
        ("economy", "Экономика"),
        ("quality", "Качество"),
        ("social", "Социальный"),
    ):
        out = breakdown(vector, {}).to_dict()
        assert expected in out["vector_label"]
