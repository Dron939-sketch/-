"""Sanity tests for config registries."""

from __future__ import annotations

import pytest

from config.cities import CITIES, KOLOMNA, get_city, get_city_by_slug
from config.sources import get_sources_for_city, iter_all_sources


SE_OBLAST_CITIES = [
    "Коломна",
    "Луховицы",
    "Воскресенск",
    "Егорьевск",
    "Ступино",
    "Озёры",
]


def test_se_oblast_cluster_registered():
    for name in SE_OBLAST_CITIES:
        assert name in CITIES, f"{name} missing from CITIES"
    assert len(CITIES) == 6


def test_kolomna_is_pilot_with_full_data():
    assert KOLOMNA["population"] > 100_000
    assert KOLOMNA["coordinates"]["lat"] == pytest.approx(55.1025, rel=1e-3)
    assert KOLOMNA["coordinates"]["lon"] == pytest.approx(38.7531, rel=1e-3)
    assert len(KOLOMNA["districts"]) >= 5
    assert KOLOMNA["is_pilot"] is True
    assert KOLOMNA["slug"] == "kolomna"


def test_each_city_has_brand_fields():
    for name in SE_OBLAST_CITIES:
        cfg = CITIES[name]
        assert cfg["slug"], f"{name} missing slug"
        assert cfg["emoji"], f"{name} missing emoji"
        assert cfg["accent_color"].startswith("#"), f"{name} missing accent_color"
        assert cfg["region"] == "Московская область"


def test_get_city_by_slug_roundtrip():
    for name in SE_OBLAST_CITIES:
        cfg = CITIES[name]
        assert get_city_by_slug(cfg["slug"])["name"] == name


def test_get_city_rejects_unknown():
    with pytest.raises(KeyError):
        get_city("Атлантида")
    with pytest.raises(KeyError):
        get_city_by_slug("atlantis")


def test_kolomna_sources_counts():
    bundle = get_sources_for_city("Коломна")
    assert len(bundle.telegram) == 10
    assert len(bundle.vk) == 5
    assert bundle.news_rss, "news_rss sources must be registered"


def test_neighbour_cities_have_at_least_rss():
    for name in SE_OBLAST_CITIES:
        if name == "Коломна":
            continue
        bundle = get_sources_for_city(name)
        assert bundle.news_rss, f"{name} missing news_rss source"


def test_iter_all_sources_is_priority_ordered():
    flat = iter_all_sources("Коломна")
    priorities = [s.priority for s in flat]
    assert priorities == sorted(priorities, key={"P0": 0, "P1": 1, "P2": 2}.get)
