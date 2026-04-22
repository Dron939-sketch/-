"""Unit tests for collector base plumbing.

The production transports (Telethon, VK API, RSS) are exercised in
integration tests with recorded fixtures — unit tests stay offline.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import pytest

from collectors import AppealsCollector, TelegramCollector, VKCollector
from collectors.base import CollectedItem


def test_collected_item_id_is_deterministic():
    a = CollectedItem(
        source_kind="telegram",
        source_handle="kolomna_live",
        title="t",
        content="c",
        published_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        url="https://t.me/kolomna_live/1",
    )
    b = CollectedItem(
        source_kind="telegram",
        source_handle="kolomna_live",
        title="t",
        content="c",
        published_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        url="https://t.me/kolomna_live/1",
    )
    assert a.id == b.id
    # Same source but different URL → different id
    c = CollectedItem(
        source_kind="telegram",
        source_handle="kolomna_live",
        title="t",
        content="c",
        published_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
        url="https://t.me/kolomna_live/2",
    )
    assert a.id != c.id


def test_telegram_collector_stub_mode_returns_empty(monkeypatch):
    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)
    collector = TelegramCollector("Коломна")
    items = asyncio.run(collector.collect())
    assert items == []


def test_vk_collector_returns_empty_without_token():
    # Settings are frozen and loaded once from env. In the test environment
    # VK_API_TOKEN is not set, so the collector must short-circuit to [].
    from config.settings import settings
    assert settings.vk_api_token == "", "expected no VK token in test env"
    collector = VKCollector("Коломна")
    items = asyncio.run(collector.collect())
    assert items == []


def test_appeals_collector_reads_fixture(tmp_path):
    fixture = tmp_path / "appeals.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "handle": "kolomna",
                    "title": "Ямы на Октябрьской",
                    "content": "Большие ямы, невозможно ездить",
                    "category": "complaints",
                    "published_at": "2026-04-22T08:00:00+00:00",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    collector = AppealsCollector("Коломна", fixture_path=str(fixture))
    items = asyncio.run(collector.collect())
    assert len(items) == 1
    assert items[0].title == "Ямы на Октябрьской"
    assert items[0].source_kind == "gosuslugi"
