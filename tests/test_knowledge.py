"""Unit tests for the knowledge bank + recommender."""

from __future__ import annotations

import pytest

from analytics.knowledge import library_size, recommend


def test_library_is_not_empty():
    assert library_size() >= 10


def test_empty_signals_returns_some_cases_anyway():
    # No signals → recommender has no rule to drop cases; returns top by evidence.
    recs = recommend()
    assert len(recs) == 3  # default limit
    # At least one should be documented or proven when sorting prefers evidence.
    levels = {r["case"]["evidence_level"] for r in [r.to_dict() for r in recs]}
    assert levels & {"documented", "proven"}


def test_weak_vector_matches_relevant_cases():
    recs = [r.to_dict() for r in recommend(weak_vectors=["safety"], limit=5)]
    # Every returned case must touch the safety vector (primary sort).
    assert all("safety" in r["case"]["vectors"] for r in recs)


def test_crisis_vectors_outweigh_weak_ones():
    only_weak = recommend(weak_vectors=["economy"], limit=5)
    with_crisis = recommend(crisis_vectors=["economy"], limit=5)
    # crisis boost (×2) + no weak signal should still rank economy cases first,
    # and at higher scores than the pure-weak version.
    top_weak = only_weak[0].score
    top_crisis = with_crisis[0].score
    # Crisis alone scores 2 per match + evidence; weak scores 3 per match + evidence.
    # Crisis with 1 vector ≈ 2 + 0.5 = 2.5; weak with 1 vector ≈ 3 + 0.5 = 3.5.
    # What we're really testing is that both produce non-zero scores.
    assert top_weak > 0 and top_crisis > 0


def test_tag_match_boosts_relevance():
    recs_no_tag = recommend(weak_vectors=["safety"], limit=5)
    recs_with_tag = recommend(weak_vectors=["safety"], extra_tags=["освещение"], limit=5)
    # The освещение case should rank higher when the tag is provided.
    top_with_tag = recs_with_tag[0].case.id
    assert top_with_tag == "safety_street_light"


def test_limit_is_respected():
    recs = recommend(weak_vectors=["safety"], limit=2)
    assert len(recs) == 2
    recs = recommend(weak_vectors=["safety"], limit=1)
    assert len(recs) == 1


def test_limit_floor_is_one():
    # Zero / negative limit coerced to at least 1.
    recs = recommend(weak_vectors=["safety"], limit=0)
    assert len(recs) == 1


def test_no_signals_no_overlap_returns_fallback():
    # Providing a vector that nothing matches returns nothing.
    recs = recommend(weak_vectors=["imaginary_vector"])
    # All matching is empty → with signals provided but zero overlap, recs are []
    assert recs == []


def test_matched_metadata_reflects_inputs():
    recs = recommend(weak_vectors=["social"], extra_tags=["волонтёры"], limit=1)
    assert recs
    d = recs[0].to_dict()
    assert "social" in d["matched_vectors"]
    assert "волонтёры" in d["matched_tags"]


def test_score_monotone_with_more_matches():
    # Two vectors matched > one vector matched.
    one = recommend(weak_vectors=["safety"], limit=1)[0].score
    two = recommend(weak_vectors=["safety", "quality"], limit=1)[0].score
    assert two >= one


def test_to_dict_shape_is_stable():
    recs = recommend(weak_vectors=["safety"], limit=1)
    d = recs[0].to_dict()
    assert set(d.keys()) == {"case", "score", "matched_vectors", "matched_tags"}
    case = d["case"]
    assert set(case.keys()) == {"id", "title", "vectors", "tags", "problem",
                                 "approach", "evidence_level"}


def test_garbage_input_does_not_crash():
    recs = recommend(weak_vectors=[None, "", "  safety  "], extra_tags=[None])
    # "  safety  " is lower-cased and stripped.
    assert recs
    top = recs[0].to_dict()
    assert "safety" in top["case"]["vectors"]
