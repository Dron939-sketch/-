"""Unit tests for the topic clustering analyzer."""

from __future__ import annotations

import pytest

from analytics.topics import analyze, classify_item


def _item(title="", content="", sentiment=None, severity=None, url=None):
    return {
        "title": title, "content": content, "url": url,
        "sentiment": sentiment, "severity": severity,
    }


def test_empty_windows_return_note():
    r = analyze().to_dict()
    assert r["topics"] == []
    assert r["total_current"] == 0
    assert r["note"] is not None


def test_classify_transport_keyword():
    assert classify_item(_item(title="Ремонт дороги на Фрунзе")) == "transport"
    assert classify_item(_item(title="Расписание автобусов изменилось")) == "transport"


def test_classify_utilities_keyword():
    assert classify_item(_item(title="Отключение горячей воды на Советской")) == "utilities"
    assert classify_item(_item(title="Авария на теплотрассе")) == "utilities"


def test_classify_unmatched_falls_to_other():
    assert classify_item(_item(title="Мэр посетил пустыню Гоби")) == "other"


def test_classify_empty_returns_other():
    assert classify_item(_item(title="", content="")) == "other"


def test_counts_and_sorting_by_count():
    current = [
        _item(title="Ремонт дороги 1"),
        _item(title="Ремонт дороги 2"),
        _item(title="Ремонт дороги 3"),
        _item(title="Отключение воды"),
        _item(title="Фестиваль джаза"),
    ]
    r = analyze(current_window=current).to_dict()
    assert r["total_current"] == 5
    # Transport (3) beats utilities (1) beats culture (1).
    assert r["topics"][0]["key"] == "transport"
    assert r["topics"][0]["count"] == 3


def test_avg_sentiment_computed_only_from_present_values():
    current = [
        _item(title="Ремонт дороги 1", sentiment=-0.5),
        _item(title="Ремонт дороги 2", sentiment=0.1),
        _item(title="Ремонт дороги 3"),       # no sentiment
    ]
    r = analyze(current_window=current).to_dict()
    transport = next(t for t in r["topics"] if t["key"] == "transport")
    assert transport["avg_sentiment"] == pytest.approx(-0.2, abs=0.01)


def test_trend_up_when_count_increases_significantly():
    current = [_item(title="дорога 1"), _item(title="дорога 2"), _item(title="дорога 3"),
               _item(title="дорога 4"), _item(title="дорога 5")]
    prior = [_item(title="дорога A")]   # 5 vs 1 → up
    r = analyze(current_window=current, prior_window=prior).to_dict()
    transport = next(t for t in r["topics"] if t["key"] == "transport")
    assert transport["trend"] == "up"
    assert transport["count"] == 5 and transport["count_prior"] == 1


def test_trend_down_when_count_drops():
    current = [_item(title="дорога 1")]
    prior = [_item(title="дорога A"), _item(title="дорога B"),
             _item(title="дорога C"), _item(title="дорога D")]
    r = analyze(current_window=current, prior_window=prior).to_dict()
    transport = next(t for t in r["topics"] if t["key"] == "transport")
    assert transport["trend"] == "down"


def test_trend_flat_when_change_small():
    current = [_item(title="дорога 1"), _item(title="дорога 2"),
               _item(title="дорога 3"), _item(title="дорога 4")]
    prior = [_item(title="дорога A"), _item(title="дорога B"),
             _item(title="дорога C"), _item(title="дорога D")]
    r = analyze(current_window=current, prior_window=prior).to_dict()
    transport = next(t for t in r["topics"] if t["key"] == "transport")
    assert transport["trend"] == "flat"


def test_trend_up_when_no_prior_but_current_exists():
    current = [_item(title="дорога 1")]
    r = analyze(current_window=current).to_dict()
    transport = next(t for t in r["topics"] if t["key"] == "transport")
    assert transport["trend"] == "up"
    assert transport["trend_ratio"] is None   # no baseline


def test_top_titles_sorted_by_severity_desc():
    current = [
        _item(title="A", severity=0.2),
        _item(title="B", severity=0.9),
        _item(title="C", severity=0.5),
    ]
    r = analyze(current_window=current, top_titles_per_topic=3).to_dict()
    other = next(t for t in r["topics"] if t["key"] == "other")
    titles = [t["title"] for t in other["top_titles"]]
    assert titles == ["B", "C", "A"]


def test_top_titles_respects_limit():
    current = [_item(title=f"дорога {i}") for i in range(10)]
    r = analyze(current_window=current, top_titles_per_topic=2).to_dict()
    transport = next(t for t in r["topics"] if t["key"] == "transport")
    assert len(transport["top_titles"]) == 2


def test_only_prior_data_still_surfaces_topic():
    # Topic only appeared in prior window — still rendered so trend=down.
    current = []
    prior = [_item(title="Ремонт дороги A"), _item(title="Ремонт дороги B")]
    r = analyze(current_window=current, prior_window=prior).to_dict()
    keys = {t["key"] for t in r["topics"]}
    assert "transport" in keys
    transport = next(t for t in r["topics"] if t["key"] == "transport")
    assert transport["count"] == 0 and transport["count_prior"] == 2
    assert transport["trend"] == "down"


def test_max_severity_is_overall_maximum():
    current = [
        _item(title="Ремонт дороги", severity=0.3),
        _item(title="Авария на дороге", severity=0.8),
    ]
    r = analyze(current_window=current).to_dict()
    transport = next(t for t in r["topics"] if t["key"] == "transport")
    assert transport["max_severity"] == pytest.approx(0.8)


def test_garbage_values_do_not_crash():
    current = [
        _item(title="дорога", sentiment="bad", severity=None),
        _item(title="дорога 2", sentiment=None, severity="oops"),
    ]
    r = analyze(current_window=current).to_dict()
    transport = next(t for t in r["topics"] if t["key"] == "transport")
    assert transport["count"] == 2
    # All sentiments/severities garbage → computed fields None.
    assert transport["avg_sentiment"] is None
    assert transport["max_severity"] is None
