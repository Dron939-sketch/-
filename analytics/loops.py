"""Analytics bridge: metrics snapshot → active loops.

Thin adapter on top of the existing core (`confinement_model.py` +
`loop_analyzer.py`). Takes a `{sb, tf, ub, chv}` snapshot, runs the
9-element model + loop detector and returns loops in a flat shape
ready for the `loops` table and the dashboard widget.

Everything is pure — no DB, no network. The scheduler layer calls this
inside `analyze_loops_for_city`.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Legacy core uses Russian-named dict keys for the 4 vectors.
_VECTOR_KEYS = {
    "sb":  "СБ",
    "tf":  "ТФ",
    "ub":  "УБ",
    "chv": "ЧВ",
}


# Map the analyzer's strategic_priority → dashboard severity level.
_PRIORITY_LEVEL = {
    "КРИТИЧЕСКИЙ": "critical",
    "ВЫСОКИЙ":     "critical",
    "СРЕДНИЙ":     "warn",
    "НИЗКИЙ":      "info",
}


def metrics_to_vectors(snapshot: Dict[str, float]) -> Dict[str, float]:
    """Project a DB metrics row into the RU-keyed dict the core expects.

    Accepts either the DB-row shape (`sb/tf/ub/chv`) or already-RU keys.
    Values that the caller didn't provide default to the mid-point (3.5).
    """
    out: Dict[str, float] = {}
    for en_key, ru_key in _VECTOR_KEYS.items():
        if ru_key in snapshot and snapshot[ru_key] is not None:
            out[ru_key] = float(snapshot[ru_key])
        elif en_key in snapshot and snapshot[en_key] is not None:
            out[ru_key] = float(snapshot[en_key])
        else:
            out[ru_key] = 3.5
    return out


def analyze_loops(
    city_name: str,
    snapshot: Dict[str, float],
    *,
    city_id: Optional[int] = None,
    top_n: int = 3,
) -> List[Dict[str, Any]]:
    """Return up to `top_n` strongest loops for a city snapshot.

    Every item has a stable shape: `name`, `description`, `strength`,
    `level`, `break_points` (JSON-serialisable). Import of the legacy core
    is local so a missing dependency / import-time error in the core
    degrades gracefully to an empty list.
    """
    try:
        from confinement_model import ConfinementModel9  # type: ignore
        from loop_analyzer import CityLoopAnalyzer  # type: ignore
    except Exception:  # noqa: BLE001 — broad: legacy code may raise on import
        logger.warning("confinement core unavailable — returning no loops", exc_info=False)
        return []

    vectors = metrics_to_vectors(snapshot)
    try:
        model = ConfinementModel9(city_id=city_id, city_name=city_name)
        model.build_from_city_data(vectors)
        analyzer = CityLoopAnalyzer(model)
        raw_loops: List[Dict[str, Any]] = analyzer.analyze() or []
    except Exception:  # noqa: BLE001
        logger.warning(
            "confinement analyze failed for %s", city_name, exc_info=False
        )
        return []

    # Rank by impact if the analyzer computed one, otherwise by raw_strength.
    def _rank(loop: Dict[str, Any]) -> float:
        for key in ("impact", "raw_strength", "strength"):
            v = loop.get(key)
            if isinstance(v, (int, float)):
                return float(v)
        return 0.0

    raw_loops.sort(key=_rank, reverse=True)
    top = raw_loops[: max(0, top_n)]
    return [_normalise_loop(loop) for loop in top]


def _normalise_loop(loop: Dict[str, Any]) -> Dict[str, Any]:
    """Project the analyzer's rich dict into a flat row we can store & ship."""
    strength = loop.get("raw_strength")
    if strength is None:
        strength = loop.get("strength") or loop.get("impact") or 0.0
    try:
        strength_f = round(float(strength), 3)
    except (TypeError, ValueError):
        strength_f = 0.0

    priority = (loop.get("strategic_priority") or "").strip().upper()
    level = _PRIORITY_LEVEL.get(priority) or _level_from_strength(strength_f)

    name = loop.get("type_name") or loop.get("type") or "Петля"
    description = loop.get("description") or name

    # break_points: store anything useful for follow-up planning.
    break_points = {
        "type":                 loop.get("type"),
        "cycle":                loop.get("cycle"),
        "length":               loop.get("length"),
        "impact":               loop.get("impact"),
        "advice":               loop.get("advice"),
        "break_timeline":       loop.get("break_timeline"),
        "effort_required":      loop.get("effort_required"),
        "recommended_resources": loop.get("recommended_resources"),
        "strategic_priority":   loop.get("strategic_priority"),
    }
    # Drop keys with None to keep the JSONB compact.
    break_points = {k: v for k, v in break_points.items() if v is not None}

    return {
        "name": name,
        "description": description,
        "strength": strength_f,
        "level": level,
        "break_points": break_points,
    }


def _level_from_strength(strength: float) -> str:
    if strength >= 0.6:
        return "critical"
    if strength >= 0.3:
        return "warn"
    return "info"
