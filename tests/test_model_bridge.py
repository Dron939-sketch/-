"""Tests for the analytics.model graph bridge.

We focus on the pure, defensible bits: node metadata, edge
serialisation from both dict-style and object-style links, and the
fail-safe empty-graph path when the legacy core can't be imported or
`build_from_city_data` raises.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from analytics.model import (
    _ELEMENT_META,
    _empty_graph,
    _extract_edges,
    _extract_nodes,
    _serialise_edge,
    build_graph,
)


def test_empty_graph_has_nine_elements_after_build_failure():
    """When legacy import blows up, caller still gets a renderable shape."""
    with patch("analytics.model.__name__"):
        graph = _empty_graph("Коломна", reason="core_unavailable")
    assert graph["disabled"] is True
    assert graph["reason"] == "core_unavailable"
    assert graph["nodes"] == []
    assert graph["edges"] == []
    assert graph["city"] == "Коломна"


def test_element_meta_covers_all_nine_ids():
    assert set(_ELEMENT_META.keys()) == set(range(1, 10))
    for meta in _ELEMENT_META.values():
        assert meta["title"]
        assert meta["short"]
        assert meta["group"] in {"outcome", "vector", "system", "context", "closure"}


def test_extract_nodes_uses_meta_when_elements_missing():
    fake = SimpleNamespace(elements={})
    nodes = _extract_nodes(fake)
    assert len(nodes) == 9
    ids = [n["id"] for n in nodes]
    assert ids == [str(i) for i in range(1, 10)]
    # All baseline strengths default to 0.5 when we have no real element.
    assert all(n["strength"] == 0.5 for n in nodes)
    assert all(n["scaled"] == 3.0 for n in nodes)


def test_extract_nodes_reads_strength_from_element():
    elements = {
        2: SimpleNamespace(strength=0.8, description="Безопасность города"),
        3: SimpleNamespace(strength=0.4, description="Экономика замедлена"),
    }
    nodes = _extract_nodes(SimpleNamespace(elements=elements))
    by_id = {n["id"]: n for n in nodes}
    assert by_id["2"]["strength"] == 0.8
    assert by_id["2"]["scaled"] == 4.8
    assert "Безопасность" in by_id["2"]["description"]
    assert by_id["3"]["strength"] == 0.4
    # Element 5 has no entry → default.
    assert by_id["5"]["strength"] == 0.5


def test_extract_edges_from_dict_links():
    links = [
        {"from": 2, "to": 3, "strength": 0.9, "description": "СБ→ТФ"},
        {"from": 3, "to": 4, "strength": 0.5, "type": "quality"},
        # Malformed entries must be filtered out.
        {"from": None, "to": 4, "strength": 0.3},
    ]
    edges = _extract_edges(SimpleNamespace(links=links))
    assert len(edges) == 2
    assert edges[0] == {"source": "2", "target": "3", "strength": 0.9, "label": "СБ→ТФ"}
    assert edges[1]["source"] == "3"
    assert edges[1]["label"] == "quality"


def test_extract_edges_fallback_to_element_causes():
    # No .links — walk .elements[*].causes instead.
    cause_to_3 = SimpleNamespace(id=3, strength=0.7)
    element_2 = SimpleNamespace(causes=[cause_to_3])
    model = SimpleNamespace(links=None, elements={2: element_2})
    edges = _extract_edges(model)
    assert edges == [{"source": "2", "target": "3", "strength": 0.7, "label": ""}]


def test_serialise_edge_object_style():
    link = SimpleNamespace(source=2, target=4, strength=0.6, description="СБ→УБ")
    out = _serialise_edge(link)
    assert out == {"source": "2", "target": "4", "strength": 0.6, "label": "СБ→УБ"}


def test_build_graph_returns_disabled_when_core_missing(monkeypatch):
    """Simulate `import confinement_model` failing."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name == "confinement_model":
            raise ImportError("pretend the legacy core is missing")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    graph = build_graph("Коломна", {"sb": 4.2, "tf": 3.8, "ub": 4.5, "chv": 3.2})
    assert graph["disabled"] is True
    assert graph["reason"] == "core_unavailable"
    assert graph["nodes"] == []
    assert graph["edges"] == []


def test_build_graph_returns_disabled_when_build_from_city_data_raises(monkeypatch):
    """Legacy imports fine but `build_from_city_data` blows up."""

    class _Broken:
        def __init__(self, *a, **kw):
            pass

        def build_from_city_data(self, *a, **kw):
            raise RuntimeError("bad data")

    fake_mod = SimpleNamespace(ConfinementModel9=_Broken)
    import sys
    monkeypatch.setitem(sys.modules, "confinement_model", fake_mod)
    graph = build_graph("Коломна", {"sb": 4.2, "tf": 3.8, "ub": 4.5, "chv": 3.2})
    assert graph["disabled"] is True
    assert graph["reason"] == "build_failed"
