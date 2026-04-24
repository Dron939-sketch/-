"""Unit tests for the Eisenhower matrix bucketing."""

from __future__ import annotations

import pytest

from analytics.eisenhower import bucket, classify


def _task(priority="medium", source="agenda", deadline_days=7, title="x"):
    return {
        "title": title, "priority": priority, "source": source,
        "deadline_days": deadline_days, "rationale": "...",
        "suggested_owner": "Администрация", "tags": [],
    }


def test_empty_list_returns_empty_quadrants_with_note():
    r = bucket([]).to_dict()
    assert r["total"] == 0
    for key in ("do_first", "schedule", "delegate", "eliminate"):
        assert r["quadrants"][key]["count"] == 0
    assert r["note"]


def test_urgent_crisis_goes_to_do_first():
    assert classify(_task(priority="urgent", source="crisis", deadline_days=1)) == "do_first"


def test_medium_roadmap_goes_to_schedule():
    assert classify(_task(priority="medium", source="roadmap", deadline_days=7)) == "schedule"


def test_urgent_low_priority_agenda_goes_to_delegate():
    # urgent by deadline, but priority=low and source=agenda → not important → delegate.
    # deadline_days=2 triggers urgency, low priority is not important.
    t = _task(priority="low", source="agenda", deadline_days=2)
    assert classify(t) == "delegate"


def test_low_priority_agenda_with_long_deadline_eliminated():
    t = _task(priority="low", source="agenda", deadline_days=14)
    assert classify(t) == "eliminate"


def test_counts_add_up_to_total():
    tasks = [
        _task(priority="urgent", source="crisis", deadline_days=1),
        _task(priority="high", source="agenda", deadline_days=3),
        _task(priority="medium", source="roadmap", deadline_days=7),
        _task(priority="medium", source="agenda", deadline_days=14),
        _task(priority="low", source="agenda", deadline_days=14),
    ]
    r = bucket(tasks).to_dict()
    assert r["total"] == 5
    total_in_quadrants = sum(q["count"] for q in r["quadrants"].values())
    assert total_in_quadrants == 5


def test_response_shape_stable():
    r = bucket([_task()]).to_dict()
    assert set(r.keys()) == {"quadrants", "total", "note"}
    for key in ("do_first", "schedule", "delegate", "eliminate"):
        q = r["quadrants"][key]
        assert set(q.keys()) == {"key", "label", "description", "count", "tasks"}


def test_roadmap_low_priority_is_important():
    # Roadmap source trumps low priority — stays in schedule instead of eliminate.
    t = _task(priority="low", source="roadmap", deadline_days=14)
    assert classify(t) == "schedule"


def test_urgent_roadmap_goes_to_do_first():
    # Short deadline on roadmap intervention bumps to do_first.
    t = _task(priority="medium", source="roadmap", deadline_days=2)
    assert classify(t) == "do_first"


def test_garbage_values_do_not_crash():
    r = bucket([
        {"priority": None, "source": None, "deadline_days": None},
        "not a dict",
        {"priority": "unknown", "deadline_days": "bad"},
    ]).to_dict()
    # Only the 2 dict-shaped items are bucketed; "not a dict" is skipped.
    assert r["total"] == 3
    assert sum(q["count"] for q in r["quadrants"].values()) == 2
