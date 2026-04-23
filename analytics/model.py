"""Bridge to the legacy `ConfinementModel9` (confinement_model.py).

Exposes the 9-element graph in a shape the frontend Cytoscape widget can
consume directly: `{nodes: [...], edges: [...]}`. Keeps the legacy
import local so a broken core module doesn't poison FastAPI imports.

Everything here is pure (no I/O). The caller picks the snapshot
(usually the latest metrics row from the DB) and passes it in.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from analytics.loops import metrics_to_vectors  # already present

logger = logging.getLogger(__name__)


# Element id → (russian title, short label, dashboard category)
# The labels are tuned for Cytoscape node.label display.
_ELEMENT_META: Dict[int, Dict[str, str]] = {
    1: {"title": "Результат",      "short": "Результат",   "group": "outcome"},
    2: {"title": "Безопасность",   "short": "СБ",          "group": "vector"},
    3: {"title": "Экономика",      "short": "ТФ",          "group": "vector"},
    4: {"title": "Качество жизни", "short": "УБ",          "group": "vector"},
    5: {"title": "Общая причина",  "short": "Причина",     "group": "system"},
    6: {"title": "Среда",          "short": "Среда",       "group": "context"},
    7: {"title": "Институты",      "short": "Институты",   "group": "context"},
    8: {"title": "Регион",         "short": "Регион",      "group": "context"},
    9: {"title": "Замыкание",      "short": "Замыкание",   "group": "closure"},
}


def build_graph(
    city_name: str,
    snapshot: Dict[str, float],
    *,
    city_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a Cytoscape-ready `{nodes, edges}` dict.

    Returns an empty graph (with a `disabled` flag set) if the legacy
    core cannot be imported or `build_from_city_data` raises — the
    frontend shows a placeholder instead of crashing.
    """
    try:
        from confinement_model import ConfinementModel9  # type: ignore
    except Exception:  # noqa: BLE001
        logger.warning("confinement_model unavailable — empty graph")
        return _empty_graph(city_name, reason="core_unavailable")

    vectors = metrics_to_vectors(snapshot)
    try:
        model = ConfinementModel9(city_id=city_id, city_name=city_name)
        model.build_from_city_data(vectors)
    except Exception:  # noqa: BLE001
        logger.warning("build_from_city_data failed for %s", city_name, exc_info=False)
        return _empty_graph(city_name, reason="build_failed")

    nodes = _extract_nodes(model)
    edges = _extract_edges(model)
    loops_summary = _summarise_loops(model)

    return {
        "city": city_name,
        "nodes": nodes,
        "edges": edges,
        "loops_count": loops_summary["count"],
        "closure_score": float(getattr(model, "closure_score", 0.0) or 0.0),
        "key_problem": _safe_string(getattr(model, "key_confinement", None)),
        "disabled": False,
    }


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------

def _empty_graph(city_name: str, *, reason: str) -> Dict[str, Any]:
    return {
        "city": city_name,
        "nodes": [],
        "edges": [],
        "loops_count": 0,
        "closure_score": 0.0,
        "key_problem": None,
        "disabled": True,
        "reason": reason,
    }


def _extract_nodes(model: Any) -> List[Dict[str, Any]]:
    """Turn `model.elements` into Cytoscape node dicts."""
    elements = getattr(model, "elements", None) or {}
    nodes: List[Dict[str, Any]] = []
    for eid in sorted(_ELEMENT_META):
        meta = _ELEMENT_META[eid]
        element = elements.get(eid) if isinstance(elements, dict) else None
        strength = _element_strength(element)
        description = _element_description(element)
        nodes.append(
            {
                "id": str(eid),
                "title": meta["title"],
                "short": meta["short"],
                "group": meta["group"],
                "strength": strength,           # 0..1
                "scaled": round(strength * 6, 2),  # 1..6 for the UI
                "description": description,
            }
        )
    return nodes


def _extract_edges(model: Any) -> List[Dict[str, Any]]:
    """Extract edges from `model.links` (preferred) or element.causes fallback."""
    links = getattr(model, "links", None)
    if isinstance(links, list) and links:
        return [_serialise_edge(link) for link in links if _is_valid_edge(link)]

    # Fallback: walk .elements[*].causes if links aren't populated.
    elements = getattr(model, "elements", None) or {}
    fallback: List[Dict[str, Any]] = []
    if isinstance(elements, dict):
        for eid, element in elements.items():
            for cause in getattr(element, "causes", []) or []:
                target_id = getattr(cause, "id", None) or getattr(cause, "element_id", None)
                if target_id is None:
                    continue
                fallback.append(
                    {
                        "source": str(eid),
                        "target": str(target_id),
                        "strength": round(float(getattr(cause, "strength", 0.5) or 0.5), 3),
                        "label": "",
                    }
                )
    return fallback


def _is_valid_edge(link: Any) -> bool:
    if isinstance(link, dict):
        return bool(link.get("from") is not None and link.get("to") is not None)
    return hasattr(link, "source") and hasattr(link, "target")


def _serialise_edge(link: Any) -> Dict[str, Any]:
    if isinstance(link, dict):
        return {
            "source": str(link.get("from")),
            "target": str(link.get("to")),
            "strength": round(float(link.get("strength", 0.5) or 0.5), 3),
            "label": _safe_string(link.get("description") or link.get("type") or ""),
        }
    # object fallback
    return {
        "source": str(getattr(link, "source", getattr(link, "from_id", ""))),
        "target": str(getattr(link, "target", getattr(link, "to_id", ""))),
        "strength": round(float(getattr(link, "strength", 0.5) or 0.5), 3),
        "label": _safe_string(getattr(link, "description", "")),
    }


def _summarise_loops(model: Any) -> Dict[str, Any]:
    loops = getattr(model, "loops", None)
    if isinstance(loops, list):
        return {"count": len(loops)}
    return {"count": 0}


def _element_strength(element: Any) -> float:
    if element is None:
        return 0.5
    val = getattr(element, "strength", 0.5)
    try:
        return max(0.0, min(1.0, float(val)))
    except (TypeError, ValueError):
        return 0.5


def _element_description(element: Any) -> str:
    if element is None:
        return ""
    for attr in ("description", "text", "name"):
        v = getattr(element, attr, None)
        if isinstance(v, str) and v.strip():
            return v.strip()[:200]
    return ""


def _safe_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()[:400] or None
    if isinstance(value, dict):
        # Pull a readable hint if present.
        for key in ("description", "name", "title"):
            v = value.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()[:400]
        return None
    return str(value)[:400]
