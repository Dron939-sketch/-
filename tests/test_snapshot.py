"""Tests for the pure snapshot aggregator."""

from __future__ import annotations

from datetime import datetime, timezone

from collectors.base import CollectedItem
from metrics.snapshot import snapshot_from_news


def _item(
    category: str, sentiment: float | None = None
) -> CollectedItem:
    return CollectedItem(
        source_kind="telegram",
        source_handle="kolomna_chp",
        title="т",
        content="с",
        published_at=datetime(2026, 4, 22, 8, 0, tzinfo=timezone.utc),
        category=category,
        enrichment=(
            {"sentiment": sentiment, "category": category,
             "severity": 0.4, "summary": ""}
            if sentiment is not None else None
        ),
    )


def test_empty_news_returns_baseline_values():
    out = snapshot_from_news([])
    assert out == {
        "sb": 3.5,
        "tf": 3.5,
        "ub": 3.5,
        "chv": 3.5,
        "trust_index": 0.58,
        "happiness_index": 0.62,
    }


def test_negative_news_drops_safety_vector():
    items = [
        _item("incidents", -0.9),
        _item("utilities", -0.8),
        _item("incidents", -0.7),
    ]
    out = snapshot_from_news(items)
    assert out["sb"] < 2.0  # well below the 3.5 baseline
    # Trust drops because 100% of items are "negative" categories.
    assert out["trust_index"] <= 0.25


def test_positive_culture_news_raises_chv_and_happiness():
    items = [_item("culture", 0.7), _item("sport", 0.9)]
    out = snapshot_from_news(items)
    assert out["chv"] > 4.5
    # Both items are positive categories → happiness clearly above baseline.
    assert out["happiness_index"] > 0.7


def test_items_without_enrichment_fall_through_with_baseline():
    items = [_item("incidents", sentiment=None), _item("culture", sentiment=None)]
    out = snapshot_from_news(items)
    # No sentiment → vector stays at baseline for each relevant cat.
    assert out["sb"] == 3.5
    assert out["chv"] == 3.5
    # But the counts still move trust/happiness.
    # negative=1, positive=1, total=2 → delta 0 → happiness 0.5
    assert out["happiness_index"] == 0.5
    # ratio 1/2 = 0.5 → trust = 0.8 - 0.3 = 0.5
    assert out["trust_index"] == 0.5


def test_vector_score_is_clamped_to_six():
    # Extreme positive sentiment shouldn't produce > 6.
    items = [_item("incidents", 1.0)] * 5
    out = snapshot_from_news(items)
    assert out["sb"] <= 6.0
