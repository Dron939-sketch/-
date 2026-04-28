"""Unit tests for the cross-city benchmark."""

from __future__ import annotations

import pytest

from analytics.benchmark import benchmark


def _snap(slug, name, emoji="🏙️", population=None, sb=None, tf=None, ub=None, chv=None):
    return {
        "slug": slug, "name": name, "emoji": emoji,
        "population": population,
        "sb": sb, "tf": tf, "ub": ub, "chv": chv,
    }


def test_empty_input_returns_empty_result_with_note():
    result = benchmark([]).to_dict()
    assert result["cities"] == []
    assert result["vector_stats"] == []
    assert result["note"] == "нет данных"


def test_single_city_is_leader_and_laggard_on_every_vector():
    snap = _snap("kolomna", "Коломна", sb=4.5, tf=4.2, ub=4.1, chv=4.0)
    result = benchmark([snap]).to_dict()

    assert len(result["cities"]) == 1
    row = result["cities"][0]
    assert row["composite"] == pytest.approx(4.2, abs=0.01)
    assert row["composite_rank"] == 1
    # Every metric rank is 1 and delta vs avg is 0.
    for key in ("safety", "economy", "quality", "social"):
        assert row["metrics"][key]["rank"] == 1
        assert row["metrics"][key]["delta_vs_avg"] == pytest.approx(0.0, abs=0.001)

    stats = {s["key"]: s for s in result["vector_stats"]}
    assert stats["safety"]["leader_slug"] == "kolomna"
    assert stats["safety"]["laggard_slug"] == "kolomna"
    assert stats["safety"]["spread"] == 0.0


def test_ranking_orders_cities_by_composite():
    snaps = [
        _snap("a", "A", sb=5.0, tf=5.0, ub=5.0, chv=5.0),
        _snap("b", "B", sb=3.0, tf=3.0, ub=3.0, chv=3.0),
        _snap("c", "C", sb=4.0, tf=4.0, ub=4.0, chv=4.0),
    ]
    result = benchmark(snaps).to_dict()
    slugs_in_order = [c["slug"] for c in result["cities"]]
    assert slugs_in_order == ["a", "c", "b"]
    assert [c["composite_rank"] for c in result["cities"]] == [1, 2, 3]


def test_per_vector_rank_is_independent_from_composite():
    # "b" has low safety but high economy — its ranks should differ per vector.
    snaps = [
        _snap("a", "A", sb=5.0, tf=2.0, ub=3.5, chv=3.5),
        _snap("b", "B", sb=2.0, tf=5.0, ub=3.5, chv=3.5),
    ]
    result = benchmark(snaps).to_dict()
    by_slug = {c["slug"]: c for c in result["cities"]}

    assert by_slug["a"]["metrics"]["safety"]["rank"] == 1
    assert by_slug["b"]["metrics"]["safety"]["rank"] == 2
    assert by_slug["a"]["metrics"]["economy"]["rank"] == 2
    assert by_slug["b"]["metrics"]["economy"]["rank"] == 1


def test_missing_metric_produces_null_rank_and_ignores_city_for_avg():
    # "c" has no safety data — must not affect avg or leader on that vector.
    snaps = [
        _snap("a", "A", sb=4.0, tf=3.5, ub=3.5, chv=3.5),
        _snap("b", "B", sb=2.0, tf=3.5, ub=3.5, chv=3.5),
        _snap("c", "C",         tf=3.5, ub=3.5, chv=3.5),  # sb=None
    ]
    result = benchmark(snaps).to_dict()

    by_slug = {c["slug"]: c for c in result["cities"]}
    assert by_slug["c"]["metrics"]["safety"]["value"] is None
    assert by_slug["c"]["metrics"]["safety"]["rank"] is None

    stats = {s["key"]: s for s in result["vector_stats"]}
    # Avg computed only from a + b = (4 + 2) / 2 = 3.0.
    assert stats["safety"]["avg"] == pytest.approx(3.0, abs=0.01)
    assert stats["safety"]["leader_slug"] == "a"
    assert stats["safety"]["laggard_slug"] == "b"


def test_city_with_no_metrics_at_all_sinks_to_bottom_with_null_composite():
    snaps = [
        _snap("a", "A", sb=4.0, tf=4.0, ub=4.0, chv=4.0),
        _snap("dead", "Dead"),  # no metrics at all
    ]
    result = benchmark(snaps).to_dict()
    assert result["cities"][-1]["slug"] == "dead"
    assert result["cities"][-1]["composite"] is None
    assert result["cities"][-1]["composite_rank"] is None


def test_values_outside_1_to_6_are_clamped():
    snaps = [
        _snap("a", "A", sb=99.0, tf=-5.0, ub=3.5, chv=3.5),
        _snap("b", "B", sb=3.0, tf=3.0, ub=3.5, chv=3.5),
    ]
    result = benchmark(snaps).to_dict()
    by_slug = {c["slug"]: c for c in result["cities"]}
    assert by_slug["a"]["metrics"]["safety"]["value"] == 6.0
    assert by_slug["a"]["metrics"]["economy"]["value"] == 1.0


def test_garbage_value_is_treated_as_missing():
    snaps = [
        _snap("a", "A", sb="oops", tf=4.0, ub=4.0, chv=4.0),
        _snap("b", "B", sb=3.0, tf=3.0, ub=3.0, chv=3.0),
    ]
    result = benchmark(snaps).to_dict()
    by_slug = {c["slug"]: c for c in result["cities"]}
    assert by_slug["a"]["metrics"]["safety"]["value"] is None
    assert by_slug["a"]["metrics"]["safety"]["rank"] is None


def test_snapshot_without_slug_is_dropped():
    snaps = [
        {"name": "orphan", "sb": 4.0, "tf": 4.0, "ub": 4.0, "chv": 4.0},
        _snap("a", "A", sb=3.0, tf=3.0, ub=3.0, chv=3.0),
    ]
    result = benchmark(snaps).to_dict()
    assert [c["slug"] for c in result["cities"]] == ["a"]
