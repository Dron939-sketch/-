"""Root-cause analysis (ТЗ §3.6, §6).

Walks the graph backward from a "problem" node through `.caused_by`
edges (i.e. against the arrows in `edges[]`). At each hop we pick the
strongest incoming edge — the element that contributes the most to the
current node's state. The chain terminates when we hit a node that has
no causes or we've gone 5 levels deep.

Pure, no I/O. The result is shaped for the "5 whys" UI in the ТЗ
mock-up: each hop carries `name`, `short`, `strength` and a human
"because ..." explanation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


_MAX_DEPTH = 5            # ТЗ §3.6 default
_MIN_STRENGTH = 0.05      # skip edges so weak they add no signal


@dataclass
class CauseHop:
    depth: int
    from_node: Dict[str, Any]    # the "because" node (a cause of `to_node`)
    to_node: Dict[str, Any]      # the current "why" node
    strength: float              # edge strength from_node → to_node

    def to_dict(self) -> Dict[str, Any]:
        return {
            "depth": self.depth,
            "cause_id": self.from_node.get("id"),
            "cause_title": self.from_node.get("title")
                or self.from_node.get("short")
                or self.from_node.get("id"),
            "effect_id": self.to_node.get("id"),
            "effect_title": self.to_node.get("title")
                or self.to_node.get("short")
                or self.to_node.get("id"),
            "strength": round(float(self.strength or 0.0), 3),
            "because": _because_sentence(self.from_node, self.to_node),
        }


@dataclass
class RootCauseTrace:
    problem_node_id: str
    chain: List[CauseHop]
    root: Optional[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem_node_id": self.problem_node_id,
            "chain": [hop.to_dict() for hop in self.chain],
            "root": (
                {
                    "id": self.root.get("id"),
                    "title": self.root.get("title") or self.root.get("short"),
                    "short": self.root.get("short"),
                    "description": self.root.get("description"),
                }
                if self.root is not None else None
            ),
            "depth": len(self.chain),
        }


def trace(
    graph: Dict[str, Any],
    problem_node_id: str,
    *,
    max_depth: int = _MAX_DEPTH,
) -> RootCauseTrace:
    """Walk the graph backward from `problem_node_id` to find the root.

    Returns a RootCauseTrace with one CauseHop per backward step. An
    empty chain means the node has no incoming edges (already a root).
    """
    nodes = _index_nodes(graph.get("nodes"))
    if problem_node_id not in nodes:
        return RootCauseTrace(problem_node_id=problem_node_id, chain=[], root=None)

    reverse_adj = _build_reverse_adjacency(graph.get("edges"), nodes)

    chain: List[CauseHop] = []
    current_id = problem_node_id
    visited = {current_id}

    for depth in range(1, max_depth + 1):
        incoming = reverse_adj.get(current_id, [])
        incoming = [(src, s) for src, s in incoming if s >= _MIN_STRENGTH and src not in visited]
        if not incoming:
            break
        # Strongest cause wins — same rule the ТЗ §6 pseudocode uses.
        incoming.sort(key=lambda item: item[1], reverse=True)
        strongest_id, strength = incoming[0]
        chain.append(
            CauseHop(
                depth=depth,
                from_node=nodes[strongest_id],
                to_node=nodes[current_id],
                strength=strength,
            )
        )
        visited.add(strongest_id)
        current_id = strongest_id

    root_node = nodes[current_id] if current_id != problem_node_id else None
    return RootCauseTrace(problem_node_id=problem_node_id, chain=chain, root=root_node)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _index_nodes(nodes: Optional[Iterable[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    if not nodes:
        return {}
    return {str(n.get("id")): n for n in nodes if n.get("id") is not None}


def _build_reverse_adjacency(
    edges: Optional[Iterable[Dict[str, Any]]],
    nodes: Dict[str, Dict[str, Any]],
) -> Dict[str, List[Tuple[str, float]]]:
    """Return `{effect_id: [(cause_id, strength), ...]}` for backward walk."""
    adj: Dict[str, List[Tuple[str, float]]] = {}
    if not edges:
        return adj
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
        adj.setdefault(tgt, []).append((src, strength))
    return adj


_BECAUSE_TEMPLATES = {
    # effect → cause sentence fragments, keyed by the effect's `short`
    # field. Keeps the UI text natural without making us lookup titles
    # manually on the frontend.
    "Результат":    "ухудшение на верхнем уровне обусловлено: {cause}",
    "СБ":           "падение безопасности объясняется: {cause}",
    "ТФ":           "экономическое ухудшение растёт из: {cause}",
    "УБ":           "качество жизни страдает из-за: {cause}",
    "Причина":      "системная причина держится на: {cause}",
    "Среда":        "состояние среды зависит от: {cause}",
    "Институты":    "работа институтов упирается в: {cause}",
    "Регион":       "региональный контекст формируется через: {cause}",
    "Замыкание":    "замыкание поддерживается элементом: {cause}",
}


def _because_sentence(cause: Dict[str, Any], effect: Dict[str, Any]) -> str:
    """Build a short, human 'because ...' sentence."""
    cause_title = (
        cause.get("title") or cause.get("short") or cause.get("description") or "—"
    )
    effect_short = effect.get("short") or effect.get("title") or ""
    template = _BECAUSE_TEMPLATES.get(effect_short, "обусловлено: {cause}")
    return template.format(cause=cause_title)
