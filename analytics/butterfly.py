"""Butterfly-effect simulator (ТЗ §4).

Takes a `{nodes, edges}` graph from `analytics.model.build_graph` plus a
desired delta on one element, propagates the change across the graph
with attenuation `0.7 ** depth`, and returns per-element predictions.

The output is intentionally flat so the frontend can diff the "before"
and "after" columns from the ТЗ mock-up:
    SB  4.2 → 5.1   ▲ +21%

Pure, no I/O. Unit-tested on a synthetic graph — real integration goes
through `POST /api/city/{name}/simulate`.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


_ATTENUATION = 0.7   # ~30% signal loss per hop
_MAX_DEPTH = 5       # §4.1: depth cap in the butterfly algorithm
_SATURATION_LO = 1.0 # final value clamp (1..6 scale)
_SATURATION_HI = 6.0


@dataclass
class NodeDelta:
    node_id: str
    title: str
    delta_scaled: float       # change in the 1..6 UI scale
    depth: int                # hops from the trigger node
    before_scaled: float
    after_scaled: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "title": self.title,
            "delta": round(self.delta_scaled, 3),
            "depth": self.depth,
            "before": round(self.before_scaled, 2),
            "after": round(self.after_scaled, 2),
            "direction": (
                "up" if self.delta_scaled > 0.05
                else "down" if self.delta_scaled < -0.05
                else "flat"
            ),
        }


@dataclass
class Simulation:
    source_node_id: str
    input_delta_scaled: float
    nodes: List[NodeDelta]
    loops_weakened: int       # placeholder — filled by the caller if needed
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_node_id": self.source_node_id,
            "input_delta": round(self.input_delta_scaled, 3),
            "nodes": [n.to_dict() for n in self.nodes],
            "loops_weakened": self.loops_weakened,
            "note": self.note,
        }


def simulate(
    graph: Dict[str, Any],
    source_node_id: str,
    delta_scaled: float,
    *,
    attenuation: float = _ATTENUATION,
    max_depth: int = _MAX_DEPTH,
) -> Simulation:
    """Propagate `delta_scaled` on `source_node_id` through the graph.

    Args:
        graph:           `{nodes, edges, ...}` output of analytics.build_graph.
        source_node_id:  id of the element the mayor "turns the dial" on.
        delta_scaled:    absolute change in 1..6 scale (e.g. +0.5).
        attenuation:     per-hop signal loss multiplier (default 0.7).
        max_depth:       BFS depth cap (default 5).

    Returns a `Simulation` with one `NodeDelta` per affected node,
    sorted by descending absolute delta so the UI can highlight the
    biggest effects first.
    """
    nodes = _index_nodes(graph.get("nodes"))
    if source_node_id not in nodes:
        return Simulation(
            source_node_id=source_node_id,
            input_delta_scaled=delta_scaled,
            nodes=[],
            loops_weakened=0,
            note=f"node {source_node_id!r} missing from graph",
        )

    adjacency = _build_adjacency(graph.get("edges"), nodes)

    # BFS: (node_id, accumulated delta, depth). A node keeps the
    # largest-magnitude delta seen across all paths; we re-enqueue only
    # when we find a path that delivers more signal than before.
    best: Dict[str, Tuple[float, int]] = {source_node_id: (delta_scaled, 0)}
    queue: deque = deque([(source_node_id, delta_scaled, 0)])

    while queue:
        node_id, change, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for target_id, strength in adjacency.get(node_id, []):
            transmitted = change * strength * (attenuation ** depth)
            if abs(transmitted) < 0.005:
                continue  # below the numerical noise floor
            prior = best.get(target_id)
            if prior is None or abs(transmitted) > abs(prior[0]):
                best[target_id] = (transmitted, depth + 1)
                queue.append((target_id, transmitted, depth + 1))

    results: List[NodeDelta] = []
    for node_id, (cum_delta, depth) in best.items():
        node = nodes[node_id]
        before = float(node.get("scaled", 3.5))
        after = max(_SATURATION_LO, min(_SATURATION_HI, before + cum_delta))
        results.append(
            NodeDelta(
                node_id=node_id,
                title=str(node.get("title") or node.get("short") or node_id),
                delta_scaled=after - before,
                depth=depth,
                before_scaled=before,
                after_scaled=after,
            )
        )
    results.sort(key=lambda n: abs(n.delta_scaled), reverse=True)

    loops_weakened = _estimate_loops_weakened(
        graph.get("loops_count", 0), delta_scaled, results,
    )
    return Simulation(
        source_node_id=source_node_id,
        input_delta_scaled=delta_scaled,
        nodes=results,
        loops_weakened=loops_weakened,
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _index_nodes(nodes: Optional[Iterable[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    if not nodes:
        return {}
    return {str(n.get("id")): n for n in nodes if n.get("id") is not None}


def _build_adjacency(
    edges: Optional[Iterable[Dict[str, Any]]],
    nodes: Dict[str, Dict[str, Any]],
) -> Dict[str, List[Tuple[str, float]]]:
    """Return `{source_id: [(target_id, strength), ...]}`.

    Drops edges whose endpoints aren't present in the node map so a
    broken graph can't produce NaN-style cascades.
    """
    adjacency: Dict[str, List[Tuple[str, float]]] = {}
    if not edges:
        return adjacency
    for edge in edges:
        src = str(edge.get("source"))
        tgt = str(edge.get("target"))
        if src not in nodes or tgt not in nodes:
            continue
        try:
            strength = float(edge.get("strength", 0.5) or 0.5)
        except (TypeError, ValueError):
            strength = 0.5
        strength = max(0.0, min(1.0, strength))
        adjacency.setdefault(src, []).append((tgt, strength))
    return adjacency


def _estimate_loops_weakened(
    total_loops: int, input_delta: float, results: List[NodeDelta]
) -> int:
    """Rough heuristic so the UI has something to show.

    We don't re-run the loop analyzer here (too expensive for an
    interactive simulator). Instead: if the positive delta pushes the
    average affected node above a threshold, we claim that 40% of known
    loops weaken. This is honest about being a rule-of-thumb; the real
    loop recalc lives in the scheduler's hourly job.
    """
    if not results or total_loops <= 0 or input_delta <= 0:
        return 0
    avg_after = sum(n.after_scaled for n in results) / len(results)
    if avg_after >= 4.5:
        return max(1, int(total_loops * 0.4))
    if avg_after >= 4.0:
        return max(1, int(total_loops * 0.2))
    return 0
