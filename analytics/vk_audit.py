"""Аудит VK-страницы депутата — fetch + analyze + suggestions.

Загружает посты со стены через collectors.vk_collector (если у депутата
указан VK handle), считает простые метрики (частота, длина, темы) и
сопоставляет фактический стиль с рекомендованным архетипом из
config.archetypes.

Pure-async, fail-safe. Если у депутата нет vk handle — возвращает
честный отчёт «нет данных, привяжите страницу».
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from statistics import mean, median
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


_WORD_RE = re.compile(r"[а-яёА-ЯЁa-zA-Z]{3,}", re.UNICODE)
_TARGET_POSTS_PER_WEEK = 3
_WALL_LOOKBACK_DAYS = 60


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def audit_vk_page(
    vk_handle: str, *,
    name: Optional[str] = None,
    sectors: Optional[List[str]] = None,
    archetype_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Аудит произвольной VK-страницы для рядового пользователя.

    Это thin-wrapper над audit_deputy: строит pseudo-deputy dict с
    минимальным набором полей. Если archetype_code передан — он
    используется напрямую (пользователь сам выбрал свой архетип),
    иначе подбираем по sectors через suggest_for_deputy.
    """
    pseudo = {
        "name":     name or "Страница",
        "id":       0,
        "vk":       vk_handle,
        "sectors":  list(sectors or ["общая_повестка"]),
        "role":     "district_rep",
        "district": "",
    }
    out = await audit_deputy(pseudo)
    # Перезатереть архетип если пользователь явно выбрал
    if archetype_code:
        from config.archetypes import get as get_arch
        a = get_arch(archetype_code)
        if a:
            out["archetype_code"]  = a.get("code")
            out["archetype_name"]  = a.get("name")
            out["archetype_voice"] = a.get("voice")
            out["archetype_do"]    = a.get("do") or []
            out["archetype_dont"]  = a.get("dont") or []
    return out


async def plan_vk_page(
    vk_handle: str, *,
    name: Optional[str] = None,
    sectors: Optional[List[str]] = None,
    archetype_code: Optional[str] = None,
) -> Dict[str, Any]:
    """Контент-план на неделю для произвольного пользователя.

    Thin-wrapper над analytics.deputy_content.recommend_weekly_plan: строит
    pseudo-deputy и резолвит archetype_code в архетип-словарь, чтобы
    переопределить автоподбор по секторам.
    """
    from analytics.deputy_content import recommend_weekly_plan
    from config.archetypes import get as get_arch

    pseudo = {
        "name":     name or "Страница",
        "id":       0,
        "vk":       vk_handle,
        "sectors":  list(sectors or ["общая_повестка"]),
        "role":     "district_rep",
        "district": "",
    }
    override = get_arch(archetype_code) if archetype_code else None
    return await recommend_weekly_plan(pseudo, archetype_override=override)


async def audit_deputy(deputy: Dict[str, Any]) -> Dict[str, Any]:
    """Главная точка. Принимает dict депутата (как из db.list_deputies),
    возвращает словарь с метриками и рекомендациями."""
    from config.archetypes import (
        archetype_match_score, suggest_for_deputy,
    )

    handle = (deputy.get("vk") or "").strip()
    archetype = suggest_for_deputy(deputy)

    base: Dict[str, Any] = {
        "deputy_name":       deputy.get("name"),
        "deputy_id":         deputy.get("id"),
        "vk_handle":         handle or None,
        "vk_url":            f"https://vk.com/{handle}" if handle else None,
        "archetype_code":    archetype.get("code"),
        "archetype_name":    archetype.get("name"),
        "archetype_voice":   archetype.get("voice"),
        "archetype_do":      archetype.get("do") or [],
        "archetype_dont":    archetype.get("dont") or [],
    }

    if not handle:
        base["state"] = "no_vk_handle"
        base["recommendations"] = [
            "Привязать VK-страницу в карточке депутата.",
            "Заполнить статус и краткое био.",
            "Запостить 1-2 поста о работе в округе для старта.",
        ]
        base["alignment_score"] = None
        return base

    # Загружаем посты — best-effort
    posts = await _fetch_recent_posts(handle, days=_WALL_LOOKBACK_DAYS)
    base["posts_fetched"] = len(posts)

    if not posts:
        base["state"] = "no_posts"
        base["recommendations"] = [
            "Стена пустая или закрытая — проверь приватность страницы.",
            f"Архетип «{archetype['name']}»: {archetype['short']}",
            f"Старт: «{archetype.get('sample_post')}»",
        ]
        base["alignment_score"] = None
        return base

    # Метрики
    metrics = _compute_metrics(posts)
    base["metrics"] = metrics

    # Соответствие стилю архетипа
    align_scores = [archetype_match_score(p["text"], archetype) for p in posts]
    avg_align = round(mean(align_scores) * 100, 1) if align_scores else 0.0
    base["alignment_score"] = avg_align
    base["alignment_label"] = _label_for_score(avg_align)

    # Что работает / что мешает
    base["what_works"], base["what_hurts"] = _split_quotes(posts, archetype)

    # Рекомендации
    base["recommendations"] = _build_recommendations(metrics, avg_align, archetype)
    # Сырые посты — для downstream-анализа (timing heatmap и т.п.).
    # Поля только нужные, чтобы JSON не разбухал.
    base["_raw_posts"] = [
        {"published_at": p.get("published_at"),
         "likes":        p.get("likes", 0),
         "views":        p.get("views", 0)}
        for p in posts
    ]
    base["state"] = "ok"
    return base


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

