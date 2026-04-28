"""Тесты Ко-пилота (ai/copilot.py): сборка промпта, парсинг ответа,
fallback'и и whitelisting actions."""

from __future__ import annotations

import asyncio

from ai.copilot import (
    ALLOWED_ACTIONS,
    MAX_HISTORY_TURNS,
    build_user_prompt,
    chat,
)


# ---------------------------------------------------------------------------
# build_user_prompt
# ---------------------------------------------------------------------------

def test_prompt_has_question():
    p = build_user_prompt("Что у нас с дорогами?", {"name": "Коломна"}, [])
    assert "Что у нас с дорогами?" in p
    assert "Коломна" in p


def test_prompt_includes_metrics_when_present():
    p = build_user_prompt(
        "Расскажи показатели",
        {"name": "Коломна", "metrics": {"sb": 4.1, "ub": 3.7, "tf": None, "chv": 2.9}},
        [],
    )
    assert "4.1/6" in p and "3.7/6" in p and "2.9/6" in p
    assert "Социально-бытовой" in p
    assert "Транспортно-финансовый" not in p  # пропущен из-за None


def test_prompt_includes_history_recent_only():
    history = [
        {"role": "user",      "text": f"вопрос-{i}"}
        for i in range(MAX_HISTORY_TURNS + 5)
    ]
    p = build_user_prompt("новый вопрос", {"name": "Коломна"}, history)
    # Старые turn'ы выходят за окно
    assert "вопрос-0" not in p
    # Последние — в промпте
    assert f"вопрос-{MAX_HISTORY_TURNS + 4}" in p


def test_prompt_handles_empty_history():
    p = build_user_prompt("?", {"name": "Коломна"}, [])
    assert "Контекст недавнего диалога" not in p


def test_prompt_has_active_topics():
    p = build_user_prompt(
        "что закрывают депутаты?",
        {"name": "Коломна", "active_topics": ["ЖКХ: всплеск жалоб", "Снижение УБ"]},
        [],
    )
    assert "Активные темы депутатов" in p
    assert "ЖКХ: всплеск жалоб" in p


# ---------------------------------------------------------------------------
# chat() — fake DeepSeek client
# ---------------------------------------------------------------------------

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


def test_chat_returns_text_action_sources():
    cli = _FakeClient({
        "text": "По дорогам жалоб нет.",
        "action": "open_scenario",
        "sources": ["метрика УБ", "новости за 3 дня"],
    })
    out = asyncio.run(chat("дороги?", {"name": "Коломна"}, [], client=cli))
    assert out["text"] == "По дорогам жалоб нет."
    assert out["action"] == "open_scenario"
    assert "метрика УБ" in out["sources"]


def test_chat_strips_unknown_action():
    cli = _FakeClient({"text": "Готово.", "action": "do_evil_thing", "sources": []})
    out = asyncio.run(chat("?", {"name": "Коломна"}, [], client=cli))
    assert out["action"] is None  # не whitelisted → None


def test_chat_handles_null_action_string():
    cli = _FakeClient({"text": "Ok", "action": "null"})
    out = asyncio.run(chat("?", {"name": "Коломна"}, [], client=cli))
    assert out["action"] is None


def test_chat_caps_text_length():
    long = "а" * 2000
    cli = _FakeClient({"text": long})
    out = asyncio.run(chat("?", {"name": "Коломна"}, [], client=cli))
    assert len(out["text"]) <= 1200


def test_chat_caps_sources_count():
    cli = _FakeClient({"text": "ok", "sources": [f"s{i}" for i in range(20)]})
    out = asyncio.run(chat("?", {"name": "Коломна"}, [], client=cli))
    assert len(out["sources"]) <= 6


def test_chat_falls_back_on_error():
    from ai.deepseek_client import DeepSeekError
    cli = _FakeClient(DeepSeekError("boom"))
    out = asyncio.run(chat("Запусти сценарий", {"name": "Коломна"}, [], client=cli))
    # Фолбэк должен по ключевому слову «сценар» предложить open_scenario
    assert out["action"] == "open_scenario"


def test_chat_fallback_when_disabled_client():
    cli = _FakeClient({"text": "wont be used"}, enabled=False)
    out = asyncio.run(chat("Открой генератор поручений", {"name": "Коломна"}, [], client=cli))
    assert out["action"] == "open_actions"
    assert cli.last_call is None  # вызова реально не было


def test_chat_empty_question_returns_prompt():
    out = asyncio.run(chat("", None, []))
    assert "слушаю" in out["text"].lower() or "ассистент" in out["text"].lower() or out["text"]


def test_chat_history_passed_into_user_prompt():
    cli = _FakeClient({"text": "ok"})
    history = [{"role": "user", "text": "вчера говорили про дороги"}]
    asyncio.run(chat("а сегодня?", {"name": "Коломна"}, history, client=cli))
    assert "вчера говорили про дороги" in cli.last_call["user"]


# ---------------------------------------------------------------------------
# Sanity
# ---------------------------------------------------------------------------

def test_allowed_actions_set_is_nonempty():
    assert "open_scenario" in ALLOWED_ACTIONS
    assert "open_actions" in ALLOWED_ACTIONS
    assert len(ALLOWED_ACTIONS) >= 4
