"""Tests for the roadmap planner."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from agenda.roadmap_planner import RoadmapPlanner


def test_baseline_scenario_produces_monotonic_plan():
    planner = RoadmapPlanner("Коломна")
    plan = planner.plan(
        vector="УБ",
        start_level=3.0,
        target_level=5.0,
        deadline=date.today() + timedelta(days=365),
        scenario="baseline",
    )
    levels = [m.target_level for m in plan.milestones]
    assert levels == sorted(levels)
    assert levels[-1] == pytest.approx(5.0, abs=0.01)
    assert plan.total_cost_rub > 0


def test_rejects_non_positive_gap():
    planner = RoadmapPlanner("Коломна")
    with pytest.raises(ValueError):
        planner.plan(
            vector="СБ",
            start_level=5.0,
            target_level=5.0,
            deadline=date.today() + timedelta(days=90),
        )


def test_rejects_past_deadline():
    planner = RoadmapPlanner("Коломна")
    with pytest.raises(ValueError):
        planner.plan(
            vector="СБ",
            start_level=2.0,
            target_level=4.0,
            deadline=date.today() - timedelta(days=1),
        )


def test_optimistic_is_front_loaded():
    planner = RoadmapPlanner("Коломна")
    deadline = date.today() + timedelta(days=360)
    baseline = planner.plan(
        vector="ТФ", start_level=2.0, target_level=5.0,
        deadline=deadline, scenario="baseline",
    )
    optimistic = planner.plan(
        vector="ТФ", start_level=2.0, target_level=5.0,
        deadline=deadline, scenario="optimistic",
    )
    # halfway through the plan, optimistic scenario is farther along
    mid = len(baseline.milestones) // 2
    assert optimistic.milestones[mid].target_level >= baseline.milestones[mid].target_level
