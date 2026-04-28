"""Тесты расширенного копилот-промпта (тренды + crisis) + emotion-injection."""

from __future__ import annotations

import asyncio

from ai.copilot import _build_system_prompt, build_user_prompt, chat


def test_prompt_contains_trend_when_present():
    p = build_user_prompt(
        "что слышно?", {
            "name": "Коломна",
            "trend_7d": {"sb": 0.4, "ub": -0.6, "tf": None, "chv": 0.0},
        }, [],
    )
    assert "Тренд за 7 дней" in p
    assert "СБ +0.4" in p
    assert "УБ -0.6" in p
    # ТФ=None пропущен, ЧВ=0.0 пропущен (порог 0.05)
    assert "ТФ" not in p
    assert "ЧВ" not in p


def test_prompt_contains_crisis_alerts():
    p = build_user_prompt(
        "что у нас?", {
            "name": "Коломна",
            "crisis": {"level": "high", "alerts": ["прорыв трубы", "массовые жалобы"]},
        }, [],
    )
    assert "Кризис-радар" in p
    assert "high" in p
    assert "прорыв трубы" in p


def test_prompt_skips_zero_trends():
    p = build_user_prompt(
        "?", {"name": "Коломна", "trend_7d": {"sb": 0.0, "ub": 0.01}}, [],
    )
    assert "Тренд за 7 дней" not in p


def test_system_prompt_injects_emotion_instruction():
    sp = _build_system_prompt({
        "emotion": "sadness", "tone": "gentle",
        "instruction": "Будь мягким, не сыпь цифрами.",
    })
    assert "gentle" in sp.lower()
    assert "мягким" in sp


def test_system_prompt_includes_time_of_day():
    sp = _build_system_prompt({
        "emotion": "neutral", "tone": "friendly", "instruction": "",
    })
    # Один из 4-х: утро/день/вечер/ночь
    assert any(w in sp for w in ("утро", "день", "вечер", "ночь"))


# ---------------------------------------------------------------------------
# chat() возвращает emotion+tone в ответе
# ---------------------------------------------------------------------------

class _FakeClient:
    def __init__(self, response, enabled=True):
        self.response = response
        self.enabled = enabled

    async def chat_json(self, system, user, **kw):
        return self.response


def test_chat_returns_emotion_field():
    cli = _FakeClient({"text": "ок"})
    out = asyncio.run(chat("Мне грустно", {"name": "Коломна"}, [], client=cli))
    assert out.get("emotion") == "sadness"
    assert out.get("tone") == "gentle"


def test_chat_neutral_when_no_emotion():
    cli = _FakeClient({"text": "ок"})
    out = asyncio.run(chat("Что у нас с метриками?", {"name": "Коломна"}, [], client=cli))
    assert out.get("emotion") == "neutral"


def test_chat_run_action_passes_through_whitelist():
    cli = _FakeClient({"text": "посмотрим", "action": "run_pulse"})
    out = asyncio.run(chat("Какой пульс?", {"name": "Коломна"}, [], client=cli))
    assert out["action"] == "run_pulse"


def test_chat_unknown_run_action_stripped():
    cli = _FakeClient({"text": "ок", "action": "run_unicorn"})
    out = asyncio.run(chat("?", {"name": "Коломна"}, [], client=cli))
    assert out["action"] is None
