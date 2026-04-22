"""Tests for the daily-agenda builder."""

from __future__ import annotations

from datetime import datetime, timezone

from agenda.daily_agenda import DailyAgendaBuilder
from collectors.base import CollectedItem


def _item(title: str, category: str, offset_s: int = 0) -> CollectedItem:
    return CollectedItem(
        source_kind="telegram",
        source_handle="kolomna_chp",
        title=title,
        content=title,
        published_at=datetime(2026, 4, 22, 8, 0, tzinfo=timezone.utc),
        category=category,
    )


def test_builder_picks_complaint_as_headline():
    builder = DailyAgendaBuilder("Коломна")
    news = [
        _item("Отсутствие тепла в Колычёво", "utilities"),
        _item("Концерт в кремле", "culture"),
    ]
    agenda = builder.build(
        date=datetime(2026, 4, 22, 9, 0, tzinfo=timezone.utc),
        city_metrics={"СБ": 4, "ТФ": 3, "УБ": 4, "ЧВ": 5},
        trust={"index": 0.5, "top_complaints": ["дороги"], "top_praises": []},
        happiness={"overall": 0.6},
        weather={"temperature": 7.0, "condition": "Ясно", "condition_emoji": "☀️"},
        news=news,
    )
    assert "Колычёво" in agenda.headline
    assert agenda.vectors == {"СБ": 4.0, "ТФ": 3.0, "УБ": 4.0, "ЧВ": 5.0}
    md = agenda.to_markdown()
    assert "Коломна" in md
    assert "Рекомендованные действия" in md
    assert "Индекс счастья" in md


def test_builder_fallback_when_no_negative_news():
    builder = DailyAgendaBuilder("Коломна")
    agenda = builder.build(
        date=datetime(2026, 4, 22, 9, 0, tzinfo=timezone.utc),
        city_metrics={},
        trust={"top_complaints": [], "top_praises": []},
        happiness={},
        weather={},
        news=[],
    )
    assert agenda.headline
    assert agenda.actions  # always at least one generic action
