"""Логика памяти Джарвиса: извлечение тем + сборка блока для prompt.

Эвристики, без LLM-вызовов — чтобы не платить токенами за каждый turn.
Из вопроса пользователя ловим:
  - кейворд-категории (ЖКХ, транспорт, здравоохранение, ...) → topic
  - сам вопрос как recent_q (кратко обрезанный)

При сборке блока памяти возвращаем 2-3 строчки в плоском тексте,
которые подмешиваем в user prompt: «Что ты знаешь о собеседнике…».
"""

from __future__ import annotations

import logging
import re
from typing import List

from db import jarvis_memory_queries as mem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Кейворд-словарь категорий (совпадает с api/copilot_routes.py
# CATEGORY_KEYWORDS, но независим — модуль не должен импортить роуты).
# ---------------------------------------------------------------------------

_TOPIC_KEYWORDS = [
    ("ЖКХ",            re.compile(r"жкх|тепло|вод(а|ы|у|ой)|свет|труб|канализ|подъезд|двор", re.I)),
    ("транспорт",      re.compile(r"транспорт|дорог|автобус|пробк|трамвай|метро|тротуар", re.I)),
    ("здравоохранение", re.compile(r"поликлин|больниц|врач|медиц|здоров", re.I)),
    ("образование",    re.compile(r"школ|детск|образован|учител|садик", re.I)),
    ("соцзащита",      re.compile(r"социал|пенси|пособи|инвалид|многодет|защит", re.I)),
    ("спорт",          re.compile(r"спорт|стадион|тренаж|футбол|бассейн|физкультур", re.I)),
    ("культура",       re.compile(r"(?<!физ)культур|музей|театр|выставк|концерт", re.I)),
    ("молодёжь",       re.compile(r"молодёж|молодеж|подрост|студент", re.I)),
    ("безопасность",   re.compile(r"безопас|преступ|правонаруш|кражи?|разбой|полиц", re.I)),
    ("экономика",      re.compile(r"эконом|бюджет|налог|инвестиц|зарплат", re.I)),
]


def detect_topics(text: str) -> List[str]:
    """Список совпавших тем по кейворд-словарю. Без дублей, в порядке
    объявления в _TOPIC_KEYWORDS."""
    if not text:
        return []
    out: List[str] = []
    for label, rx in _TOPIC_KEYWORDS:
        if rx.search(text) and label not in out:
            out.append(label)
    return out


def _shorten_question(text: str, *, limit: int = 200) -> str:
    """Усечь вопрос для recent_q — без обрыва на середине слова."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    if space > 100:
        cut = cut[:space]
    return cut + "…"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def record_user_turn(identity: str, question: str) -> None:
    """Извлекает темы + сохраняет вопрос в память."""
    if not identity or not question:
        return
    for topic in detect_topics(question):
        await mem.upsert(identity, "topic", topic)
    short = _shorten_question(question)
    if short:
        await mem.upsert(identity, "recent_q", short)


async def build_memory_lines(identity: str) -> List[str]:
    """2-4 строки текста для подмеса в prompt.

    Пример вывода:
      ["Часто спрашивает о: транспорт, ЖКХ.",
       "Прошлые темы разговоров: «когда починят дороги?», «что с уборкой снега?»."]
    """
    if not identity:
        return []
    lines: List[str] = []
    topics = await mem.top_topics(identity, limit=4)
    if topics:
        joined = ", ".join(t["topic"] for t in topics)
        lines.append(f"Часто спрашивает о: {joined}.")
    qs = await mem.last_questions(identity, limit=3)
    if qs:
        joined_q = "; ".join(f"«{q}»" for q in qs[:3])
        lines.append(f"Прошлые вопросы: {joined_q}.")
    return lines
