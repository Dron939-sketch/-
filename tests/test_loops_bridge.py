"""Offline tests for the loops bridge.

We don't exercise the real `ConfinementModel9` here — that belongs in an
integration suite with a snapshot of the legacy core. The unit tests
cover the pure parts: vector projection and the raw-loop normalisation
path.
"""

from __future__ import annotations

from analytics.loops import _normalise_loop, metrics_to_vectors


def test_metrics_to_vectors_accepts_db_row_shape():
    snapshot = {"sb": 4.2, "tf": 3.1, "ub": 3.8, "chv": 2.5}
    out = metrics_to_vectors(snapshot)
    assert out == {"СБ": 4.2, "ТФ": 3.1, "УБ": 3.8, "ЧВ": 2.5}


def test_metrics_to_vectors_accepts_russian_keys():
    snapshot = {"СБ": 5.0, "ТФ": 5.0, "УБ": 5.0, "ЧВ": 5.0}
    assert metrics_to_vectors(snapshot) == snapshot


def test_metrics_to_vectors_fills_missing_with_baseline():
    out = metrics_to_vectors({"sb": 6.0})
    assert out == {"СБ": 6.0, "ТФ": 3.5, "УБ": 3.5, "ЧВ": 3.5}


def test_metrics_to_vectors_treats_none_as_missing():
    out = metrics_to_vectors({"sb": None, "tf": 4.0, "ub": None, "chv": None})
    assert out["СБ"] == 3.5
    assert out["ТФ"] == 4.0
    assert out["УБ"] == 3.5
    assert out["ЧВ"] == 3.5


def test_normalise_loop_maps_strategic_priority_to_level():
    raw = {
        "type_name": "Петля безопасности",
        "description": "🔴 описание",
        "raw_strength": 0.42,
        "impact": 0.5,
        "cycle": [1, 2, 3, 1],
        "strategic_priority": "ВЫСОКИЙ",
    }
    out = _normalise_loop(raw)
    assert out["name"] == "Петля безопасности"
    assert out["description"] == "🔴 описание"
    assert out["strength"] == 0.42
    assert out["level"] == "critical"
    assert out["break_points"]["cycle"] == [1, 2, 3, 1]


def test_normalise_loop_falls_back_to_strength_based_level():
    # No priority → level derived from strength.
    assert _normalise_loop({"type_name": "X", "raw_strength": 0.7})["level"] == "critical"
    assert _normalise_loop({"type_name": "X", "raw_strength": 0.4})["level"] == "warn"
    assert _normalise_loop({"type_name": "X", "raw_strength": 0.1})["level"] == "info"


def test_normalise_loop_drops_none_fields_from_break_points():
    raw = {
        "type_name": "Y",
        "raw_strength": 0.25,
        "advice": "совет",
        "break_timeline": None,
        "effort_required": None,
    }
    out = _normalise_loop(raw)
    assert out["break_points"] == {"advice": "совет"}


def test_normalise_loop_handles_missing_strength_gracefully():
    out = _normalise_loop({"type": "безопасность"})
    assert out["strength"] == 0.0
    assert out["name"] == "безопасность"
    assert out["level"] == "info"
