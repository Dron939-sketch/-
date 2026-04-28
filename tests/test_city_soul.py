"""Тесты сборки промпта «Душа города»."""

from __future__ import annotations

import asyncio

import pytest

from ai.city_soul import answer, build_user_prompt
from ai.voice_service import normalize_for_tts


# ---------------------------------------------------------------------------
# build_user_prompt
# ---------------------------------------------------------------------------

def test_prompt_includes_city_name():
    p = build_user_prompt("Как дела?", {"name": "Коломна"})
    assert "Коломна" in p
    assert "Как дела?" in p


def test_prompt_includes_metrics_when_provided():
    p = build_user_prompt(
        "Что нового?",
        {
            "name": "Коломна",
            "metrics": {"sb": 4.2, "tf": 3.5, "ub": 4.0, "chv": 3.8},
        },
    )
    assert "4.2/6" in p
    assert "Социально-бытовой" in p
    assert "Человек-Власть" in p


def test_prompt_skips_none_metrics():
    p = build_user_prompt(
        "Привет",
        {"name": "Коломна", "metrics": {"sb": None, "ub": 4.0}},
    )
    assert "4.0/6" in p
    # для sb значения нет, "Социально-бытовой" не должен попасть в текст
    assert "sb" not in p
    # ub попадает, sb — нет
    assert "Уровень благополучия" in p


def test_prompt_includes_top_complaints_top3():
    p = build_user_prompt(
        "Хорошо ли в городе?",
        {
            "name": "Коломна",
            "top_complaints": ["a", "b", "c", "d"],
        },
    )
    assert "Топ жалоб" in p
    assert "- a" in p and "- b" in p and "- c" in p
    assert "- d" not in p  # обрезаем до 3


def test_prompt_unknown_city_uses_default():
    p = build_user_prompt("Как дела?", {})
    assert "Коломна" in p


def test_prompt_handles_weather():
    p = build_user_prompt(
        "Холодно?",
        {"name": "Коломна", "weather": {"temperature": -3.4, "condition": "снег"}},
    )
    assert "-3°C" in p
    assert "снег" in p


# ---------------------------------------------------------------------------
# answer() с замоканным DeepSeek-клиентом
# ---------------------------------------------------------------------------

class _FakeClient:
    def __init__(self, response):
        self.response = response
        self.last_call = None

    async def chat_json(self, system, user, **kw):
        self.last_call = {"system": system, "user": user, **kw}
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_answer_returns_reply_field():
    client = _FakeClient({"reply": "Я слышу тебя, друг."})
    out = asyncio.run(answer("Как ты?", {"name": "Коломна"}, client=client))
    assert out == "Я слышу тебя, друг."
    assert "Коломна" in client.last_call["user"]
    assert "Душа города" in client.last_call["system"]


def test_answer_falls_back_on_empty_question():
    out = asyncio.run(answer("", None))
    assert "слушаю" in out.lower() or "?" in out


def test_answer_falls_back_on_deepseek_error():
    from ai.deepseek_client import DeepSeekError
    client = _FakeClient(DeepSeekError("boom"))
    out = asyncio.run(answer("Эй?", {"name": "Луховицы"}, client=client))
    # Fallback должен включить имя города
    assert "Луховицы" in out


def test_answer_handles_missing_reply_key():
    client = _FakeClient({"text": "no reply field"})
    out = asyncio.run(answer("test", {}, client=client))
    assert out  # не пустая строка


def test_answer_strips_whitespace():
    client = _FakeClient({"reply": "  тёплый ответ  \n"})
    out = asyncio.run(answer("?", {}, client=client))
    assert out == "тёплый ответ"


# ---------------------------------------------------------------------------
# normalize_for_tts
# ---------------------------------------------------------------------------

def test_normalize_strips_emoji():
    assert "🌆" not in normalize_for_tts("Привет 🌆 как дела?")


def test_normalize_strips_markdown():
    out = normalize_for_tts("**Жирный** и *курсив* и `код`")
    assert "*" not in out and "`" not in out


def test_normalize_adds_terminal_punctuation():
    assert normalize_for_tts("Город спит").endswith(".")


def test_normalize_caps_at_4500():
    long = "а" * 6000
    out = normalize_for_tts(long)
    assert len(out) <= 4504  # 4500 + "..."


def test_normalize_empty_returns_fallback():
    out = normalize_for_tts("")
    assert out  # не пустое


def test_normalize_strips_remarks_in_parens():
    assert "(вздыхает)" not in normalize_for_tts("Привет (вздыхает) друг")
