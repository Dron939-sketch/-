"""Тесты helper'ов для подписок Max — на null pool path и helper'ы."""

import asyncio

from db import jarvis_max_queries as mq


def test_upsert_returns_none_without_identity():
    assert asyncio.run(mq.upsert_subscription("", "chat-1")) is None


def test_upsert_returns_none_without_chat_id():
    assert asyncio.run(mq.upsert_subscription("identity-xxx", "")) is None


def test_upsert_returns_none_without_pool():
    assert asyncio.run(mq.upsert_subscription("a" * 32, "chat-1")) is None


def test_get_returns_none_without_identity():
    assert asyncio.run(mq.get_by_identity("")) is None


def test_get_returns_none_without_pool():
    assert asyncio.run(mq.get_by_identity("a" * 32)) is None


def test_update_prefs_rejects_empty():
    assert asyncio.run(mq.update_prefs("a" * 32, {})) is False


def test_update_prefs_rejects_unknown_keys():
    # Без pool — всё равно должно вернуть False
    assert asyncio.run(mq.update_prefs("a" * 32, {"unknown_key": True})) is False


def test_delete_without_pool():
    assert asyncio.run(mq.delete_subscription("a" * 32)) is False


def test_list_chat_ids_unknown_pref():
    out = asyncio.run(mq.list_chat_ids_for_pref("invalid"))
    assert out == []


def test_list_chat_ids_known_pref_no_pool():
    out = asyncio.run(mq.list_chat_ids_for_pref("critical"))
    assert out == []


def test_default_prefs_shape():
    assert mq._DEFAULT_PREFS["critical"] is True
    assert mq._DEFAULT_PREFS["daily_brief"] is False
    assert mq._DEFAULT_PREFS["topics"] is False
