"""Tests for NewsEnricher.

All network calls are mocked so the test runs offline. We cover three
paths: enabled + happy-path response, DeepSeek disabled (stub mode), and
DeepSeek error (items pass through unchanged).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from ai.deepseek_client import DeepSeekError
from ai.enricher import NewsEnricher
from collectors.base import CollectedItem


class _FakeClient:
    def __init__(self, response: Dict[str, Any] | None, *, enabled: bool = True,
                 raises: Exception | None = None):
        self._response = response
        self._enabled = enabled
        self._raises = raises
        self.calls = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def chat_json(self, system: str, user: str, **kwargs):
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._response


def _item(title: str, category: str = "news") -> CollectedItem:
    return CollectedItem(
        source_kind="telegram",
        source_handle="kolomna_chp",
        title=title,
        content=title,
        published_at=datetime(2026, 4, 22, 8, 0, tzinfo=timezone.utc),
        category=category,
    )


def test_enrich_applies_llm_response():
    items = [_item("Авария на теплотрассе"), _item("День города")]
    response = {
        "items": [
            {
                "id": items[0].id,
                "sentiment": -0.8,
                "category": "utilities",
                "severity": 0.9,
                "summary": "Обрыв теплотрассы, 5 домов без отопления",
            },
            {
                "id": items[1].id,
                "sentiment": 0.6,
                "category": "culture",
                "severity": 0.2,
                "summary": "Празднование Дня города на набережной",
            },
        ]
    }
    fake = _FakeClient(response)
    enricher = NewsEnricher(client=fake, batch_size=10, max_items=10)
    result = asyncio.run(enricher.enrich(items))
    assert fake.calls == 1
    assert result[0].enrichment["sentiment"] == pytest.approx(-0.8)
    assert result[0].enrichment["category"] == "utilities"
    assert result[0].enrichment["severity"] == pytest.approx(0.9)
    assert "теплотрассы" in result[0].enrichment["summary"]
    assert result[1].enrichment["category"] == "culture"


def test_disabled_client_is_a_noop():
    items = [_item("Авария")]
    fake = _FakeClient(None, enabled=False)
    enricher = NewsEnricher(client=fake)
    out = asyncio.run(enricher.enrich(items))
    assert fake.calls == 0
    assert out[0].enrichment is None


def test_deepseek_error_leaves_items_unchanged():
    items = [_item("Авария")]
    fake = _FakeClient(None, raises=DeepSeekError("boom"))
    enricher = NewsEnricher(client=fake, batch_size=10, max_items=10)
    out = asyncio.run(enricher.enrich(items))
    assert fake.calls == 1
    assert out[0].enrichment is None


def test_invalid_category_normalises_to_other():
    items = [_item("Странное")]
    response = {
        "items": [
            {
                "id": items[0].id,
                "sentiment": 0.0,
                "category": "КРИПТОВАЛЮТА",
                "severity": 0.1,
                "summary": "тест",
            }
        ]
    }
    fake = _FakeClient(response)
    enricher = NewsEnricher(client=fake, batch_size=10, max_items=10)
    out = asyncio.run(enricher.enrich(items))
    assert out[0].enrichment["category"] == "other"


def test_sentiment_clamped():
    items = [_item("Что-то")]
    response = {
        "items": [
            {
                "id": items[0].id,
                "sentiment": -9.9,
                "category": "news",
                "severity": 5.0,
                "summary": "x",
            }
        ]
    }
    fake = _FakeClient(response)
    enricher = NewsEnricher(client=fake, batch_size=10, max_items=10)
    out = asyncio.run(enricher.enrich(items))
    assert out[0].enrichment["sentiment"] == -1.0
    assert out[0].enrichment["severity"] == 1.0


def test_already_enriched_items_skipped():
    items = [_item("A"), _item("B")]
    items[0].enrichment = {"sentiment": 0.0, "category": "news", "severity": 0.1, "summary": "pre"}
    response = {
        "items": [
            {
                "id": items[1].id,
                "sentiment": 0.5,
                "category": "culture",
                "severity": 0.3,
                "summary": "new",
            }
        ]
    }
    fake = _FakeClient(response)
    enricher = NewsEnricher(client=fake, batch_size=10, max_items=10)
    out = asyncio.run(enricher.enrich(items))
    # First was pre-enriched: untouched
    assert out[0].enrichment["summary"] == "pre"
    # Second was freshly enriched
    assert out[1].enrichment["summary"] == "new"
