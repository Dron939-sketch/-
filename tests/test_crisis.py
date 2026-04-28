"""Unit tests for the crisis predictor rules."""

from __future__ import annotations

import pytest

from analytics.crisis import detect_crises


def test_empty_inputs_return_ok_status():
    report = detect_crises().to_dict()
    assert report["status"] == "ok"
    assert report["alerts"] == []
    assert "норме" in report["headline"]


def test_stable_metrics_produce_no_alerts():
    report = detect_crises(
        current_metrics={"sb": 4.0, "tf": 4.0, "ub": 4.0, "chv": 4.0},
        metrics_history_7d={
            "sb":  [4.0, 4.1, 3.9, 4.0, 4.0, 4.0, 4.0],
            "tf":  [4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0],
            "ub":  [4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0],
            "chv": [4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0],
        },
    ).to_dict()
    assert report["status"] == "ok"
    assert report["alerts"] == []


def test_metric_drop_of_1_2_points_is_critical():
    report = detect_crises(
        current_metrics={"sb": 3.0, "tf": 4.0, "ub": 4.0, "chv": 4.0},
        metrics_history_7d={
            "sb":  [4.2, 4.2, 4.2, 4.2, 4.2, 4.2, 3.0],
            "tf":  [4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0],
            "ub":  [4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0],
            "chv": [4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0],
        },
    ).to_dict()

    drops = [a for a in report["alerts"] if a["kind"] == "metric_drop"]
    assert len(drops) == 1
    assert drops[0]["level"] == "critical"
    assert drops[0]["vector"] == "safety"
    assert report["status"] == "attention"
    assert drops[0]["evidence"]["drop"] >= 1.0


def test_metric_drop_between_05_and_07_is_medium():
    report = detect_crises(
        current_metrics={"sb": 3.5, "tf": 4.0, "ub": 4.0, "chv": 4.0},
        metrics_history_7d={
            "sb":  [4.1, 4.1, 4.1, 4.1, 4.1, 4.1, 3.5],
            "tf":  [4.0] * 7,
            "ub":  [4.0] * 7,
            "chv": [4.0] * 7,
        },
    ).to_dict()
    drops = [a for a in report["alerts"] if a["kind"] == "metric_drop"]
    assert len(drops) == 1
    assert drops[0]["level"] == "medium"


def test_metric_rise_never_raises_a_drop_alert():
    report = detect_crises(
        current_metrics={"sb": 5.0, "tf": 4.0, "ub": 4.0, "chv": 4.0},
        metrics_history_7d={
            "sb":  [3.0, 3.2, 3.5, 3.7, 4.0, 4.5, 5.0],
            "tf":  [4.0] * 7,
            "ub":  [4.0] * 7,
            "chv": [4.0] * 7,
        },
    ).to_dict()
    assert all(a["kind"] != "metric_drop" for a in report["alerts"])


def test_sentiment_spike_triggers_when_negatives_exceed_baseline():
    news = [{"sentiment": -0.6} for _ in range(8)]  # 8 negatives in 24h
    report = detect_crises(
        news_24h=news,
        news_7d_neg_count=7,  # ~1/day baseline → 8 is ~×8
    ).to_dict()
    spikes = [a for a in report["alerts"] if a["kind"] == "sentiment_spike"]
    assert len(spikes) == 1
    assert spikes[0]["level"] == "critical"
    assert spikes[0]["evidence"]["negative_24h"] == 8


def test_sentiment_spike_ignored_when_count_is_low():
    news = [{"sentiment": -0.6}, {"sentiment": -0.4}]  # only 2 negatives
    report = detect_crises(news_24h=news, news_7d_neg_count=14).to_dict()
    assert all(a["kind"] != "sentiment_spike" for a in report["alerts"])


def test_high_severity_event_is_surfaced():
    news = [
        {"title": "Авария на теплотрассе", "severity": 0.85},
        {"title": "Праздник", "severity": 0.1},
    ]
    report = detect_crises(news_24h=news).to_dict()
    crit = [a for a in report["alerts"] if a["kind"] == "high_severity"]
    assert len(crit) == 1
    assert crit[0]["level"] == "critical"
    assert crit[0]["evidence"]["max_severity"] >= 0.8
    assert crit[0]["evidence"]["top"][0]["title"].startswith("Авария")


def test_high_severity_reads_from_enrichment_dict_too():
    news = [{"title": "X", "enrichment": {"severity": 0.7}}]
    report = detect_crises(news_24h=news).to_dict()
    matches = [a for a in report["alerts"] if a["kind"] == "high_severity"]
    assert len(matches) == 1
    assert matches[0]["level"] == "high"


def test_complaint_surge_triggers_when_ratio_high():
    report = detect_crises(appeals_24h=40, appeals_7d_avg=5.0).to_dict()
    surges = [a for a in report["alerts"] if a["kind"] == "complaint_surge"]
    assert len(surges) == 1
    assert surges[0]["level"] == "critical"
    assert surges[0]["evidence"]["appeals_24h"] == 40


def test_complaint_surge_needs_at_least_five_appeals():
    # 3 appeals with zero baseline — still under the 5-floor, no alert.
    report = detect_crises(appeals_24h=3, appeals_7d_avg=0.0).to_dict()
    assert all(a["kind"] != "complaint_surge" for a in report["alerts"])


def test_alerts_are_sorted_with_critical_first():
    report = detect_crises(
        current_metrics={"sb": 3.4, "tf": 4.0, "ub": 4.0, "chv": 4.0},
        metrics_history_7d={
            "sb":  [4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 3.4],  # drop 0.6 → medium
            "tf":  [4.0] * 7, "ub":  [4.0] * 7, "chv": [4.0] * 7,
        },
        news_24h=[{"severity": 0.9, "title": "Big"}],  # severity → critical
    ).to_dict()
    # critical comes first.
    assert report["alerts"][0]["level"] == "critical"
    assert report["status"] == "attention"


def test_rollup_status_is_watch_when_only_medium_alerts():
    report = detect_crises(
        current_metrics={"sb": 3.5, "tf": 4.0, "ub": 4.0, "chv": 4.0},
        metrics_history_7d={
            "sb":  [4.1, 4.1, 4.1, 4.1, 4.1, 4.1, 3.5],  # medium
            "tf": [4.0] * 7, "ub": [4.0] * 7, "chv": [4.0] * 7,
        },
    ).to_dict()
    assert report["status"] == "watch"
    assert "наблюдением" in report["headline"].lower()


def test_garbage_values_do_not_crash():
    report = detect_crises(
        current_metrics={"sb": 4.0, "tf": 4.0, "ub": 4.0, "chv": 4.0},
        metrics_history_7d={"sb": [4.0] * 7, "tf": [4.0] * 7, "ub": [4.0] * 7, "chv": [4.0] * 7},
        news_24h=[
            {"sentiment": "nope"},
            {"severity": None},
            {"enrichment": "not a dict"},
        ],
    ).to_dict()
    assert report["status"] == "ok"
