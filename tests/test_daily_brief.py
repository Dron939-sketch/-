"""Тесты run_daily_brief — сводка дня."""

import asyncio
from unittest.mock import patch

import pytest


def _run_brief(mocks: dict):
    from api.copilot_routes import _run_daily_brief

    patches = []
    if "city_pulse" in mocks:
        patches.append(patch("api.routes.city_pulse",
                              lambda _: mocks["city_pulse"]))
    if "city_crisis" in mocks:
        patches.append(patch("api.routes.city_crisis",
                              lambda _: mocks["city_crisis"]))
    if "latest_metrics" in mocks:
        patches.append(patch("db.queries.latest_metrics",
                              lambda _: mocks["latest_metrics"]))
    if "list_topics" in mocks:
        patches.append(patch("db.deputy_queries.list_topics",
                              lambda *a, **kw: mocks["list_topics"]))
    if "news_window" in mocks:
        patches.append(patch("db.queries.news_window",
                              lambda *a, **kw: mocks["news_window"]))

    async def call():
        return await _run_daily_brief("Коломна", 42)

    # Wrap each lambda in a coroutine
    async def _async_return(value):
        return value

    # Convert sync mocks to async - simpler: use side_effect
    for p in patches:
        p.start()
    try:
        return asyncio.run(call())
    finally:
        for p in patches:
            p.stop()


def test_daily_brief_quiet_when_nothing_works():
    """Если все источники возвращают None/[]/пусто — fallback-фраза."""
    async def empty(*a, **kw): return None

    with patch("api.routes.city_pulse", empty), \
         patch("api.routes.city_crisis", empty), \
         patch("db.queries.latest_metrics", empty), \
         patch("db.deputy_queries.list_topics",
               lambda *a, **kw: []) as _, \
         patch("db.queries.news_window",
               lambda *a, **kw: []):
        from api.copilot_routes import _run_daily_brief
        # list_topics + news_window возвращают coroutine, обернём:
        async def empty_list(*a, **kw): return []
        with patch("db.deputy_queries.list_topics", empty_list), \
             patch("db.queries.news_window", empty_list):
            text, src = asyncio.run(_run_daily_brief("Коломна", 42))
        assert "сводка" in text.lower() or "тихо" in text.lower() or "мало" in text.lower()
        assert src == ["daily_brief"]


def test_daily_brief_has_pulse_score():
    async def fake_pulse(_): return {"score": 72.4, "grade": "OK"}
    async def fake_crisis(_): return {"alerts": []}
    async def fake_metrics(_): return None
    async def empty_list(*a, **kw): return []

    with patch("api.routes.city_pulse", fake_pulse), \
         patch("api.routes.city_crisis", fake_crisis), \
         patch("db.queries.latest_metrics", fake_metrics), \
         patch("db.deputy_queries.list_topics", empty_list), \
         patch("db.queries.news_window", empty_list):
        from api.copilot_routes import _run_daily_brief
        text, _ = asyncio.run(_run_daily_brief("Коломна", 42))
    assert "72" in text
    assert "100" in text
    assert "кризис-радар чист" in text


def test_daily_brief_low_metrics():
    async def fake_pulse(_): return None
    async def fake_crisis(_): return {"alerts": [{"title": "a"}, {"title": "b"}]}
    async def fake_metrics(_):
        return {"sb": 4.0, "tf": 4.5, "ub": 2.6, "chv": 2.9}
    async def empty_list(*a, **kw): return []

    with patch("api.routes.city_pulse", fake_pulse), \
         patch("api.routes.city_crisis", fake_crisis), \
         patch("db.queries.latest_metrics", fake_metrics), \
         patch("db.deputy_queries.list_topics", empty_list), \
         patch("db.queries.news_window", empty_list):
        from api.copilot_routes import _run_daily_brief
        text, _ = asyncio.run(_run_daily_brief("Коломна", 42))
    assert "просели" in text
    assert "УБ 2.6" in text
    assert "ЧВ 2.9" in text
    assert "СБ" not in text  # СБ=4.0 нормальный
    assert "2 алертов" in text or "кризис-алертов: 2" in text


def test_daily_brief_includes_active_topics_count():
    async def fake_pulse(_): return None
    async def fake_crisis(_): return None
    async def fake_metrics(_): return None
    async def fake_topics(*a, **kw):
        return [{"title": "t1"}, {"title": "t2"}, {"title": "t3"}]
    async def empty_list(*a, **kw): return []

    with patch("api.routes.city_pulse", fake_pulse), \
         patch("api.routes.city_crisis", fake_crisis), \
         patch("db.queries.latest_metrics", fake_metrics), \
         patch("db.deputy_queries.list_topics", fake_topics), \
         patch("db.queries.news_window", empty_list):
        from api.copilot_routes import _run_daily_brief
        text, _ = asyncio.run(_run_daily_brief("Коломна", 42))
    assert "3 активных тем" in text


def test_daily_brief_news_count():
    async def fake_pulse(_): return None
    async def fake_crisis(_): return None
    async def fake_metrics(_): return None
    async def empty_list(*a, **kw): return []
    async def fake_news(*a, **kw):
        return [{"x": i} for i in range(7)]

    with patch("api.routes.city_pulse", fake_pulse), \
         patch("api.routes.city_crisis", fake_crisis), \
         patch("db.queries.latest_metrics", fake_metrics), \
         patch("db.deputy_queries.list_topics", empty_list), \
         patch("db.queries.news_window", fake_news):
        from api.copilot_routes import _run_daily_brief
        text, _ = asyncio.run(_run_daily_brief("Коломна", 42))
    assert "свежих новостей: 7" in text
