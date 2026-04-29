"""Тесты analytics/deputy_content.py — recommend_post + recommend_weekly_plan."""

import asyncio
from typing import Any, Dict
from unittest.mock import patch

from analytics.deputy_content import recommend_post, recommend_weekly_plan


class _FakeClient:
    def __init__(self, response, enabled=True):
        self.response = response
        self.enabled = enabled
        self.last_call = None

    async def chat_json(self, system, user, **kw):
        self.last_call = {"system": system, "user": user, **kw}
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _deputy(role="district_rep", sectors=("ЖКХ",)):
    return {
        "id":       42,
        "name":     "Иванов Иван Иванович",
        "district": "Округ №3",
        "sectors":  list(sectors),
        "role":     role,
        "vk":       "ivanov",
    }


# ---------------------------------------------------------------------------
# recommend_post
# ---------------------------------------------------------------------------

def test_post_uses_llm_when_enabled():
    cli = _FakeClient({
        "title": "Прорыв трубы на Ленина",
        "body":  "Сегодня выехал на ул. Ленина...",
        "cta":   "Сообщайте о проблемах в комментариях.",
    })
    out = asyncio.run(recommend_post(
        _deputy(), "ямы на дорогах", {"top_complaints": ["прорыв"]},
        client=cli,
    ))
    assert out["title"] == "Прорыв трубы на Ленина"
    assert "архетип" not in out["body"].lower()  # LLM-ответ, не fallback
    assert out["archetype"]
    assert out["archetype_name"]


def test_post_fallback_when_llm_disabled():
    cli = _FakeClient({}, enabled=False)
    out = asyncio.run(recommend_post(
        _deputy(), "когда починят дороги", None, client=cli,
    ))
    assert out.get("fallback") is True
    assert out["archetype"]


def test_post_fallback_on_empty_request():
    cli = _FakeClient({"body": "x"})
    out = asyncio.run(recommend_post(_deputy(), "", None, client=cli))
    assert out.get("fallback") is True


def test_post_caps_long_body():
    long = "А" * 5000
    cli = _FakeClient({"title": "x", "body": long, "cta": "y"})
    out = asyncio.run(recommend_post(_deputy(), "ямы", None, client=cli))
    assert len(out["body"]) <= 1500


def test_post_includes_city_context_in_user_prompt():
    cli = _FakeClient({"title": "t", "body": "b", "cta": "c"})
    asyncio.run(recommend_post(
        _deputy(), "что писать?",
        {"top_complaints": ["прорыв трубы", "пробки"], "top_praises": ["парк"]},
        client=cli,
    ))
    user = cli.last_call["user"]
    assert "прорыв трубы" in user
    assert "парк" in user


def test_post_honors_archetype_in_prompt():
    cli = _FakeClient({"title": "t", "body": "b", "cta": "c"})
    asyncio.run(recommend_post(
        _deputy(role="speaker", sectors=("общая_повестка",)),
        "?",
        None,
        client=cli,
    ))
    user = cli.last_call["user"]
    assert "Архетип бренда" in user
    assert "Голос:" in user


# ---------------------------------------------------------------------------
# recommend_weekly_plan
# ---------------------------------------------------------------------------

def test_plan_uses_llm():
    cli = _FakeClient({
        "week_of": "2026-05-04",
        "items": [
            {"day": "пн", "topic": "X", "voice": "Y", "draft": "Z"},
            {"day": "вт", "topic": "X2", "voice": "Y2", "draft": "Z2"},
        ],
    })
    out = asyncio.run(recommend_weekly_plan(_deputy(), None, client=cli))
    assert len(out["items"]) == 2
    assert out["items"][0]["day"] == "пн"


def test_plan_caps_items_at_5():
    items = [
        {"day": str(i), "topic": "T", "voice": "V", "draft": "D"}
        for i in range(20)
    ]
    cli = _FakeClient({"week_of": "2026-05-04", "items": items})
    out = asyncio.run(recommend_weekly_plan(_deputy(), None, client=cli))
    assert len(out["items"]) == 5


def test_plan_fallback_when_llm_disabled():
    cli = _FakeClient({}, enabled=False)
    out = asyncio.run(recommend_weekly_plan(_deputy(), None, client=cli))
    assert out.get("fallback") is True
    assert len(out["items"]) == 5
    days = [it["day"] for it in out["items"]]
    assert days == ["пн", "вт", "ср", "чт", "пт"]


def test_plan_fallback_on_garbage_response():
    cli = _FakeClient({"week_of": "2026-05-04", "items": "not-a-list"})
    out = asyncio.run(recommend_weekly_plan(_deputy(), None, client=cli))
    # Должен fallback'нуться
    assert out.get("fallback") is True


def test_plan_includes_archetype_code():
    cli = _FakeClient({}, enabled=False)
    out = asyncio.run(recommend_weekly_plan(
        _deputy(sectors=("соцзащита",)), None, client=cli,
    ))
    assert out["archetype"]
    assert out["archetype_name"]
