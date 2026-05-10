"""Где комментировать — посты горожан, под которыми комментарий депутата
принесёт максимум внимания.

Логика поиска:
1. VK newsfeed.search по ключевикам её секторов + название города
2. Фильтр: посты с высокими likes/views, но пока МАЛО комментариев
   (комментарий депутата заметен; на «забитых» постах теряется)
3. Сортировка по «opportunity score» = engagement × (1 / (comments+1))

Каждая карточка содержит готовый шаблон комментария в её архетипе:
дружелюбный + полезный + с предложением встретиться. Депутат
открывает пост в VK, копирует комментарий, отправляет.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Маппинг sector → ключевые слова для поиска постов
_SECTOR_KEYWORDS = {
    "ЖКХ":             ["ЖКХ", "отопление"],
    "благоустройство": ["двор", "благоустройство"],
    "соцзащита":       ["многодетные", "пенсионеры"],
    "здравоохранение": ["поликлиника", "врач"],
    "молодёжь":        ["подростки", "школьники"],
    "образование":     ["школа", "детский сад"],
    "транспорт":       ["автобус", "дорога"],
    "ТКО":             ["мусор", "контейнер"],
    "общая_повестка":  ["администрация", "город"],
}


# Шаблоны комментариев под архетип. Депутат адаптирует, не копирует слепо.
_COMMENT_TEMPLATES = {
    "caregiver": (
        "Спасибо, что подняли тему. Я слышу. Готова разобраться вместе — "
        "напишите мне в личные адрес и контакт, передам в УК и проконтролирую."
    ),
    "ruler": (
        "Принял. Передаю в работу профильному отделу. "
        "Срок — 10 рабочих дней. Отчитаюсь по результату."
    ),
    "sage": (
        "По нормативу у этой ситуации есть процедура решения. "
        "Если интересно — расскажу, что предусмотрено и как использовать. "
        "Напишите в личные."
    ),
    "hero": (
        "Беру под контроль. Если ведомство будет тянуть — поднимем вопрос "
        "публично. Жду от вас адрес и фото для протокола."
    ),
    "explorer": (
        "Спасибо. Сегодня же проеду по этой точке, посмотрю своими глазами. "
        "Готова взять с собой 1-2 жителей — кто хочет, пишите."
    ),
    "creator": (
        "Кейс знакомый — у нас уже есть рабочее решение в соседнем дворе. "
        "Хотите, расскажу как оно устроено? Можем повторить."
    ),
    "everyman": (
        "Здравствуйте, соседи. Меня тоже это беспокоит — давайте решать "
        "вместе. Напишите контакт, познакомимся."
    ),
    "lover": (
        "Спасибо, что пишете. Очень переживаю с вами — давайте разберёмся "
        "по-человечески. Пишите в личные."
    ),
    "jester": (
        "Видел, услышал, принял :) Без формализма — пишите в личные, "
        "буду решать."
    ),
    "innocent": (
        "Спасибо за доверие. Постараемся сделать всё, что в наших силах. "
        "Пишите контакт — буду на связи."
    ),
    "magician": (
        "Это часто симптом более глубокой проблемы. "
        "Если хотите системного решения — напишите, обсудим."
    ),
    "outlaw": (
        "Долго это всё терпеть нельзя. Беру в работу. "
        "Жду от вас фактов — адрес, фото, дату."
    ),
}


def _city_pattern(city: str) -> str:
    """Регексп под все падежи названия города. Простая морфология:
    отбрасываем последние 1-2 буквы и ищем все склонения с любыми
    концовками 1-3 символа.
    """
    base = (city or "").strip().lower()
    if not base:
        return r"коломн"
    if base.endswith("а"):
        stem = base[:-1]
    else:
        stem = base
    # Латиница для VK-постов от англоязычной аудитории
    lat = {"коломн": "kolomn"}.get(stem, "")
    pat = re.escape(stem) + r"\w{0,4}"
    if lat:
        pat = f"(?:{pat}|{re.escape(lat)}\\w{{0,4}})"
    return pat


async def build_comment_targets(
    deputy: Dict[str, Any], archetype: Dict[str, Any], city: str = "Коломна",
) -> Dict[str, Any]:
    """Возвращает {targets: [...], state, source}."""
    sectors = list(deputy.get("sectors") or [])
    if not sectors:
        return {"targets": [], "state": "no_sectors"}

    template = _COMMENT_TEMPLATES.get(archetype.get("code") or "everyman", _COMMENT_TEMPLATES["everyman"])

    # 1. VK newsfeed.search
    vk_targets = await _vk_targets(sectors, city, template)
    if vk_targets:
        return {"targets": vk_targets, "state": "ok", "source": "vk"}

    return {"targets": [], "state": "no_data"}


async def _vk_targets(
    sectors: List[str], city: str, template: str,
) -> List[Dict[str, Any]]:
    try:
        import aiohttp
        from config.settings import settings
    except Exception:  # noqa: BLE001
        return []
    if getattr(settings, "demo_mode", False):
        return []
    token = settings.vk_api_token
    if not token:
        return []

    keywords: List[str] = []
    for s in sectors[:3]:
        for kw in (_SECTOR_KEYWORDS.get(s) or [])[:2]:
            keywords.append(kw)
    if not keywords:
        return []

    cutoff = (datetime.now(tz=timezone.utc) - timedelta(hours=72)).timestamp()
    candidates: List[Dict[str, Any]] = []
    # Регексп для проверки, что пост действительно про этот город:
    # «коломна», «коломне», «коломенск», и склонения. VK newsfeed.search
    # часто возвращает посты по соседним темам без географической привязки.
    city_re = re.compile(_city_pattern(city), re.IGNORECASE)

    async with aiohttp.ClientSession() as session:
        for kw in keywords:
            params = {
                "q":            f"{kw} {city}",
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
                if not text or len(text) < 60:
                    continue
                # Жёстко фильтруем по упоминанию города — VK возвращает посты
                # по ключевику «двор», «школа» вообще откуда угодно (часто
                # из Зеленограда / Москвы)
                if not city_re.search(text):
                    continue
                likes    = int((it.get("likes") or {}).get("count") or 0)
                views    = int((it.get("views") or {}).get("count") or 0)
                comments = int((it.get("comments") or {}).get("count") or 0)
                # Opportunity score: high reach (likes+views) but low comments
                if likes + views < 30:
                    continue
                opportunity = round((likes * 3 + views * 0.1) / max(comments + 1, 1), 1)
                owner = it.get("owner_id") or it.get("from_id")
                pid = it.get("id")
                vk_url = f"https://vk.com/wall{owner}_{pid}" if owner and pid else None
                candidates.append({
                    "text":       text[:280],
                    "likes":      likes,
                    "views":      views,
                    "comments":   comments,
                    "opportunity": opportunity,
                    "url":        vk_url,
                    "keyword":    kw,
                    "comment":    template,
                })
    candidates.sort(key=lambda x: -x["opportunity"])
    # Уникализуем по началу текста
    seen = set()
    out: List[Dict[str, Any]] = []
    for c in candidates:
        key = (c["text"][:60]).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
        if len(out) >= 5:
            break
    return out
