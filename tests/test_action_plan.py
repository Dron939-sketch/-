"""Тесты run_action_plan — маршрут к решению."""

import asyncio
from unittest.mock import patch


async def _empty(*a, **kw): return None
async def _empty_list(*a, **kw): return []


def test_action_plan_uses_query_as_problem():
    """Если передан query — он попадает в problems[0]."""
    from api.copilot_routes import _run_action_plan

    captured = {}

    class _FakeGen:
        def __init__(self, city): self.city = city
        def create_daily_plan(self, problems, metrics=None, trends=None):
            captured["problems"] = list(problems)
            captured["metrics"] = metrics
            captured["trends"]  = trends

            class A:
                title = "Запросить инспекцию"
                deadline_days = 3
                class responsible:
                    role = "Зам по ЖКХ"

            class P:
                summary = "1 критич, 0 важных; Всего: 1 поручение"
                actions = [A()]

            return P()

    with patch("analytics.action_generator.ActionGenerator", _FakeGen), \
         patch("api.routes._build_agenda", _empty), \
         patch("db.queries.latest_metrics", _empty), \
         patch("db.queries.metrics_trend_7d", _empty):
        text, src = asyncio.run(_run_action_plan("Коломна", 42, "как поднять УБ"))

    assert "Шаг 1" in text
    assert "Запросить инспекцию" in text
    assert "Зам по ЖКХ" in text
    assert "3 дн" in text
    assert "как поднять УБ" in captured["problems"]


def test_action_plan_uses_agenda_complaints():
    """Когда query пустой — берём top complaints из agenda."""
    from api.copilot_routes import _run_action_plan

    class _Agenda:
        top_complaints = ["прорыв трубы", "ямы на дорогах"]

    async def fake_agenda(*a, **kw): return _Agenda()

    captured = {}

    class _FakeGen:
        def __init__(self, city): self.city = city
        def create_daily_plan(self, problems, **kw):
            captured["problems"] = list(problems)
            class A:
                title = "Действие"
                deadline_days = 5
                class responsible:
                    role = "Зам"
            class P:
                summary = ""
                actions = [A()]
            return P()

    with patch("analytics.action_generator.ActionGenerator", _FakeGen), \
         patch("api.routes._build_agenda", fake_agenda), \
         patch("db.queries.latest_metrics", _empty), \
         patch("db.queries.metrics_trend_7d", _empty):
        asyncio.run(_run_action_plan("Коломна", 42, None))

    assert "прорыв трубы" in captured["problems"]
    assert "ямы на дорогах" in captured["problems"]


def test_action_plan_caps_at_three_steps():
    """Если генератор выдал больше 3 — в голос идут только первые 3."""
    from api.copilot_routes import _run_action_plan

    class _FakeGen:
        def __init__(self, city): pass
        def create_daily_plan(self, problems, **kw):
            class A:
                def __init__(self, n):
                    self.title = f"Step{n}"
                    self.deadline_days = n
                    class R:
                        role = "X"
                    self.responsible = R()
            class P:
                summary = ""
                actions = [A(i) for i in range(1, 8)]
            return P()

    with patch("analytics.action_generator.ActionGenerator", _FakeGen), \
         patch("api.routes._build_agenda", _empty), \
         patch("db.queries.latest_metrics", _empty), \
         patch("db.queries.metrics_trend_7d", _empty):
        text, _ = asyncio.run(_run_action_plan("Коломна", 42, "Q"))

    assert "Шаг 1" in text and "Шаг 2" in text and "Шаг 3" in text
    assert "Шаг 4" not in text
    assert "Шаг 5" not in text


def test_action_plan_no_actions_returns_friendly_text():
    from api.copilot_routes import _run_action_plan

    class _FakeGen:
        def __init__(self, city): pass
        def create_daily_plan(self, problems, **kw):
            class P:
                summary = ""
                actions = []
            return P()

    with patch("analytics.action_generator.ActionGenerator", _FakeGen), \
         patch("api.routes._build_agenda", _empty), \
         patch("db.queries.latest_metrics", _empty), \
         patch("db.queries.metrics_trend_7d", _empty):
        text, _ = asyncio.run(_run_action_plan("Коломна", 42, "?"))

    assert "конкретных шагов не вижу" in text or "Сформулируй" in text


def test_action_plan_handles_metrics_unit_conversion():
    """Метрики 1..6 переводятся в 0..1 для action_generator."""
    from api.copilot_routes import _run_action_plan

    captured = {}

    class _FakeGen:
        def __init__(self, city): pass
        def create_daily_plan(self, problems, metrics=None, trends=None):
            captured["metrics"] = metrics
            class A:
                title = "x"; deadline_days = 1
                class responsible:
                    role = "y"
            class P:
                summary = ""
                actions = [A()]
            return P()

    async def fake_metrics(_): return {"sb": 4.2, "tf": 3.0, "ub": 3.6, "chv": 2.4}
    async def fake_trend(_):   return None
    async def fake_agenda(*a, **kw): return None

    with patch("analytics.action_generator.ActionGenerator", _FakeGen), \
         patch("api.routes._build_agenda", fake_agenda), \
         patch("db.queries.latest_metrics", fake_metrics), \
         patch("db.queries.metrics_trend_7d", fake_trend):
        asyncio.run(_run_action_plan("Коломна", 42, "Q"))

    m = captured["metrics"]
    # 4.2 / 6 ≈ 0.7
    assert abs(m["safety"] - 0.7) < 0.01
    # 2.4 / 6 = 0.4
    assert abs(m["social"] - 0.4) < 0.01
