"""Тесты модуля долговременной памяти Джарвиса.

DB-helpers (db.jarvis_memory_queries) тестируем только на null-pool path
(гарантия fail-safe). Логику извлечения тем + сборки prompt-блока —
полноценно с моком БД.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from ai.jarvis_memory import (
    _shorten_question, build_memory_lines, detect_topics, record_user_turn,
)
from db import jarvis_memory_queries as mem


# ---------------------------------------------------------------------------
# detect_topics
# ---------------------------------------------------------------------------

def test_detect_topics_transport():
    out = detect_topics("Когда уже дороги починят?")
    assert "транспорт" in out


def test_detect_topics_zhkh():
    out = detect_topics("Опять воды нет в подъезде")
    assert "ЖКХ" in out


def test_detect_topics_multiple():
    out = detect_topics("В школе нет учителя по физкультуре")
    assert "образование" in out
    assert "спорт" in out
    # «культур» отдельно от «физкультур» — не должна сматчиться
    assert "культура" not in out


def test_detect_topics_no_match():
    assert detect_topics("просто привет") == []


def test_detect_topics_empty():
    assert detect_topics("") == []


# ---------------------------------------------------------------------------
# _shorten_question
# ---------------------------------------------------------------------------

def test_shorten_short_unchanged():
    assert _shorten_question("Как дела?") == "Как дела?"


def test_shorten_long_cuts_at_word_boundary():
    long = "когда уже починят " * 20
    out = _shorten_question(long, limit=120)
    assert len(out) <= 130
    assert out.endswith("…")


def test_shorten_strips_whitespace():
    assert _shorten_question("  привет  ") == "привет"


# ---------------------------------------------------------------------------
# Async-helpers с моками БД (без реального pool)
# ---------------------------------------------------------------------------

def test_record_user_turn_no_identity():
    # При пустом identity не должно быть никаких упсёртов
    with patch.object(mem, "upsert") as up:
        up.return_value = asyncio.sleep(0)  # async no-op
        asyncio.run(record_user_turn("", "что-нибудь"))
    assert up.call_count == 0


def test_record_user_turn_inserts_topics_and_recent_q():
    calls: List[Dict[str, Any]] = []

    async def fake_upsert(identity, kind, payload):
        calls.append({"identity": identity, "kind": kind, "payload": payload})

    with patch.object(mem, "upsert", side_effect=fake_upsert):
        asyncio.run(record_user_turn("user-1", "Когда дороги починят? И с водой что?"))
    kinds = [c["kind"] for c in calls]
    payloads = [c["payload"] for c in calls]
    assert "topic" in kinds
    assert "recent_q" in kinds
    assert "транспорт" in payloads
    assert "ЖКХ" in payloads


def test_build_memory_lines_empty_returns_empty():
    async def empty_topics(identity, **kw): return []
    async def empty_qs(identity, **kw): return []
    with patch.object(mem, "top_topics", side_effect=empty_topics), \
         patch.object(mem, "last_questions", side_effect=empty_qs):
        out = asyncio.run(build_memory_lines("user-1"))
    assert out == []


def test_build_memory_lines_renders_topics_and_questions():
    async def fake_top(identity, **kw):
        return [{"topic": "транспорт", "weight": 5}, {"topic": "ЖКХ", "weight": 3}]

    async def fake_qs(identity, **kw):
        return ["Когда дороги починят?", "Что с водой?"]

    with patch.object(mem, "top_topics", side_effect=fake_top), \
         patch.object(mem, "last_questions", side_effect=fake_qs):
        out = asyncio.run(build_memory_lines("user-1"))
    assert len(out) == 2
    assert "транспорт" in out[0]
    assert "ЖКХ" in out[0]
    assert "Когда дороги починят?" in out[1]
    assert "Что с водой?" in out[1]


def test_build_memory_lines_no_identity():
    out = asyncio.run(build_memory_lines(""))
    assert out == []


# ---------------------------------------------------------------------------
# Fail-safe queries — на отсутствующем pool возвращают пустой результат
# ---------------------------------------------------------------------------

def test_queries_failsafe_no_pool():
    """Все async helper'ы должны тихо вернуть [] / None при pool=None."""
    assert asyncio.run(mem.list_recent("user-1")) == []
    assert asyncio.run(mem.top_topics("user-1")) == []
    assert asyncio.run(mem.last_questions("user-1")) == []
    # upsert / forget_all возвращают None и не должны бросать
    asyncio.run(mem.upsert("user-1", "topic", "транспорт"))
    asyncio.run(mem.forget_all("user-1"))


def test_upsert_rejects_oversized_input():
    # Не должно бросать — просто игнорит
    asyncio.run(mem.upsert("u" * 81, "topic", "транспорт"))
    asyncio.run(mem.upsert("user-1", "topic", "x" * 300))
