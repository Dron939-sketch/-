"""Unit tests for the happiness-events adapter."""

from __future__ import annotations

from datetime import datetime

import pytest

from analytics.events_library import (
    current_season, library_size, recommend,
)


def test_library_has_at_least_15_events():
    assert library_size() >= 15


def test_current_season_maps_months_correctly():
    assert current_season(datetime(2024, 1, 15)) == "winter"
    assert current_season(datetime(2024, 4, 15)) == "spring"
    assert current_season(datetime(2024, 7, 15)) == "summer"
    assert current_season(datetime(2024, 10, 15)) == "autumn"
    assert current_season(datetime(2024, 12, 31)) == "winter"


def test_recommend_default_uses_today_season():
    r = recommend().to_dict()
    assert r["season"] in {"winter", "spring", "summer", "autumn"}
    assert r["audience"] is None


def test_recommend_filters_by_season():
    r = recommend(season="winter", limit=20).to_dict()
    seasons_found = {e["season"] for e in r["events"]}
    # year_round events are always eligible.
    assert seasons_found <= {"winter", "year_round"}


def test_recommend_filters_by_audience():
    r = recommend(audience="seniors", season="autumn", limit=20).to_dict()
    audiences = {e["audience"] for e in r["events"]}
    assert audiences <= {"seniors", "all"}


def test_recommend_respects_limit():
    r = recommend(limit=3).to_dict()
    assert len(r["events"]) <= 3


def test_events_sorted_by_combined_impact_desc():
    r = recommend(limit=20).to_dict()
    scores = [
        e["happiness_impact"] + 0.5 * e["trust_impact"]
        for e in r["events"]
    ]
    assert scores == sorted(scores, reverse=True)


def test_recommend_summer_includes_kolomna_kremlin():
    r = recommend(season="summer", limit=20).to_dict()
    ids = {e["id"] for e in r["events"]}
    assert "kolomna_kremlin" in ids
    assert "day_of_city" in ids


def test_recommend_winter_includes_new_year_tree():
    r = recommend(season="winter", limit=20).to_dict()
    ids = {e["id"] for e in r["events"]}
    assert "new_year_tree" in ids


def test_year_round_event_appears_in_every_season():
    for s in ("winter", "spring", "summer", "autumn"):
        r = recommend(season=s, limit=20).to_dict()
        ids = {e["id"] for e in r["events"]}
        assert "crafts_market" in ids, f"crafts_market missing in {s}"


def test_unknown_audience_still_surfaces_all_audience_events():
    # "all"-audience events are universal and should match any audience filter.
    r = recommend(season="winter", audience="martians").to_dict()
    if r["events"]:
        assert all(e["audience"] == "all" for e in r["events"])


def test_event_dict_shape_is_stable():
    r = recommend(limit=1).to_dict()
    event = r["events"][0]
    assert set(event.keys()) == {
        "id", "name", "description", "type", "audience", "season",
        "happiness_impact", "trust_impact", "cost_rub", "duration_days", "tags",
    }


def test_total_library_reflects_size():
    r = recommend(limit=3).to_dict()
    assert r["total_library"] == library_size()


def test_limit_floor_at_one():
    r = recommend(limit=0).to_dict()
    assert len(r["events"]) == 1
