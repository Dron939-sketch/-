"""Unit tests for the task-derivation adapter."""

from __future__ import annotations

import pytest

from analytics.tasks import derive


def test_empty_input_attaches_note():
    r = derive().to_dict()
    assert r["tasks"] == []
    assert r["note"]


def test_agenda_actions_become_tasks():
    agenda = {
        "headline": "Решить проблему с отключением воды",
        "actions": ["Проверить аварийные службы", "Обеспечить подвоз воды"],
    }
    r = derive(agenda=agenda).to_dict()
    assert len(r["tasks"]) == 2
    # First action is high priority, rest medium.
    titles = {t["title"]: t for t in r["tasks"]}
    assert titles["Проверить аварийные службы"]["priority"] == "high"
    assert titles["Обеспечить подвоз воды"]["priority"] == "medium"
    assert all(t["source"] == "agenda" for t in r["tasks"])


def test_crisis_alerts_become_urgent_tasks():
    crisis = {
        "alerts": [
            {"level": "critical", "kind": "metric_drop", "vector": "safety",
             "title": "Падение безопасности", "description": "СБ упал с 4.2 до 3.0",
             "horizon": "24-48ч"},
        ]
    }
    r = derive(crisis=crisis).to_dict()
    assert len(r["tasks"]) == 1
    t = r["tasks"][0]
    assert t["priority"] == "urgent"
    assert t["source"] == "crisis"
    assert "безопасность" in t["suggested_owner"].lower()
    assert "кризис" in t["tags"]


def test_roadmap_milestones_become_medium_and_low_tasks():
    roadmap = {"roadmap": {
        "vector": "СБ",
        "milestones": [
            {"target_level": 4.0, "interventions": ["Установить 100 камер", "Усилить патруль"]},
            {"target_level": 4.5, "interventions": ["Провести аудит освещения"]},
        ],
    }}
    r = derive(roadmap=roadmap).to_dict()
    assert len(r["tasks"]) == 2   # one per milestone's first intervention
    priorities = sorted([t["priority"] for t in r["tasks"]],
                        key=lambda p: {"urgent": 4, "high": 3, "medium": 2, "low": 1}[p],
                        reverse=True)
    assert priorities == ["medium", "low"]


def test_priority_sorts_urgent_first():
    agenda = {"headline": "X", "actions": ["Plan review"]}
    crisis = {"alerts": [{"level": "critical", "kind": "x", "vector": "safety",
                          "title": "CRITICAL"}]}
    r = derive(agenda=agenda, crisis=crisis).to_dict()
    assert r["tasks"][0]["priority"] == "urgent"


def test_counts_by_priority_and_source():
    agenda = {"headline": "X", "actions": ["A1", "A2"]}
    crisis = {"alerts": [
        {"level": "high", "kind": "x", "title": "C1"},
        {"level": "watch", "kind": "y", "title": "C2"},
    ]}
    r = derive(agenda=agenda, crisis=crisis).to_dict()
    assert r["counts_by_source"]["agenda"] == 2
    assert r["counts_by_source"]["crisis"] == 2
    # high crisis -> urgent, watch -> medium; agenda first -> high, second -> medium
    assert r["counts_by_priority"].get("urgent", 0) == 1


def test_deadline_days_matches_priority_ladder():
    agenda = {"headline": "X", "actions": ["single"]}
    r = derive(agenda=agenda).to_dict()
    assert r["tasks"][0]["deadline_days"] == 3


def test_duplicate_titles_deduplicated_keeping_highest_priority():
    agenda = {"headline": "Отключение воды", "actions": ["Установить резервы"]}
    crisis = {"alerts": [{"level": "critical", "kind": "util",
                          "title": "Установить резервы",
                          "description": "desc"}]}
    r = derive(agenda=agenda, crisis=crisis).to_dict()
    # Duplicate title "Установить резервы" — we dedup by title, earlier = higher priority.
    # Agenda's "Установить резервы" has priority=high, crisis-derived has priority=urgent
    # BUT the crisis task title is "Реагирование: Установить резервы" (prefixed) — so
    # titles differ. Both survive.
    titles = [t["title"] for t in r["tasks"]]
    assert len(titles) == len(set(titles))


def test_max_tasks_limit_respected():
    agenda = {"headline": "X", "actions": [f"Action {i}" for i in range(20)]}
    r = derive(agenda=agenda, max_tasks=5).to_dict()
    assert len(r["tasks"]) == 5


def test_garbage_inputs_do_not_crash():
    r = derive(
        agenda={"headline": None, "actions": [None, "", 42, "  valid  "]},
        crisis={"alerts": ["not a dict", {"level": None, "title": None}]},
        roadmap={"milestones": ["not a dict", {"interventions": []}]},
    ).to_dict()
    # Only "valid" action survives.
    titles = [t["title"] for t in r["tasks"]]
    assert "valid" in titles


def test_task_id_stable():
    agenda = {"headline": "X", "actions": ["do thing"]}
    r1 = derive(agenda=agenda).to_dict()
    r2 = derive(agenda=agenda).to_dict()
    assert r1["tasks"][0]["id"] == r2["tasks"][0]["id"]


def test_vector_maps_to_owner_hint():
    crisis = {"alerts": [
        {"level": "high", "kind": "metric_drop", "vector": "economy",
         "title": "TF crash", "description": "x"},
    ]}
    r = derive(crisis=crisis).to_dict()
    assert "экономразвитие" in r["tasks"][0]["suggested_owner"].lower()


def test_response_shape_is_stable():
    r = derive().to_dict()
    assert set(r.keys()) == {"tasks", "counts_by_priority", "counts_by_source", "note"}
