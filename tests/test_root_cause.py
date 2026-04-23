"""Offline tests for the root-cause trace."""

from __future__ import annotations

from analytics.root_cause import trace


def _graph(nodes, edges):
    return {"nodes": nodes, "edges": edges}


def test_missing_problem_returns_empty_trace():
    g = _graph([{"id": "1", "title": "A"}], [])
    result = trace(g, "999")
    assert result.chain == []
    assert result.root is None
    d = result.to_dict()
    assert d["depth"] == 0


def test_problem_with_no_incoming_edges_has_empty_chain():
    g = _graph([{"id": "1", "title": "A"}], [])
    result = trace(g, "1")
    assert result.chain == []
    # No backward hops → no root "deeper" than problem itself.
    assert result.root is None


def test_strongest_incoming_cause_wins():
    # Two causes into B. Stronger one should be picked.
    g = _graph(
        [
            {"id": "1", "title": "Weak cause", "short": "Weak"},
            {"id": "2", "title": "Strong cause", "short": "Strong"},
            {"id": "3", "title": "Problem", "short": "Problem"},
        ],
        [
            {"source": "1", "target": "3", "strength": 0.3},
            {"source": "2", "target": "3", "strength": 0.9},
        ],
    )
    result = trace(g, "3")
    assert len(result.chain) == 1
    hop = result.chain[0]
    assert hop.from_node["id"] == "2"
    assert hop.to_node["id"] == "3"
    assert hop.strength == 0.9
    assert result.root["id"] == "2"


def test_chain_terminates_at_depth_cap():
    # 1 → 2 → 3 → 4 → 5 → 6. Problem = 6, max_depth = 3.
    nodes = [{"id": str(i), "title": f"N{i}"} for i in range(1, 7)]
    edges = [{"source": str(i), "target": str(i + 1), "strength": 0.8} for i in range(1, 6)]
    result = trace(_graph(nodes, edges), "6", max_depth=3)
    # 3 hops: 6←5, 5←4, 4←3.
    assert len(result.chain) == 3
    assert result.root["id"] == "3"


def test_chain_skips_already_visited_nodes():
    # Cycle between 2 and 3. Starting from 3, we go to 2, but shouldn't bounce back.
    g = _graph(
        [
            {"id": "1", "title": "Root cause"},
            {"id": "2", "title": "Middle"},
            {"id": "3", "title": "Problem"},
        ],
        [
            {"source": "1", "target": "2", "strength": 0.5},
            {"source": "2", "target": "3", "strength": 0.9},
            {"source": "3", "target": "2", "strength": 0.9},  # the cycle
        ],
    )
    result = trace(g, "3")
    ids = [hop.from_node["id"] for hop in result.chain]
    # After 3←2 we must not return to 3; expect 3←2, 2←1.
    assert ids == ["2", "1"]
    assert result.root["id"] == "1"


def test_low_strength_edges_are_ignored():
    # Only edge strength 0.01 — below _MIN_STRENGTH.
    g = _graph(
        [{"id": "1", "title": "Weak"}, {"id": "2", "title": "Problem"}],
        [{"source": "1", "target": "2", "strength": 0.01}],
    )
    result = trace(g, "2")
    assert result.chain == []
    assert result.root is None


def test_because_template_uses_effect_short_when_known():
    g = _graph(
        [
            {"id": "1", "title": "Высокая безработица", "short": "Причина"},
            {"id": "3", "title": "Экономика", "short": "ТФ"},
        ],
        [{"source": "1", "target": "3", "strength": 0.7}],
    )
    out = trace(g, "3").to_dict()
    assert out["chain"][0]["because"].startswith("экономическое ухудшение")
    assert "Высокая безработица" in out["chain"][0]["because"]


def test_to_dict_root_is_none_when_no_hops():
    g = _graph([{"id": "1", "title": "A"}], [])
    out = trace(g, "1").to_dict()
    assert out["root"] is None
    assert out["depth"] == 0


def test_to_dict_has_both_cause_and_effect_titles():
    g = _graph(
        [
            {"id": "1", "title": "Страх", "short": "СБ"},
            {"id": "3", "title": "Эконспад", "short": "ТФ"},
        ],
        [{"source": "1", "target": "3", "strength": 0.8}],
    )
    hop = trace(g, "3").to_dict()["chain"][0]
    assert hop["cause_title"] == "Страх"
    assert hop["effect_title"] == "Эконспад"
    assert hop["depth"] == 1
    assert hop["strength"] == 0.8
