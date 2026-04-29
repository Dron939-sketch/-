"""Карта внимания горожан — что обсуждают сейчас по секторам депутата.

Источники в порядке приоритета:
1. VK newsfeed.search по ключевикам секторов + название города (если
   есть VK token — даёт горячие посты публики, не из её ленты)
2. Локальная БД news, отфильтрованная по category-маппингу секторов

На выход — топ-5 «трендов» (ключевое слово / тема + примеры постов +
суммарный engagement), которые депутату стоит подхватить или обыграть.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Маппинг sector → ключевые слова для VK поиска
_SECTOR_KEYWORDS = {
    "ЖКХ":             ["ЖКХ", "отопление", "управляющая компания"],
    "благоустройство": ["благоустройство", "двор", "детская площадка"],
    "соцзащита":       ["соцзащита", "пенсионеры", "многодетные"],
    "здравоохранение": ["поликлиника", "врач", "скорая"],
    "молодёжь":        ["молодёжь", "школьники", "подростки"],
    "образование":     ["школа", "детский сад", "учитель"],
    "транспорт":       ["автобус", "дорога", "пробки"],
    "ТКО":             ["мусор", "контейнер", "вывоз"],
    "общая_повестка":  ["администрация", "городской совет", "депутаты"],
    "экономика":       ["бюджет", "налоги", "инвестиции"],
    "культура":        ["культура", "библиотека", "музей"],
}

# Маппинг sector → news.category (для fallback)
_SECTOR_TO_CATEGORY = {
    "ЖКХ":             ["utilities", "complaints"],
    "благоустройство": ["complaints", "incidents"],
    "соцзащита":       ["social", "official"],
    "здравоохранение": ["health"],
    "молодёжь":        ["culture", "sport"],
    "образование":     ["education"],
    "транспорт":       ["transport"],
    "ТКО":             ["utilities"],
    "экономика":       ["economy"],
    "культура":        ["culture"],
    "общая_повестка":  ["official"],
}

_STOPWORDS = {
    "это", "что", "как", "так", "уже", "ещё", "только", "сейчас", "может",
    "будет", "если", "когда", "потому", "после", "перед", "очень", "также",
    "более", "менее", "сегодня", "вчера", "завтра", "недели", "недель",
    "коломна", "коломне", "коломны", "коломну", "город", "города", "году",
}

_WORD_RE = re.compile(r"[а-яёa-z]{4,}", re.IGNORECASE)


async def build_trends(
    deputy: Dict[str, Any], city: str = "Коломна",
) -> Dict[str, Any]:
    """Возвращает {trends: [...], source, state}."""
    sectors = list(deputy.get("sectors") or [])
    if not sectors:
        return {"trends": [], "state": "no_sectors", "source": None}

    # 1. Пробуем VK newsfeed.search
    vk_trends = await _vk_trends(sectors, city)
    if vk_trends:
        return {"trends": vk_trends, "state": "ok", "source": "vk"}

    # 2. Fallback на локальную БД news
    db_trends = await _db_trends(sectors, city)
    if db_trends:
        return {"trends": db_trends, "state": "ok", "source": "db"}

    return {"trends": [], "state": "no_data", "source": None}


# ---------------------------------------------------------------------------
# VK newsfeed.search
# ---------------------------------------------------------------------------

def _city_pattern(city: str) -> str:
    base = (city or "").strip().lower()
    if not base:
        return r"коломн"
    stem = base[:-1] if base.endswith("а") else base
    lat = {"коломн": "kolomn"}.get(stem, "")
    pat = re.escape(stem) + r"\w{0,4}"
    if lat:
        pat = f"(?:{pat}|{re.escape(lat)}\\w{{0,4}})"
    return pat


async def _vk_trends(sectors: List[str], city: str) -> List[Dict[str, Any]]:
    try:
        import aiohttp
        from config.settings import settings
    except Exception:  # noqa: BLE001
        return []
    token = settings.vk_api_token
    if not token:
        return []

    # Берём топ-2 ключевика на сектор × максимум 4 сектора → 8 поисков
    keywords: List[str] = []
    for s in sectors[:4]:
        for kw in (_SECTOR_KEYWORDS.get(s) or [])[:2]:
            keywords.append(kw)
    if not keywords:
        return []

    cutoff = (datetime.now(tz=timezone.utc) - timedelta(hours=48)).timestamp()
    aggregated: Dict[str, Dict[str, Any]] = {}
    city_re = re.compile(_city_pattern(city), re.IGNORECASE)

    async with aiohttp.ClientSession() as session:
        for kw in keywords:
            q = f"{kw} {city}"
            params = {
                "q":            q,
                "count":        20,
                "extended":     1,
                "access_token": token,
                "v":            "5.199",
            }
            try:
                async with session.get(
                    "https://api.vk.com/method/newsfeed.search",
                    params=params, timeout=12,
                ) as resp:
                    data = await resp.json()
            except Exception:  # noqa: BLE001
                continue
            if "error" in data:
                continue
            items = (data.get("response") or {}).get("items") or []
            for it in items:
                ts = int(it.get("date") or 0)
                if ts < cutoff:
                    continue
                text = (it.get("text") or "").strip()
                if not text:
                    continue
                # Жёсткий фильтр на упоминание Коломны — VK по ключевику
                # «двор» / «школа» возвращает посты из любых городов
                if not city_re.search(text):
                    continue
                eng = (
                    int((it.get("likes") or {}).get("count") or 0)
                    + int((it.get("reposts") or {}).get("count") or 0) * 2
                    + int((it.get("comments") or {}).get("count") or 0) * 3
                )
                # ID в VK = "owner_id_post_id"
                owner = it.get("owner_id") or it.get("from_id")
                pid = it.get("id")
                vk_url = (
                    f"https://vk.com/wall{owner}_{pid}"
                    if owner and pid else None
                )
                key = kw.lower()
                bucket = aggregated.setdefault(key, {
                    "keyword":   kw,
                    "posts":     0,
                    "engagement": 0,
                    "samples":   [],
                })
                bucket["posts"] += 1
                bucket["engagement"] += eng
                if len(bucket["samples"]) < 3:
                    bucket["samples"].append({
                        "text": text[:240],
                        "url":  vk_url,
                        "engagement": eng,
                    })

    # Сортируем по engagement
    out = sorted(aggregated.values(), key=lambda b: -b["engagement"])
    return out[:5]


# ---------------------------------------------------------------------------
# Local DB fallback
# ---------------------------------------------------------------------------

async def _db_trends(sectors: List[str], city: str) -> List[Dict[str, Any]]:
    try:
        from db.queries import top_recent_summaries
        from db.seed import city_id_by_name
    except Exception:  # noqa: BLE001
        return []
    try:
        city_id = await city_id_by_name(city)
    except Exception:  # noqa: BLE001
        return []
    if not city_id:
        return []

    cats: List[str] = []
    for s in sectors:
        for c in _SECTOR_TO_CATEGORY.get(s, []):
            if c not in cats:
                cats.append(c)
    if not cats:
        return []

    try:
        items = await top_recent_summaries(city_id, categories=cats, limit=20)
    except Exception:  # noqa: BLE001
        items = []
    if not items:
        return []

    # Группируем по топ-словам
    word_to_items: Dict[str, List[str]] = {}
    word_counts: Counter = Counter()
    for text in items:
        words = [w.lower() for w in _WORD_RE.findall(text)]
        words = [w for w in words if w not in _STOPWORDS and len(w) >= 5]
        for w in set(words):
            word_counts[w] += 1
            word_to_items.setdefault(w, []).append(text)

    out: List[Dict[str, Any]] = []
    for w, c in word_counts.most_common(5):
        if c < 2:
            continue
        samples = word_to_items[w][:3]
        out.append({
            "keyword":    w,
            "posts":      c,
            "engagement": 0,
            "samples": [
                {"text": s[:240], "url": None, "engagement": 0}
                for s in samples
            ],
        })
    return out
