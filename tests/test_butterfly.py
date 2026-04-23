"""Offline tests for the butterfly-effect simulator.

We hand-craft a tiny graph (3-4 nodes) so we can reason about the
expected cascade values exactly. The real 9-element ConfinementModel9
is covered in the bridge tests.
"""

from __future__ import annotations

from analytics.butterfly import simulate


def _graph(nodes, edges, loops_count=0):
    return {"nodes": nodes, "edges": edges, "loops_count": loops_count}


def test_missing_source_returns_empty_simulation_with_note():
    g = _graph([{"id": "1", "title": "A", "scaled": 4.0}], [])
    sim = simulate(g, "999", delta_scaled=0.5)
    assert sim.nodes == []
    assert sim.source_node_id == "999"
    assert "missing" in (sim.note or "").lower()


def test_single_node_no_edges_only_affects_source():
    g = _graph([{"id": "1", "title": "A", "scaled": 4.0}], [])
    sim = simulate(g, "1", delta_scaled=0.5)
    d = sim.to_dict()
    assert len(d["nodes"]) == 1
    node = d["nodes"][0]
    assert node["node_id"] == "1"
    assert node["before"] == 4.0
    assert node["after"] == 4.5
    assert node["delta"] == 0.5
    assert node["direction"] == "up"
    assert node["depth"] == 0


def test_direct_edge_propagates_with_attenuation():
    # A (4.0) --[0.8]--> B (3.0). No depth-0 attenuation on first hop.
    g = _graph(
        [
            {"id": "1", "title": "A", "scaled": 4.0},
            {"id": "2", "title": "B", "scaled": 3.0},
        ],
        [{"source": "1", "target": "2", "strength": 0.8}],
    )
    sim = simulate(g, "1", delta_scaled=1.0)
    nodes = {n["node_id"]: n for n in sim.to_dict()["nodes"]}
    # First hop: 1.0 * 0.8 * 0.7^0 = 0.8
    assert nodes["2"]["delta"] == 0.8
    assert nodes["2"]["after"] == 3.8
    assert nodes["2"]["depth"] == 1


def test_two_hops_apply_attenuation_per_depth():
    # A -> B -> C, both edges strength 1.0 for clarity.
    g = _graph(
        [
            {"id": "1", "title": "A", "scaled": 3.0},
            {"id": "2", "title": "B", "scaled": 3.0},
            {"id": "3", "title": "C", "scaled": 3.0},
        ],
        [
            {"source": "1", "target": "2", "strength": 1.0},
            {"source": "2", "target": "3", "strength": 1.0},
        ],
    )
    sim = simulate(g, "1", delta_scaled=1.0)
    nodes = {n["node_id"]: n for n in sim.to_dict()["nodes"]}
    # hop 1: 1.0 * 1.0 * 0.7^0 = 1.0
    assert nodes["2"]["delta"] == 1.0
    # hop 2: 1.0 * 1.0 * 0.7^1 = 0.7
    assert nodes["3"]["delta"] == 0.7


def test_after_value_is_clamped_to_1_6():
    # A=5.5, big positive delta would push B to >6.
    g = _graph(
        [
            {"id": "1", "title": "A", "scaled": 5.5},
            {"id": "2", "title": "B", "scaled": 5.5},
        ],
        [{"source": "1", "target": "2", "strength": 1.0}],
    )
    sim = simulate(g, "1", delta_scaled=2.0)
    nodes = {n["node_id"]: n for n in sim.to_dict()["nodes"]}
    # The cascade would deliver delta=2.0 to B → 5.5 + 2.0 = 7.5 → clamped to 6.0
    assert nodes["2"]["after"] == 6.0
    assert nodes["2"]["delta"] == 0.5  # actual post-clamp delta


def test_negative_delta_direction_is_down():
    g = _graph(
        [{"id": "1", "title": "A", "scaled": 4.0}, {"id": "2", "title": "B", "scaled": 3.0}],
        [{"source": "1", "target": "2", "strength": 0.5}],
    )
    sim = simulate(g, "1", delta_scaled=-1.0)
    nodes = {n["node_id"]: n for n in sim.to_dict()["nodes"]}
    assert nodes["2"]["direction"] == "down"
    assert nodes["2"]["after"] == 2.5


def test_cycle_does_not_inflate_signal():
    # A <-> B. Should not blow up.
    g = _graph(
        [{"id": "1", "title": "A", "scaled": 4.0}, {"id": "2", "title": "B", "scaled": 4.0}],
        [
            {"source": "1", "target": "2", "strength": 0.8},
            {"source": "2", "target": "1", "strength": 0.8},
        ],
    )
    sim = simulate(g, "1", delta_scaled=1.0)
    # No ValueError / RecursionError; output is finite.
    for n in sim.to_dict()["nodes"]:
        assert -3.0 <= n["delta"] <= 3.0


def test_nodes_are_sorted_by_abs_delta_descending():
    g = _graph(
        [
            {"id": "1", "title": "A", "scaled": 3.0},
            {"id": "2", "title": "B", "scaled": 3.0},
            {"id": "3", "title": "C", "scaled": 3.0},
        ],
        [
            {"source": "1", "target": "2", "strength": 0.9},  # strong
            {"source": "1", "target": "3", "strength": 0.2},  # weak
        ],
    )
    out = simulate(g, "1", delta_scaled=1.0).to_dict()
    # Order: source itself (1.0), then B (0.9), then C (0.2).
    deltas = [abs(n["delta"]) for n in out["nodes"]]
    assert deltas == sorted(deltas, reverse=True)


def test_edges_with_missing_endpoints_are_ignored():
    g = _graph(
        [{"id": "1", "title": "A", "scaled": 3.0}, {"id": "2", "title": "B", "scaled": 3.0}],
        [
            {"source": "1", "target": "2", "strength": 1.0},
            {"source": "1", "target": "999", "strength": 1.0},  # dangling
            {"source": "7", "target": "2", "strength": 1.0},    # dangling source
        ],
    )
    sim = simulate(g, "1", delta_scaled=1.0)
    ids = {n.node_id for n in sim.nodes}
    assert ids == {"1", "2"}


def test_loops_weakened_heuristic():
    # Positive delta + high post-change averages → some loops weaken.
    g = _graph(
        [{"id": "1", "title": "A", "scaled": 4.0}, {"id": "2", "title": "B", "scaled": 4.0}],
        [{"source": "1", "target": "2", "strength": 1.0}],
        loops_count=5,
    )
    sim = simulate(g, "1", delta_scaled=1.0)
    assert sim.loops_weakened >= 1
    # Negative delta → no loops weakened.
    sim_neg = simulate(g, "1", delta_scaled=-1.0)
    assert sim_neg.loops_weakened == 0