async def _fetch_recent_posts(
    handle: str, *, days: int = 60,
) -> List[Dict[str, Any]]:
    """Через collectors.vk_collector берём wall.get для одного handle.
    Возвращает список dict {text, published_at, likes, reposts, views}."""
    try:
        import aiohttp
        from config.settings import settings
    except Exception:  # noqa: BLE001
        return []

    token = settings.vk_api_token
    if not token:
        return []

    is_numeric = handle.lstrip("-").isdigit()
    params: Dict[str, Any] = {
        "count": 50,
        "access_token": token,
        "v": "5.199",
    }
    if is_numeric:
        params["owner_id"] = handle
    else:
        params["domain"] = handle

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.vk.com/method/wall.get",
                params=params, timeout=15,
            ) as resp:
                data = await resp.json()
    except Exception:  # noqa: BLE001
        logger.debug("VK wall.get failed for %s", handle, exc_info=False)
        return []

    if "error" in data:
        return []
    items = data.get("response", {}).get("items", []) or []
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days)).timestamp()
    out: List[Dict[str, Any]] = []
    for p in items:
        ts = int(p.get("date", 0))
        if ts < cutoff:
            continue
        text = (p.get("text") or "").strip()
        if not text:
            continue
        out.append({
            "text": text,
            "published_at": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
            "likes":   (p.get("likes") or {}).get("count") or 0,
            "reposts": (p.get("reposts") or {}).get("count") or 0,
            "views":   (p.get("views") or {}).get("count") or 0,
        })
    return out


def _compute_metrics(posts: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not posts:
        return {}
    lengths = [len(p["text"]) for p in posts]
    likes = [int(p.get("likes") or 0) for p in posts]
    views = [int(p.get("views") or 0) for p in posts]
    # Период посчитаем по самой ранней дате
    times = sorted(p.get("published_at") or "" for p in posts)
    first = times[0] if times else None
    last = times[-1] if times else None
    span_days = 0
    if first and last and first != last:
        try:
            span_days = (
                datetime.fromisoformat(last.replace("Z", "+00:00"))
                - datetime.fromisoformat(first.replace("Z", "+00:00"))
            ).days
        except Exception:  # noqa: BLE001
            pass
    posts_per_week = (
        round(len(posts) * 7 / span_days, 1)
        if span_days >= 7 else float(len(posts))
    )
    return {
        "posts_count":    len(posts),
        "span_days":      span_days,
        "posts_per_week": posts_per_week,
        "avg_length":     round(mean(lengths), 0),
        "median_length":  round(median(lengths), 0),
        "avg_likes":      round(mean(likes), 1),
        "avg_views":      round(mean(views), 1),
        "first_post":     first,
        "last_post":      last,
    }


def _label_for_score(score: float) -> str:
    if score >= 70:
        return "В голосе"
    if score >= 40:
        return "Частично совпадает"
    if score >= 15:
        return "Размытый стиль"
    return "Стиль не виден"


def _split_quotes(posts, archetype) -> tuple:
    """Делит на «что работает» (≥0.5 alignment) и «что мешает» (<0.2).
    Возвращает 2 списка по 3 цитаты максимум."""
    from config.archetypes import archetype_match_score

    works: List[str] = []
    hurts: List[str] = []
    for p in posts:
        s = archetype_match_score(p["text"], archetype)
        snippet = (p["text"][:200]).replace("\n", " ").strip()
        if s >= 0.5 and len(works) < 3:
            works.append(snippet)
        elif s < 0.2 and len(hurts) < 3:
            hurts.append(snippet)
    return works, hurts


def _build_recommendations(
    metrics: Dict[str, Any], alignment: float, archetype: Dict[str, Any],
) -> List[str]:
    recs: List[str] = []
    pp_week = metrics.get("posts_per_week") or 0
    if pp_week < 1:
        recs.append(
            f"Сейчас постов меньше одного в неделю — поднимай до "
            f"{_TARGET_POSTS_PER_WEEK}/неделю, иначе аудитория уходит."
        )
    elif pp_week < _TARGET_POSTS_PER_WEEK:
        recs.append(
            f"Регулярность {pp_week} постов/неделю — целься в "
            f"{_TARGET_POSTS_PER_WEEK}, давай аудитории ритм ожидания."
        )
    avg_len = metrics.get("avg_length") or 0
    if avg_len < 80:
        recs.append(
            "Посты слишком короткие. Делай содержательнее — 2-3 абзаца, "
            "конкретные цифры, факты, источники."
        )
    elif avg_len > 1500:
        recs.append(
            "Слишком длинные тексты — режь на 2-3 поста с разными темами, "
            "люди читают мобильные дозами."
        )
    if alignment < 40:
        recs.append(
            f"Голос «{archetype['name']}» пока слабо звучит. Возьми один из "
            f"do-приёмов: {archetype.get('do', [''])[0]}"
        )
    if not recs:
        recs.append(
            f"Стиль в голосе «{archetype['name']}» — продолжай в этом духе. "
            f"Образец поста: «{archetype.get('sample_post', '')[:120]}…»"
        )
    return recs[:5]
