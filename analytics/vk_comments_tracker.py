"""Реактивный трекер комментариев под постами депутата.

Логика:
1. Берём её последние посты через wall.get
2. Для каждого поста с >0 комментариев — wall.getComments
3. Грубо классифицируем тон по словарю (как voice_portrait)
4. Фильтруем уже отвеченные через deputy_comments_seen
5. Сортируем: critical / unanswered first, потом по возрасту

На выход — очередь из топ-N комментариев требующих внимания.
Каждый имеет: id, post_id, author_id, time, text, tone, age_hours.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# Словарь для грубой тональности
_NEGATIVE_KW = {
    "не работает", "плохо", "ужасно", "обман", "не сделали", "ничего не",
    "проблема", "сорван", "стыдно", "позор", "никто не", "обещали",
    "разорв", "сломан", "разбит", "пожар", "взлом", "беда",
}
_POSITIVE_KW = {
    "спасибо", "благодар", "молодц", "помог", "решен", "сделал",
    "красав", "победа", "поддержив", "согласен", "правильн",
}
_QUESTION_KW = {
    "?", "когда", "как", "почему", "зачем", "что",
}


async def build_comments_queue(
    deputy: Dict[str, Any], *,
    posts_limit: int = 8,
    seen_ids: Optional[Set[str]] = None,
    queue_limit: int = 8,
) -> Dict[str, Any]:
    """Возвращает {queue: [...], state, summary}."""
    handle = (deputy.get("vk") or "").strip()
    if not handle:
        return {"queue": [], "state": "no_vk_handle", "summary": ""}

    try:
        import aiohttp
        from config.settings import settings
    except Exception:  # noqa: BLE001
        return {"queue": [], "state": "no_settings", "summary": ""}

    if getattr(settings, "demo_mode", False):
        return {"queue": [], "state": "demo_mode", "summary": ""}

    token = settings.vk_api_token
    if not token:
        return {"queue": [], "state": "no_token", "summary": ""}

    seen = seen_ids or set()
    posts = await _fetch_recent_posts(handle, token, posts_limit)
    if not posts:
        return {"queue": [], "state": "no_posts", "summary": ""}

    # Параллельно тянем комменты по всем постам
    queue_items: List[Dict[str, Any]] = []
    for p in posts:
        if int(p.get("comments", {}).get("count") or 0) == 0:
            continue
        comments = await _fetch_comments(handle_to_owner(handle), p.get("id"), token)
        for c in comments:
            cid = f"{p.get('id')}_{c.get('id')}"
            if cid in seen:
                continue
            text = (c.get("text") or "").strip()
            if not text:
                continue
            tone = _classify_tone(text)
            ts = int(c.get("date") or 0)
            try:
                age_hours = (datetime.now(tz=timezone.utc).timestamp() - ts) / 3600.0
            except Exception:  # noqa: BLE001
                age_hours = 0
            from_id = c.get("from_id") or 0
            queue_items.append({
                "id":         cid,
                "post_id":    p.get("id"),
                "post_url":   f"https://vk.com/wall{handle_to_owner(handle)}_{p.get('id')}",
                "author_id":  from_id,
                "author_url": f"https://vk.com/id{abs(int(from_id))}" if from_id else None,
                "time":       datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None,
                "age_hours":  round(age_hours, 1),
                "text":       text[:400],
                "tone":       tone,
                "post_text":  (p.get("text") or "")[:120],
            })

    # Приоритет: critical first, затем question, потом neutral by age
    tone_weight = {"critical": 0, "question": 1, "neutral": 2, "positive": 3}
    queue_items.sort(key=lambda i: (tone_weight.get(i["tone"], 9), -i["age_hours"]))

    queue = queue_items[:queue_limit]
    summary = _summarize(queue_items)

    return {"queue": queue, "state": "ok", "summary": summary}


def handle_to_owner(handle: str) -> str:
    """Если handle — это id12345, отдаём 12345 для wall.getComments owner_id.
    Иначе нужен resolveScreenName, но в нашем случае Pavlova = id342610269."""
    h = (handle or "").strip()
    if h.startswith("id") and h[2:].isdigit():
        return h[2:]
    if h.lstrip("-").isdigit():
        return h
    return h  # screen_name — VK сам отрезолвит


async def _fetch_recent_posts(handle: str, token: str, count: int) -> List[Dict[str, Any]]:
    try:
        import aiohttp
    except Exception:  # noqa: BLE001
        return []
    is_numeric = handle.lstrip("id").lstrip("-").isdigit()
    params: Dict[str, Any] = {
        "count": count,
        "access_token": token,
        "v": "5.199",
    }
    if is_numeric:
        params["owner_id"] = handle.lstrip("id")
    else:
        params["domain"] = handle
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.vk.com/method/wall.get",
                params=params, timeout=12,
            ) as resp:
                data = await resp.json()
    except Exception:  # noqa: BLE001
        return []
    if "error" in data:
        return []
    items = (data.get("response") or {}).get("items") or []
    return items


async def _fetch_comments(owner_id: str, post_id: int, token: str) -> List[Dict[str, Any]]:
    try:
        import aiohttp
    except Exception:  # noqa: BLE001
        return []
    params = {
        "owner_id": owner_id,
        "post_id":  post_id,
        "count":    25,
        "sort":     "desc",
        "access_token": token,
        "v": "5.199",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.vk.com/method/wall.getComments",
                params=params, timeout=10,
            ) as resp:
                data = await resp.json()
    except Exception:  # noqa: BLE001
        return []
    if "error" in data:
        return []
    return (data.get("response") or {}).get("items") or []


def _classify_tone(text: str) -> str:
    if not text:
        return "neutral"
    low = text.lower()
    neg = sum(1 for kw in _NEGATIVE_KW if kw in low)
    pos = sum(1 for kw in _POSITIVE_KW if kw in low)
    has_q = "?" in text
    if neg >= 1 and neg > pos:
        return "critical"
    if has_q and neg == 0:
        return "question"
    if pos > 0 and neg == 0:
        return "positive"
    return "neutral"


def _summarize(items: List[Dict[str, Any]]) -> str:
    if not items:
        return ""
    n = len(items)
    crit = sum(1 for i in items if i["tone"] == "critical")
    q = sum(1 for i in items if i["tone"] == "question")
    parts = [f"{n} ждут ответа"]
    if crit:
        parts.append(f"{crit} с негативом")
    if q:
        parts.append(f"{q} с вопросом")
    return "Очередь · " + " · ".join(parts) + "."
