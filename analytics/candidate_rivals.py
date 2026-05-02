"""Досье на конкурентов кандидата.

5-7 типичных оппонентов с метриками. Сейчас demo-конфиг,
адаптируется под партию текущего кандидата (свой и чужие).

Для каждого rival:
- ФИО (или прозвище)
- Партия + цвет
- Статус: «registered» | «primaries» | «not_registered»
- Метрики (compare-grade): охват / частота / тон / опыт
- Sentiment: tone их соцсетей (positive/neutral/critical)
- Угроза: 1-5 (5 = самый опасный)

В будущем — ручной ввод через UI + хранение в БД.
"""

from __future__ import annotations

from typing import Any, Dict, List


# Базовые demo-rivals — типажи, не реальные люди
_BASE_RIVALS: List[Dict[str, Any]] = [
    {
        "code":   "incumbent",
        "name":   "Действующий депутат-старожил",
        "party":  "er",
        "status": "registered",
        "experience_years": 12,
        "reach":     85,    # 0-100
        "frequency": 70,
        "tone":      "Сдержанный, опытный",
        "sentiment": "positive",
        "threat":    5,
        "strengths": "Связи в администрации, известность, опытная команда",
        "weaknesses": "Усталость избирателей, ассоциация с проблемами региона",
    },
    {
        "code":   "challenger",
        "name":   "Молодой бизнесмен — новое лицо",
        "party":  "new_people",
        "status": "primaries",
        "experience_years": 0,
        "reach":     45,
        "frequency": 90,
        "tone":      "Энергичный, прямой",
        "sentiment": "positive",
        "threat":    4,
        "strengths": "Свежесть, цифровая грамотность, бизнес-кейсы",
        "weaknesses": "Нет политического опыта, узкая аудитория",
    },
    {
        "code":   "populist",
        "name":   "Эмоциональный оппозиционер",
        "party":  "ldpr",
        "status": "primaries",
        "experience_years": 4,
        "reach":     60,
        "frequency": 85,
        "tone":      "Резкий, эмоциональный",
        "sentiment": "critical",
        "threat":    3,
        "strengths": "Узнаваемость, медийность, эмоциональный отклик",
        "weaknesses": "Неустойчивая поддержка, конфликты с системой",
    },
    {
        "code":   "social",
        "name":   "Защитник трудящихся",
        "party":  "kprf",
        "status": "registered",
        "experience_years": 8,
        "reach":     50,
        "frequency": 40,
        "tone":      "Идейный, серьёзный",
        "sentiment": "neutral",
        "threat":    3,
        "strengths": "Твёрдая идейная база, лояльный электорат пенсионеров",
        "weaknesses": "Низкая активность в соцсетях, мало молодёжи",
    },
    {
        "code":   "independent",
        "name":   "Самовыдвиженец-активист",
        "party":  "independent",
        "status": "not_registered",
        "experience_years": 2,
        "reach":     30,
        "frequency": 75,
        "tone":      "Локальный, искренний",
        "sentiment": "positive",
        "threat":    2,
        "strengths": "Личные знакомства в округе, гибкость",
        "weaknesses": "Сложности со сбором подписей, ресурсы ограничены",
    },
]


# Цвета партий (как в role_picker)
_PARTY_COLORS = {
    "er":          "#2C70D9",
    "new_people":  "#00B4FF",
    "ldpr":        "#FFD700",
    "sr":          "#FF6B6B",
    "kprf":        "#C70000",
    "independent": "#B0B0B0",
}

_PARTY_SHORTS = {
    "er":          "ЕР",
    "new_people":  "НЛ",
    "ldpr":        "ЛДПР",
    "sr":          "СР",
    "kprf":        "КПРФ",
    "independent": "Самовыдв.",
}


def build_rivals_block(my_party: str) -> Dict[str, Any]:
    """Собирает досье на конкурентов с учётом партии текущего кандидата.
    Свои по партии — ниже в приоритете (это конкуренты в праймериз),
    чужие — стандартная конкурентная гонка.
    """
    rivals = []
    for r in _BASE_RIVALS:
        is_same_party = r["party"] == my_party
        rivals.append({
            **r,
            "party_short": _PARTY_SHORTS.get(r["party"], "?"),
            "party_color": _PARTY_COLORS.get(r["party"], "#5EA8FF"),
            "is_same_party": is_same_party,
            "competition_kind": "intra-party" if is_same_party else "inter-party",
        })

    # Сортировка: сначала по угрозе (опасные first)
    rivals.sort(key=lambda x: -x["threat"])

    # Сравнительная таблица — собираем агрегаты для контекста
    if rivals:
        avg_reach = round(sum(r["reach"] for r in rivals) / len(rivals))
        avg_freq  = round(sum(r["frequency"] for r in rivals) / len(rivals))
        max_reach = max(r["reach"] for r in rivals)
        max_freq  = max(r["frequency"] for r in rivals)
    else:
        avg_reach = avg_freq = max_reach = max_freq = 0

    return {
        "data_kind": "demo",
        "items":     rivals,
        "aggregate": {
            "count":     len(rivals),
            "avg_reach": avg_reach,
            "avg_freq":  avg_freq,
            "max_reach": max_reach,
            "max_freq":  max_freq,
        },
        "hint":      "Это типажи конкурентов — реальных по округу добавишь в Этапе 6.",
    }
