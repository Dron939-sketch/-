"""Unit tests for the market-gap analyzer."""

from __future__ import annotations

import pytest

from analytics.market_gaps import analyze


def _topic(key, label, count, negative_titles=0, total_titles=3, trend="flat"):
    """Build a topics_report-style entry for a topic."""
    titles = []
    for i in range(negative_titles):
        titles.append({"title": f"neg-{key}-{i}", "sentiment": -0.6, "severity": 0.4})
    for i in range(max(0, total_titles - negative_titles)):
        titles.append({"title": f"neu-{key}-{i}", "sentiment": 0.1, "severity": 0.1})
    return {"key": key, "label": label, "count": count,
            "top_titles": titles, "trend": trend}


def test_empty_input_returns_note():
    r = analyze({}).to_dict()
    assert r["niches"] == []
    assert r["window_items"] == 0
    assert r["note"]


def test_missing_topics_report_still_returns_stable_shape():
    r = analyze(None).to_dict()
    assert set(r.keys()) == {"niches", "topic_signals", "window_items", "note"}


def test_high_pain_topic_surfaces_niche_with_high_confidence():
    report = {"topics": [
        _topic("education", "Образование", count=40,
               negative_titles=2, total_titles=3),   # 2/3 → 67% negative → high pain
    ]}
    r = analyze(report).to_dict()
    assert len(r["niches"]) >= 1
    top = r["niches"][0]
    assert top["linked_topic"] == "education"
    assert top["confidence"] == "high"
    assert top["demand_score"] > 0.5


def test_medium_pain_topic_marked_medium():
    report = {"topics": [
        _topic("utilities", "ЖКХ", count=15,
               negative_titles=1, total_titles=3),   # 33% → medium
    ]}
    r = analyze(report).to_dict()
    top = r["niches"][0]
    assert top["confidence"] == "medium"


def test_low_activity_gets_low_confidence():
    report = {"topics": [
        _topic("culture", "Культура", count=2,
               negative_titles=0, total_titles=2),
    ]}
    r = analyze(report).to_dict()
    assert r["niches"][0]["confidence"] == "low"


def test_topics_without_niche_mapping_are_ignored():
    # "other" is not in _NICHES_BY_TOPIC → should be dropped silently.
    report = {"topics": [
        _topic("other", "Прочее", count=100,
               negative_titles=3, total_titles=3),
    ]}
    r = analyze(report).to_dict()
    assert r["niches"] == []   # nothing to recommend
    assert r["note"]


def test_diversity_one_niche_per_topic_before_repeats():
    # Two topics with lots of pain — first pass gives one niche per topic.
    report = {"topics": [
        _topic("education", "Образование", count=30, negative_titles=3, total_titles=3),
        _topic("transport", "Транспорт", count=25, negative_titles=3, total_titles=3),
    ]}
    r = analyze(report, top_k=2).to_dict()
    topics_covered = {n["linked_topic"] for n in r["niches"]}
    assert topics_covered == {"education", "transport"}


def test_top_k_respected():
    report = {"topics": [
        _topic("education", "Образование", count=30, negative_titles=3, total_titles=3),
        _topic("transport", "Транспорт", count=25, negative_titles=3, total_titles=3),
        _topic("safety", "Безопасность", count=20, negative_titles=3, total_titles=3),
        _topic("utilities", "ЖКХ", count=15, negative_titles=3, total_titles=3),
    ]}
    r = analyze(report, top_k=3).to_dict()
    assert len(r["niches"]) == 3


def test_topic_signals_reflect_input():
    report = {"topics": [
        _topic("utilities", "ЖКХ", count=12, negative_titles=2, total_titles=3),
    ]}
    r = analyze(report).to_dict()
    sig = r["topic_signals"]["utilities"]
    assert sig["label"] == "ЖКХ"
    assert sig["count"] == 12
    # 2/3 ≈ 0.667
    assert sig["negative_ratio"] == pytest.approx(0.667, abs=0.01)


def test_evidence_attached_up_to_two_items():
    report = {"topics": [
        _topic("transport", "Транспорт", count=20, negative_titles=3, total_titles=3),
    ]}
    r = analyze(report).to_dict()
    top = r["niches"][0]
    assert len(top["evidence"]) <= 2
    assert top["evidence"][0]["title"].startswith("neg-transport")


def test_rationale_includes_mentions_count():
    report = {"topics": [
        _topic("education", "Образование", count=42, negative_titles=3, total_titles=3),
    ]}
    r = analyze(report).to_dict()
    top = r["niches"][0]
    assert "42" in top["rationale"]


def test_zero_count_topics_skipped():
    # Topic appeared with count=0 (only prior window had data) → skip.
    report = {"topics": [
        {"key": "education", "label": "Образование", "count": 0,
         "top_titles": [], "trend": "down"},
        _topic("transport", "Транспорт", count=20, negative_titles=3, total_titles=3),
    ]}
    r = analyze(report).to_dict()
    topics_covered = {n["linked_topic"] for n in r["niches"]}
    assert "education" not in topics_covered
    assert "transport" in topics_covered


def test_window_items_is_sum_of_counts():
    report = {"topics": [
        _topic("education", "Образование", count=10, negative_titles=2, total_titles=3),
        _topic("transport", "Транспорт", count=15, negative_titles=2, total_titles=3),
    ]}
    r = analyze(report).to_dict()
    assert r["window_items"] == 25


def test_response_shape_is_stable():
    r = analyze({"topics": [
        _topic("culture", "Культура", count=5, negative_titles=1, total_titles=2)
    ]}).to_dict()
    niche = r["niches"][0]
    assert set(niche.keys()) == {
        "key", "label", "linked_topic", "demand_score",
        "confidence", "rationale", "evidence",
    }
