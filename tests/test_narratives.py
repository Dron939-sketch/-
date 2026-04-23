"""Unit tests for the narrative generator."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from ai.narratives import generate


class _FakeClient:
    def __init__(self, response: Optional[Dict[str, Any]] = None,
                 enabled: bool = True, raise_error: bool = False,
                 model: str = "deepseek-chat"):
        self.response = response or {}
        self._enabled = enabled
        self.raise_error = raise_error
        self.model = model
        self.calls: List[tuple] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def chat_json(self, system: str, user: str, **_) -> Dict[str, Any]:
        self.calls.append((system, user))
        if self.raise_error:
            from ai.deepseek_client import DeepSeekError
            raise DeepSeekError("boom")
        return self.response


@pytest.mark.asyncio
async def test_returns_error_when_topic_missing():
    out = await generate("Коломна", topic="", client=_FakeClient())
    d = out.to_dict()
    assert d["error"] and "тема" in d["error"].lower()
    assert d["variants"] == []


@pytest.mark.asyncio
async def test_returns_error_when_client_disabled():
    out = await generate("Коломна", "Проблема с ЖКХ",
                         client=_FakeClient(enabled=False))
    d = out.to_dict()
    assert d["error"] and "deepseek" in d["error"].lower()
    assert d["variants"] == []


@pytest.mark.asyncio
async def test_returns_error_on_deepseek_failure():
    out = await generate("Коломна", "Проблема",
                         client=_FakeClient(raise_error=True))
    d = out.to_dict()
    assert d["error"] and "deepseek" in d["error"].lower()


@pytest.mark.asyncio
async def test_happy_path_returns_three_variants_in_fixed_order():
    response = {"variants": [
        {"tone": "mobilizing", "text": "Делаем шаги прямо сейчас."},
        {"tone": "formal",     "text": "Администрация приняла меры."},
        {"tone": "empathetic", "text": "Мы слышим вас и работаем."},
    ]}
    out = await generate("Коломна", "Горячая вода",
                         context="Отключения на Фрунзе",
                         client=_FakeClient(response=response))
    d = out.to_dict()
    assert d["error"] is None
    assert [v["tone"] for v in d["variants"]] == ["formal", "empathetic", "mobilizing"]
    texts = {v["tone"]: v["text"] for v in d["variants"]}
    assert texts["formal"].startswith("Администрация")
    assert texts["empathetic"].startswith("Мы слышим")
    assert texts["mobilizing"].startswith("Делаем")


@pytest.mark.asyncio
async def test_missing_tone_fills_with_empty_text():
    response = {"variants": [
        {"tone": "formal", "text": "Только официальный."},
    ]}
    out = await generate("Коломна", "X", client=_FakeClient(response=response))
    d = out.to_dict()
    by_tone = {v["tone"]: v for v in d["variants"]}
    assert by_tone["formal"]["text"] == "Только официальный."
    assert by_tone["empathetic"]["text"] == ""
    assert by_tone["mobilizing"]["text"] == ""
    assert d["error"] is None  # at least one filled → no error


@pytest.mark.asyncio
async def test_empty_response_sets_error():
    out = await generate("Коломна", "X", client=_FakeClient(response={}))
    d = out.to_dict()
    # All 3 variants present but empty text.
    assert len(d["variants"]) == 3
    assert all(v["text"] == "" for v in d["variants"])
    assert d["error"]


@pytest.mark.asyncio
async def test_malformed_response_does_not_crash():
    out = await generate("Коломна", "X",
                         client=_FakeClient(response={"variants": "not a list"}))
    d = out.to_dict()
    assert len(d["variants"]) == 3
    assert all(v["text"] == "" for v in d["variants"])


@pytest.mark.asyncio
async def test_length_chars_matches_text_length():
    response = {"variants": [
        {"tone": "formal", "text": "ABCDE"},
        {"tone": "empathetic", "text": ""},
        {"tone": "mobilizing", "text": "X" * 200},
    ]}
    out = await generate("Коломна", "X",
                         client=_FakeClient(response=response))
    by_tone = {v["tone"]: v for v in out.to_dict()["variants"]}
    assert by_tone["formal"]["length_chars"] == 5
    assert by_tone["empathetic"]["length_chars"] == 0
    assert by_tone["mobilizing"]["length_chars"] == 200


@pytest.mark.asyncio
async def test_prompt_contains_city_topic_context():
    client = _FakeClient(response={"variants": []})
    await generate("Коломна", "Отключения воды",
                   context="Фрунзе, 3 дома, с утра",
                   client=client)
    assert len(client.calls) == 1
    _system, user = client.calls[0]
    assert "Коломна" in user
    assert "Отключения воды" in user
    assert "Фрунзе" in user
