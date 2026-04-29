"""Тесты analytics/vk_audit.py — pure-helpers + scenarios без сети."""

import asyncio
from unittest.mock import patch

from analytics.vk_audit import (
    _build_recommendations, _compute_metrics, _label_for_score,
    audit_deputy,
)


def _deputy(vk: str = "ivanov", **overrides):
    base = {
        "id": 42, "name": "Иванов И.И.",
        "district": "Округ №3", "sectors": ["ЖКХ", "благоустройство"],
        "role": "district_rep", "vk": vk,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------

def test_label_for_score_steps():
    assert _label_for_score(80) == "В голосе"
    assert _label_for_score(50) == "Частично совпадает"
    assert _label_for_score(20) == "Размытый стиль"
    assert _label_for_score(5) == "Стиль не виден"


def test_compute_metrics_empty():
    assert _compute_metrics([]) == {}


def test_compute_metrics_single_post():
    posts = [{
        "text": "Привет",
        "published_at": "2026-04-29T10:00:00+00:00",
        "likes": 5, "reposts": 1, "views": 100,
    }]
    m = _compute_metrics(posts)
    assert m["posts_count"] == 1
    assert m["avg_likes"] == 5
    assert m["avg_views"] == 100


def test_compute_metrics_per_week():
    posts = [
        {
            "text": "p" * 50, "published_at": "2026-04-01T10:00:00+00:00",
            "likes": 1, "views": 10,
        },
        {
            "text": "p" * 50, "published_at": "2026-04-08T10:00:00+00:00",
            "likes": 1, "views": 10,
        },
        {
            "text": "p" * 50, "published_at": "2026-04-15T10:00:00+00:00",
            "likes": 1, "views": 10,
        },
    ]
    m = _compute_metrics(posts)
    # 14 дней между постами, 3 поста → ~1.5 поста/неделю
    assert m["span_days"] == 14
    assert m["posts_per_week"] == 1.5


def test_build_recommendations_low_frequency():
    metrics = {"posts_per_week": 0.5, "avg_length": 200}
    archetype = {"code": "caregiver", "name": "Заботливый",
                 "do": ["Помогай"], "sample_post": "x"}
    recs = _build_recommendations(metrics, alignment=80, archetype=archetype)
    assert any("неделю" in r for r in recs)


def test_build_recommendations_short_posts():
    metrics = {"posts_per_week": 5, "avg_length": 50}
    archetype = {"code": "caregiver", "name": "Заботливый",
                 "do": ["Помогай"], "sample_post": "x"}
    recs = _build_recommendations(metrics, alignment=80, archetype=archetype)
    assert any("коротк" in r.lower() for r in recs)


def test_build_recommendations_long_posts():
    metrics = {"posts_per_week": 5, "avg_length": 2000}
    archetype = {"code": "caregiver", "name": "Заботливый",
                 "do": ["Помогай"], "sample_post": "x"}
    recs = _build_recommendations(metrics, alignment=80, archetype=archetype)
    assert any("длинн" in r.lower() or "режь" in r.lower() for r in recs)


def test_build_recommendations_low_alignment():
    metrics = {"posts_per_week": 3, "avg_length": 300}
    archetype = {"code": "ruler", "name": "Правитель",
                 "do": ["Декларируй"], "sample_post": "x"}
    recs = _build_recommendations(metrics, alignment=20, archetype=archetype)
    assert any("Правитель" in r for r in recs)


def test_build_recommendations_good_state():
    metrics = {"posts_per_week": 3, "avg_length": 300}
    archetype = {"code": "caregiver", "name": "Заботливый",
                 "do": ["Помогай"], "sample_post": "В этом духе и продолжай."}
    recs = _build_recommendations(metrics, alignment=80, archetype=archetype)
    assert recs  # хоть одна
    assert any("в голосе" in r.lower() or "Заботливый" in r for r in recs)


# ---------------------------------------------------------------------------
# audit_deputy — scenarios with mocked _fetch_recent_posts
# ---------------------------------------------------------------------------

def test_audit_no_vk_handle():
    out = asyncio.run(audit_deputy(_deputy(vk="")))
    assert out["state"] == "no_vk_handle"
    assert out["alignment_score"] is None
    assert out["recommendations"]


def test_audit_no_posts(monkeypatch):
    async def empty(*a, **kw): return []
    with patch("analytics.vk_audit._fetch_recent_posts", empty):
        out = asyncio.run(audit_deputy(_deputy()))
    assert out["state"] == "no_posts"
    assert out["alignment_score"] is None


def test_audit_with_posts(monkeypatch):
    posts = [
        {
            "text": "Сегодня помог бабушке Марии — будем поддерживать вместе.",
            "published_at": "2026-04-01T10:00:00+00:00",
            "likes": 5, "reposts": 1, "views": 100,
        },
        {
            "text": "Проект освещения двора 7 — вместе с жителями выбираем фонари.",
            "published_at": "2026-04-08T10:00:00+00:00",
            "likes": 7, "reposts": 2, "views": 150,
        },
    ]
    async def fetch(*a, **kw): return posts
    with patch("analytics.vk_audit._fetch_recent_posts", fetch):
        out = asyncio.run(audit_deputy(_deputy()))
    assert out["state"] == "ok"
    assert out["posts_fetched"] == 2
    assert out["alignment_score"] is not None
    assert out["alignment_label"] in (
        "В голосе", "Частично совпадает", "Размытый стиль", "Стиль не виден",
    )
    assert out["recommendations"]


def test_audit_includes_archetype_info():
    async def fetch(*a, **kw): return []
    with patch("analytics.vk_audit._fetch_recent_posts", fetch):
        out = asyncio.run(audit_deputy(_deputy()))
    assert out["archetype_code"]
    assert out["archetype_name"]
    assert out["archetype_voice"]
    assert isinstance(out["archetype_do"], list)
    assert isinstance(out["archetype_dont"], list)
