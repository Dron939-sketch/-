"""Unit tests for AIPulseCollector."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest

from collectors.ai_pulse import AIPulseCollector
from collectors.base import CollectedItem


class _FakeClient:
    """Stand-in for DeepSeekClient that returns a canned JSON payload."""

    def __init__(self, response: Optional[Dict[str, Any]] = None, enabled: bool = True,
                 raise_error: bool = False, model: str = "deepseek-chat"):
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


def _ref_item(title: str, category: str = "news", sentiment: Optional[float] = None) -> CollectedItem:
    return CollectedItem(
        source_kind="news_rss",
        source_handle="test",
        title=title,
        content=title,
        published_at=datetime.now(tz=timezone.utc),
        category=category,
        enrichment={"sentiment": sentiment, "category": category} if sentiment is not None else None,
    )


@pytest.mark.asyncio
async def test_returns_empty_when_client_disabled():
    client = _FakeClient(enabled=False)
    coll = AIPulseCollector("Коломна", reference_items=[_ref_item("x")], client=client)
    assert await coll.collect() == []
    assert client.calls == []  # no network call attempted


@pytest.mark.asyncio
async def test_returns_empty_when_no_reference_items():
    client = _FakeClient(response={"posts": [{"title": "X", "content": "X"}]})
    coll = AIPulseCollector("Коломна", reference_items=[], client=client)
    assert await coll.collect() == []
    assert client.calls == []


@pytest.mark.asyncio
async def test_returns_empty_on_deepseek_error():
    client = _FakeClient(raise_error=True)
    coll = AIPulseCollector("Коломна", reference_items=[_ref_item("x")], client=client)
    assert await coll.collect() == []
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_builds_items_with_ai_pulse_source_kind():
    response = {
        "posts": [
            {"title": "Снова нет горячей воды",
             "content": "Второй день без горячей, СК молчит.",
             "sentiment": -0.8, "category": "utilities", "severity": 0.4},
            {"title": "Отличный концерт вчера!",
             "content": "Послушали джаз на набережной, приятный вечер.",
             "sentiment": 0.7, "category": "culture", "severity": 0.0},
        ]
    }
    client = _FakeClient(response=response)
    coll = AIPulseCollector(
        "Коломна",
        reference_items=[_ref_item("Отключили воду", "utilities", -0.5)],
        client=client,
    )
    items = await coll.collect()

    assert len(items) == 2
    for it in items:
        assert it.source_kind == "ai_pulse"
        assert it.source_handle == "ai_pulse:Коломна"
        assert it.author == "AI-синтез"
        assert it.enrichment["ai_synth"] is True
        assert it.raw["ai_synth"] is True

    assert items[0].title.startswith("Снова")
    assert items[0].category == "utilities"
    assert items[0].enrichment["sentiment"] == pytest.approx(-0.8)
    assert items[1].category == "culture"


@pytest.mark.asyncio
async def test_unknown_category_falls_back_to_other():
    response = {"posts": [{"title": "x", "content": "x", "category": "made_up"}]}
    client = _FakeClient(response=response)
    coll = AIPulseCollector("Коломна", reference_items=[_ref_item("x")], client=client)
    items = await coll.collect()
    assert len(items) == 1
    assert items[0].category == "other"


@pytest.mark.asyncio
async def test_caps_posts_at_requested_count():
    response = {"posts": [{"title": str(i), "content": str(i)} for i in range(10)]}
    client = _FakeClient(response=response)
    coll = AIPulseCollector(
        "Коломна", reference_items=[_ref_item("x")], client=client, posts=3,
    )
    items = await coll.collect()
    assert len(items) == 3


@pytest.mark.asyncio
async def test_skips_malformed_post_entries():
    response = {"posts": [
        {"title": "good", "content": "good"},
        "just a string",             # must be skipped
        None,                         # must be skipped
        {"title": "", "content": ""}, # empty — skipped
        {"title": "also good", "content": "yes"},
    ]}
    client = _FakeClient(response=response)
    coll = AIPulseCollector("Коломна", reference_items=[_ref_item("x")], client=client)
    items = await coll.collect()
    titles = [it.title for it in items]
    assert titles == ["good", "also good"]


@pytest.mark.asyncio
async def test_reference_context_included_in_prompt():
    client = _FakeClient(response={"posts": []})
    coll = AIPulseCollector(
        "Коломна",
        reference_items=[
            _ref_item("Отключили воду на Фрунзе", "utilities", -0.6),
            _ref_item("Открыли парк", "culture", 0.7),
        ],
        client=client,
    )
    await coll.collect()
    assert len(client.calls) == 1
    _system, user_prompt = client.calls[0]
    assert "Отключили воду" in user_prompt
    assert "Открыли парк" in user_prompt
    assert "Коломна" in user_prompt


@pytest.mark.asyncio
async def test_sentiment_clamped_to_minus_one_plus_one():
    response = {"posts": [
        {"title": "a", "content": "a", "sentiment": -10.0},
        {"title": "b", "content": "b", "sentiment": 5.0},
    ]}
    client = _FakeClient(response=response)
    coll = AIPulseCollector("Коломна", reference_items=[_ref_item("x")], client=client)
    items = await coll.collect()
    assert items[0].enrichment["sentiment"] == pytest.approx(-1.0)
    assert items[1].enrichment["sentiment"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_items_have_unique_ids_via_staggered_timestamps():
    response = {"posts": [
        {"title": "same", "content": "same text"} for _ in range(3)
    ]}
    client = _FakeClient(response=response)
    coll = AIPulseCollector("Коломна", reference_items=[_ref_item("x")], client=client)
    items = await coll.collect()
    # published_at should be strictly decreasing so ids (hash of source+url) aren't
    # all identical even with identical content.
    timestamps = [it.published_at for it in items]
    assert timestamps[0] > timestamps[1] > timestamps[2]
