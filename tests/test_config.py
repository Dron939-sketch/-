"""Sanity tests for config registries."""

from __future__ import annotations

import pytest

from config.cities import CITIES, KOLOMNA, get_city
from config.sources import get_sources_for_city, iter_all_sources


def test_kolomna_is_registered():
    assert "Коломна" in CITIES
    assert KOLOMNA["population"] > 100_000
    assert KOLOMNA["coordinates"]["lat"] == pytest.approx(55.1025, rel=1e-3)
    assert KOLOMNA["coordinates"]["lon"] == pytest.approx(38.7531, rel=1e-3)
    assert len(KOLOMNA["districts"]) >= 5


def test_get_city_rejects_unknown():
    with pytest.raises(KeyError):
        get_city("Атлантида")


def test_kolomna_sources_counts():
    bundle = get_sources_for_city("Коломна")
    assert len(bundle.telegram) == 10
    assert len(bundle.vk) == 5
    assert bundle.news_rss, "news_rss sources must be registered"


def test_iter_all_sources_is_priority_ordered():
    flat = iter_all_sources("Коломна")
    priorities = [s.priority for s in flat]
    assert priorities == sorted(priorities, key={"P0": 0, "P1": 1, "P2": 2}.get)
