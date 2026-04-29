"""Демо-данные для блоков «Упоминания» и «Коалиция» в кабинете депутата.

Реальные источники (поиск VK + анализ упоминаний) подключим отдельным
этапом. Сейчас — статика для wow-демо: для Павловой собран реальный
состав Округа №1 по config.deputies + типичные паттерны упоминаний.

Когда подключим парсер VK, форма ответа не изменится, просто
data_kind="demo" → "live".
"""

from __future__ import annotations

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Упоминания обо мне — 3 типа: позитив / нейтрал / негатив
# ---------------------------------------------------------------------------

_DEFAULT_MENTIONS: List[Dict[str, Any]] = [
    {
        "kind":     "positive",
        "source":   "Соседский паблик",
        "context":  "Жительница округа",
        "text":     "Спасибо депутату — реально вышли проверить двор после моей жалобы.",
        "weight":   "good",
    },
    {
        "kind":     "neutral",
        "source":   "Чат подъезда",
        "context":  "Активист дома",
        "text":     "Видел депутата на встрече — рассказала про планы по благоустройству.",
        "weight":   "neutral",
    },
    {
        "kind":     "critical",
        "source":   "Комментарии под постом",
        "context":  "Мама школьника",
        "text":     "Ответ так и не пришёл, написала 2 недели назад про детский сад.",
        "weight":   "bad",
    },
]


def mentions_for(deputy: Dict[str, Any]) -> Dict[str, Any]:
    """Заглушки для блока «Упоминания обо мне». В реальности — VK search."""
    return {
        "data_kind": "demo",
        "items":     _DEFAULT_MENTIONS,
        "summary":   "За неделю — ~12 упоминаний. 67% позитив, 25% нейтрал, 8% критика.",
        "hint":      "Эти карточки — пример. Когда подключим парсер VK, заменим на живые упоминания.",
    }


# ---------------------------------------------------------------------------
# Коалиция — соседи по Округу + руководство Совета
# ---------------------------------------------------------------------------

# Тематические сильные стороны (для индикатора «силен в…»)
_DEPUTY_STRENGTHS = {
    "vaulin-av":     "ЖКХ",
    "orlov-sv":      "благоустройство",
    "kostyunin-aa":  "соцзащита",
    "rvachev-vm":    "общая_повестка",
    "bratushkov-nv": "руководство Совета",
    "androsov-rv":   "комиссия по бюджету",
    "kossov-vs":     "правовые вопросы",
}


def coalition_for(deputy: Dict[str, Any], all_deputies: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Соседи по округу + 1-2 ключевых руководителя Совета."""
    district = deputy.get("district") or ""
    my_id = deputy.get("external_id")

    # Соседи по округу (исключаем себя)
    neighbours = [
        d for d in all_deputies
        if d.get("district") == district and d.get("external_id") != my_id
    ]

    # 1-2 руководителя Совета (speaker)
    leadership = [d for d in all_deputies if d.get("role") == "speaker"]

    items = []
    for d in neighbours[:4]:
        items.append({
            "external_id": d.get("external_id"),
            "name":        d.get("name"),
            "role":        "По округу",
            "strength":    _DEPUTY_STRENGTHS.get(d.get("external_id"), "общая повестка"),
            "scope":       "neighbour",
        })
    for d in leadership[:2]:
        items.append({
            "external_id": d.get("external_id"),
            "name":        d.get("name"),
            "role":        d.get("note") or "Руководство Совета",
            "strength":    _DEPUTY_STRENGTHS.get(d.get("external_id"), "руководство"),
            "scope":       "leadership",
        })

    return {
        "data_kind": "demo",
        "district":  district,
        "items":     items,
        "hint":      "Совместный пост / встреча / акция с коллегой даёт +30-50% охвата.",
    }
