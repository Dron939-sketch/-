"""Unit tests for the decision library."""

from __future__ import annotations

import pytest

from analytics.decisions import filter_for, get_decision, list_decisions


def test_library_is_not_empty():
    decisions = list_decisions()
    assert len(decisions) >= 8


def test_every_decision_has_three_scenarios():
    for d in list_decisions():
        assert set(d.scenarios.keys()) == {"optimistic", "realistic", "pessimistic"}


def test_every_decision_exposes_stable_dict_shape():
    d = list_decisions()[0].to_dict()
    assert set(d.keys()) == {
        "id", "name", "description", "primary_vector",
        "cost_rub", "duration_months", "tags", "risks", "scenarios",
    }
    scenario = d["scenarios"]["realistic"]
    assert set(scenario.keys()) == {
        "label", "safety", "economy", "quality", "social", "note",
    }


def test_scenarios_stronger_in_optimistic_than_pessimistic():
    # For each decision, the sum of all 4 vector deltas should follow
    # optimistic >= realistic >= pessimistic.
    for d in list_decisions():
        def _total(s):
            return s.safety + s.economy + s.quality + s.social

        o = _total(d.scenarios["optimistic"])
        r = _total(d.scenarios["realistic"])
        p = _total(d.scenarios["pessimistic"])
        assert o >= r >= p, f"{d.id}: {o} / {r} / {p} not monotone"


def test_filter_by_primary_vector_includes_all_matching():
    safety = filter_for("safety")
    ids = {d.id for d in safety}
    assert "cam_network" in ids
    # All returned decisions must either have primary_vector=safety or a
    # significant safety effect in the realistic scenario.
    for d in safety:
        realistic_safety = d.scenarios["realistic"].safety
        assert d.primary_vector == "safety" or abs(realistic_safety) >= 0.15


def test_filter_by_unknown_vector_returns_empty():
    assert filter_for("made_up") == []


def test_filter_without_vector_returns_all():
    assert len(filter_for()) == len(list_decisions())


def test_get_decision_by_id():
    d = get_decision("cam_network")
    assert d is not None
    assert d.name.startswith("Расширение")


def test_get_decision_missing_id_returns_none():
    assert get_decision("nonexistent_id") is None


def test_costs_are_positive_and_durations_sensible():
    for d in list_decisions():
        assert d.cost_rub > 0
        assert 1 <= d.duration_months <= 36


def test_tags_and_risks_are_non_empty_tuples():
    for d in list_decisions():
        assert isinstance(d.tags, tuple)
        assert len(d.tags) >= 1
        assert isinstance(d.risks, tuple)
        assert len(d.risks) >= 1


def test_decisions_cover_all_four_vectors():
    primaries = {d.primary_vector for d in list_decisions()}
    assert primaries >= {"safety", "economy", "quality", "social"}
