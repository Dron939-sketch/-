"""Unit tests for the reputation-guard analyzer."""

from __future__ import annotations

import pytest

from analytics.reputation import analyze


def _m(author=None, source_kind=None, title="t", sentiment=None, severity=None, category=None, url=None):
    return {
        "author": author, "source_kind": source_kind, "title": title,
        "url": url, "category": category,
        "sentiment": sentiment, "severity": severity,
    }


def test_empty_mentions_returns_low_risk_zero_counts():
    report = analyze([]).to_dict()
    assert report["total_mentions"] == 0
    assert report["avg_sentiment"] is None
    assert report["negative_share"] is None
    assert report["risk"] == "low"
    assert report["top_negative_authors"] == []
    assert report["viral_negative"] == []


def test_only_positive_mentions_low_risk():
    mentions = [
        _m(author="a", source_kind="news_rss", sentiment=+0.5),
        _m(author="b", source_kind="news_rss", sentiment=+0.8),
    ]
    report = analyze(mentions).to_dict()
    assert report["total_mentions"] == 2
    assert report["negative_share"] == 0.0
    assert report["avg_sentiment"] == pytest.approx(0.65, abs=0.01)
    assert report["risk"] == "low"


def test_majority_negative_raises_risk_to_high():
    mentions = [
        _m(author="hater", source_kind="telegram", sentiment=-0.7, severity=0.3),
        _m(author="hater", source_kind="telegram", sentiment=-0.6, severity=0.2),
        _m(author="b",     source_kind="vk",       sentiment=-0.5),
        _m(author="c",     source_kind="news_rss", sentiment=-0.4),
        _m(author="d",     source_kind="news_rss", sentiment=+0.1),
    ]
    report = analyze(mentions).to_dict()
    # 4 out of 5 negative → share 0.8.
    assert report["negative_share"] == pytest.approx(0.8, abs=0.01)
    assert report["risk"] == "high"


def test_single_viral_severity_alone_raises_risk_to_high():
    mentions = [
        _m(author="a", source_kind="news_rss", sentiment=+0.1, severity=0.9),
        _m(author="b", source_kind="news_rss", sentiment=+0.2),
    ]
    report = analyze(mentions).to_dict()
    # Only severity lifts the risk.
    assert report["risk"] == "high"


def test_trend_spike_promotes_from_low_to_medium():
    # 3 of 10 negative (share = 0.3) but baseline was 0.1 → ratio 3× → medium.
    mentions = (
        [_m(author="x", source_kind="vk", sentiment=-0.5)] * 3
        + [_m(author="x", source_kind="vk", sentiment=+0.2)] * 7
    )
    report = analyze(mentions, prior_negative_share=0.1).to_dict()
    assert report["negative_share"] == pytest.approx(0.3, abs=0.01)
    # 0.3 exactly triggers medium by share rule; trend rule would too.
    assert report["risk"] == "medium"


def test_top_negative_authors_ranked_by_volume_and_severity():
    mentions = [
        # "loud" has 2 neg at mild severity.
        _m(author="loud", source_kind="telegram", sentiment=-0.5, severity=0.2),
        _m(author="loud", source_kind="telegram", sentiment=-0.6, severity=0.3),
        # "intense" has 1 neg but very high severity.
        _m(author="intense", source_kind="news_rss", sentiment=-0.8, severity=0.95),
        # "quiet" has 1 neg, low severity — lowest impact.
        _m(author="quiet", source_kind="vk", sentiment=-0.4, severity=0.1),
    ]
    report = analyze(mentions).to_dict()
    top = report["top_negative_authors"]
    # Impact = negative * (1 + worst_severity)
    # loud:    2 * 1.3 = 2.6
    # intense: 1 * 1.95 = 1.95
    # quiet:   1 * 1.1 = 1.1
    assert [a["author"] for a in top] == ["loud", "intense", "quiet"]
    assert top[0]["negative"] == 2
    assert top[0]["avg_sentiment"] == pytest.approx(-0.55, abs=0.01)


def test_non_negative_authors_are_excluded_from_ranking():
    mentions = [
        _m(author="fan", source_kind="news_rss", sentiment=+0.8),
        _m(author="fan", source_kind="news_rss", sentiment=+0.7),
        _m(author="one_hater", source_kind="telegram", sentiment=-0.6),
    ]
    report = analyze(mentions).to_dict()
    authors = [a["author"] for a in report["top_negative_authors"]]
    assert authors == ["one_hater"]


def test_viral_negative_ranks_by_blended_score():
    mentions = [
        _m(title="mild neg",      sentiment=-0.4, severity=0.1),   # score ~0.5
        _m(title="heavy neg",     sentiment=-0.9, severity=0.3),   # score ~1.2
        _m(title="severe event",  sentiment=+0.0, severity=0.85),  # score ~0.85
        _m(title="boring",        sentiment=+0.1, severity=0.0),   # excluded
    ]
    report = analyze(mentions).to_dict()
    titles = [v["title"] for v in report["viral_negative"]]
    assert titles[:2] == ["heavy neg", "severe event"]
    assert "boring" not in titles


def test_by_source_counts_every_item():
    mentions = [
        _m(source_kind="telegram"), _m(source_kind="telegram"),
        _m(source_kind="news_rss"),
        _m(source_kind=None),  # dropped from by_source, kept in total
    ]
    report = analyze(mentions).to_dict()
    assert report["by_source"] == {"telegram": 2, "news_rss": 1}
    assert report["total_mentions"] == 4


def test_garbage_sentiment_and_severity_do_not_crash():
    mentions = [
        _m(author="a", source_kind="vk", sentiment="oops", severity="nope"),
        _m(author="b", source_kind="vk", sentiment=None, severity=None),
    ]
    report = analyze(mentions).to_dict()
    assert report["total_mentions"] == 2
    assert report["avg_sentiment"] is None
    assert report["negative_share"] == 0.0
    assert report["risk"] == "low"


def test_author_falls_back_to_source_handle():
    mentions = [
        {"author": None, "source_handle": "@myblog",
         "source_kind": "telegram", "title": "x",
         "sentiment": -0.6, "severity": 0.3},
    ]
    report = analyze(mentions).to_dict()
    assert report["top_negative_authors"][0]["author"] == "@myblog"


def test_top_k_limits_respected():
    # 6 different hater authors — top_k_authors=3 should cap the list.
    mentions = [
        _m(author=f"h{i}", source_kind="vk", sentiment=-0.5)
        for i in range(6)
    ]
    report = analyze(mentions, top_k_authors=3).to_dict()
    assert len(report["top_negative_authors"]) == 3
