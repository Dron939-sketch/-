"""Авто-сгенерированное описание депутата.

Из role / district / sectors / архетипа собираем 2-3 предложения,
которые читаются как нормальная человеческая характеристика. Без
LLM (быстро + кэшируется).

Приоритет: реальный VK status / about, если есть; иначе — собранный
текст по полям из config.deputies.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_bio(
    deputy: Dict[str, Any],
    archetype: Dict[str, Any],
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Возвращает {summary, facts, calling_card}.

    summary — 2-3 связных предложения для верха кабинета.
    facts   — список 3-5 фактов чипами (округ, сектора, роль, профиль).
    calling_card — короткое представление для обложки приложения.
    """
    name = deputy.get("name") or "—"
    district = deputy.get("district") or ""
    sectors = list(deputy.get("sectors") or [])
    role = deputy.get("role") or "district_rep"
    note = deputy.get("note") or ""
    arch_name = archetype.get("name") or "—"
    arch_voice = archetype.get("voice") or ""

    role_label = {
        "district_rep": "Депутат от округа",
        "speaker":      "Руководитель в Совете депутатов",
        "sector_lead":  "Куратор сектора",
        "support":      "Депутат",
    }.get(role, "Депутат")

    sector_phrase = ""
    if sectors:
        if len(sectors) == 1:
            sector_phrase = f"работает по теме «{sectors[0]}»"
        elif len(sectors) <= 3:
            sector_phrase = "работает по темам " + ", ".join(f"«{s}»" for s in sectors)
        else:
            sector_phrase = (
                "работает по широкому набору тем, ключевые — "
                + ", ".join(f"«{s}»" for s in sectors[:3])
            )

    archetype_phrase = (
        f"Голос — «{arch_name}»: {arch_voice.lower()}" if arch_voice else
        f"Голос ближе всего к архетипу «{arch_name}»."
    )

    parts: List[str] = []
    parts.append(f"{role_label} {district}".strip(". ") + ".")
    if sector_phrase:
        parts.append(f"В Совете {sector_phrase}.")
    if note:
        parts.append(note + ".")
    parts.append(archetype_phrase)
    if profile and profile.get("about"):
        parts.append("О себе: «" + str(profile["about"])[:280] + "»")

    summary = " ".join(parts)

    facts = []
    facts.append({"icon": "🏛", "label": role_label})
    if district:
        facts.append({"icon": "📍", "label": district})
    if sectors:
        facts.append({"icon": "🗂", "label": " · ".join(sectors[:3])})
    if profile and profile.get("followers"):
        facts.append({"icon": "👥", "label": f"{profile['followers']} подписчиков в VK"})
    if profile and profile.get("verified"):
        facts.append({"icon": "✓",  "label": "Верифицирована в VK"})
    facts.append({"icon": "🎭", "label": f"Архетип «{arch_name}»"})

    # «Визитка» — короткое представление в одну строку для шапки
    calling_card = (
        f"{role_label} · {district}"
        + (f" · {sectors[0]}" if sectors else "")
        + f" · «{arch_name}»"
    )

    return {
        "summary":       summary,
        "facts":         facts,
        "calling_card":  calling_card,
    }
