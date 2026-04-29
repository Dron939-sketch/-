"""Утренний брифинг депутата — 5-минутное «что важно сегодня».

Собирает 4 ключевые карточки на сегодня + готовый текст для голосового
прочтения Джарвисом. Без дополнительных fetch'ей: использует уже
посчитанные данные кабинета (district_today, missions, plan, coalition,
calendar, mentions).

Идея: депутат открывает приложение утром → видит брифинг первым →
понимает что делать сегодня без листания всего кабинета.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def build_briefing(
    deputy: Dict[str, Any],
    archetype: Dict[str, Any],
    *,
    district_today: Optional[Dict[str, Any]] = None,
    missions: Optional[List[Dict[str, Any]]] = None,
    plan: Optional[Dict[str, Any]] = None,
    coalition: Optional[Dict[str, Any]] = None,
    calendar: Optional[List[Dict[str, Any]]] = None,
    mentions: Optional[Dict[str, Any]] = None,
    timing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Возвращает {greeting, items[4], voice_text} для UI и голоса."""
    name_parts = (deputy.get("name") or "").split(" ")
    first = name_parts[1] if len(name_parts) > 1 else (name_parts[0] if name_parts else "")
    diminutive = _DIMINUTIVES.get(first, first)
    greeting = _greeting_by_hour(diminutive)

    items: List[Dict[str, Any]] = []

    # 1. Горячая тема дня — приоритет округа или ближайший повод
    today_items = (district_today or {}).get("items") or []
    if today_items:
        first_topic = today_items[0]
        items.append({
            "kind":   "hot_topic",
            "icon":   "🔥",
            "title":  "Горячая тема в округе",
            "body":   first_topic.get("text", ""),
            "tag":    first_topic.get("sector") or "округ",
            "action": "Сделать пост-разбор",
            "wizard": "content",
        })
    elif calendar:
        soon = next((e for e in calendar if (e.get("days_until") or 99) <= 3), None)
        if soon:
            items.append({
                "kind":   "calendar_event",
                "icon":   "🗓",
                "title":  f"Повод близко — {soon.get('title', '')}",
                "body":   soon.get("hint", ""),
                "tag":    "событие",
                "action": "Подготовить пост",
                "wizard": "content",
            })

    # 2. Срочная миссия — то, что просело сильнее всего
    if missions:
        m = missions[0]
        items.append({
            "kind":   "urgent_mission",
            "icon":   "🎯",
            "title":  m.get("title", ""),
            "body":   m.get("hint") or m.get("why", ""),
            "tag":    "миссия",
            "action": "Принять",
            "wizard": None,
        })

    # 3. Готовый пост на сегодня — из плана недели
    if plan and plan.get("items"):
        today_dow = _RU_DAYS_SHORT[datetime.now().weekday()]
        slot = next(
            (i for i in plan["items"] if i.get("day", "").lower().startswith(today_dow.lower())),
            plan["items"][0],
        )
        items.append({
            "kind":   "ready_post",
            "icon":   "✏",
            "title":  f"Готовый пост — {slot.get('day','')}",
            "body":   slot.get("topic", ""),
            "tag":    "контент-план",
            "action": "Скопировать",
            "wizard": "content",
            "draft":  slot.get("draft", ""),
        })

    # 4. Вдохновение от коллеги или упоминание о тебе
    if mentions and mentions.get("items"):
        # Если есть критический mention — приоритет на него (требует реакции)
        critical = next((m for m in mentions["items"] if m.get("kind") == "critical"), None)
        if critical:
            items.append({
                "kind":   "needs_reply",
                "icon":   "⚠",
                "title":  "Требует ответа",
                "body":   critical.get("text", ""),
                "tag":    critical.get("source") or "комментарий",
                "action": "Ответить",
                "wizard": None,
            })
        elif coalition and coalition.get("items"):
            colleague = coalition["items"][0]
            items.append({
                "kind":   "coalition",
                "icon":   "🤝",
                "title":  f"Совместный шаг — {colleague.get('name', '')}",
                "body":   f"Сильна в: {colleague.get('strength', '—')}. Совместный пост даёт +30-50% охвата.",
                "tag":    "коалиция",
                "action": "Предложить",
                "wizard": None,
            })

    # Дополним до 4-х из лучшего окна публикации, если ещё мало
    if len(items) < 4 and timing and timing.get("heatmap", {}).get("state") == "ok":
        bc = timing["heatmap"].get("best_cell") or {}
        if bc.get("avg_likes", 0) > 0:
            items.append({
                "kind":   "best_window",
                "icon":   "📊",
                "title":  f"Окно публикации — {bc.get('day')}, {bc.get('band')}",
                "body":   f"В среднем {bc.get('avg_likes')} лайков. Запланируй главный пост недели сюда.",
                "tag":    "аналитика",
                "action": "Запланировать",
                "wizard": None,
            })

    items = items[:4]

    voice_text = _build_voice_text(diminutive, items, archetype)

    return {
        "greeting":     greeting,
        "items":        items,
        "voice_text":   voice_text,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RU_DAYS_SHORT = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


_DIMINUTIVES = {
    "Наталья":   "Наташа",
    "Александр": "Саша",
    "Сергей":    "Серёжа",
    "Андрей":    "Андрей",
    "Дмитрий":   "Дима",
    "Алексей":   "Алёша",
    "Михаил":    "Миша",
    "Николай":   "Коля",
    "Виктор":    "Витя",
    "Анатолий":  "Толя",
    "Игорь":     "Игорь",
    "Роман":     "Рома",
    "Валерий":   "Валера",
    "Жанна":     "Жанна",
    "Екатерина": "Катя",
    "Нина":      "Нина",
    "Наталия":   "Наташа",
}


def _greeting_by_hour(name: str) -> str:
    h = datetime.now().hour
    if 5 <= h < 11:
        return f"Доброе утро, {name}!"
    if 11 <= h < 17:
        return f"Добрый день, {name}!"
    if 17 <= h < 23:
        return f"Добрый вечер, {name}!"
    return f"Привет, {name}."


def _build_voice_text(
    name: str, items: List[Dict[str, Any]], archetype: Dict[str, Any],
) -> str:
    """Текст для TTS — Джарвис говорит за 2 минуты."""
    parts: List[str] = []
    parts.append(_greeting_by_hour(name))
    parts.append(
        f"Я подготовил тебе короткий брифинг — {len(items)} пунктов на сегодня."
    )

    for i, it in enumerate(items, 1):
        body = (it.get("body") or "")[:240]
        title = it.get("title") or ""
        if it.get("kind") == "hot_topic":
            parts.append(f"Первое. Горячая тема в округе. {body}.")
        elif it.get("kind") == "calendar_event":
            parts.append(f"{_n(i)}. Близкий повод — {title}. {body}.")
        elif it.get("kind") == "urgent_mission":
            parts.append(f"{_n(i)}. Срочная миссия. {title}. {body}.")
        elif it.get("kind") == "ready_post":
            parts.append(f"{_n(i)}. У тебя готов пост на сегодня — тема: {body}.")
        elif it.get("kind") == "needs_reply":
            parts.append(f"{_n(i)}. Кое-что требует ответа. {body}.")
        elif it.get("kind") == "coalition":
            parts.append(f"{_n(i)}. Совет от Джарвиса. {body}.")
        elif it.get("kind") == "best_window":
            parts.append(f"{_n(i)}. {title}. {body}.")
        else:
            parts.append(f"{_n(i)}. {title}. {body}.")

    parts.append(
        f"Голос архетипа «{archetype.get('name','—')}» — твоя сильная сторона. "
        "Удачного дня."
    )
    return " ".join(parts)


def _n(i: int) -> str:
    return ["Первое", "Второе", "Третье", "Четвёртое", "Пятое"][i - 1] \
        if 1 <= i <= 5 else f"Пункт {i}"
