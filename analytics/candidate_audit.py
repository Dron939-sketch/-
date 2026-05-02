"""Аудит VK-страницы кандидата + рекомендации по победной стратегии.

Использует существующие модули:
- analytics.vk_audit.audit_vk_page — базовый аудит (тот же что у депутата)
- analytics.archetype_affinity — близость к 12 архетипам
- analytics.voice_portrait — голос-портрет
- analytics.vk_profile — фото / bio / followers

Поверх собирает 4 уровня рекомендаций специфичных для КАНДИДАТА:
1. Образ — какое впечатление складывается у избирателя
2. Бренд — что укрепить/выправить
3. Архетип — какой выбрать как основной (с учётом партии)
4. Победная стратегия — конкретные действия в ближайшие 30 дней
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Подходящий архетип под каждую партию — рекомендация если у кандидата
# текущий архетип не совпадает.
_PARTY_RECOMMENDED_ARCHETYPE = {
    "er":          {"code": "ruler",     "name": "Правитель",   "why": "ЕР — партия порядка и стабильности. Голосом Правителя легче говорить итогами и сроками."},
    "new_people":  {"code": "sage",      "name": "Мудрец",      "why": "НЛ — про данные и прозрачность. Голос Мудреца — цифры, факты, разъяснения."},
    "ldpr":        {"code": "outlaw",    "name": "Бунтарь",     "why": "ЛДПР исторически громкий и эмоциональный — голос Бунтаря резонирует с ядром."},
    "sr":          {"code": "caregiver", "name": "Заботливый",  "why": "СР — социальная защита. Заботливый говорит «мы», «вместе», «помогу»."},
    "kprf":        {"code": "sage",      "name": "Мудрец",      "why": "КПРФ — про идеологическую преемственность. Мудрец опирается на исторические параллели."},
    "independent": {"code": "everyman",  "name": "Свой",         "why": "Самовыдвиженцу нужно быть «соседом-соседу» — голос Своего звучит честно."},
}


async def build_candidate_audit(
    vk_handle: str, party_code: str,
) -> Dict[str, Any]:
    """Полный аудит для кандидата. Возвращает {audit, profile, affinity,
    voice_portrait, recommendations: {image, brand, archetype, strategy}}.
    """
    from analytics.archetype_affinity import compute_affinity
    from analytics.candidate_party import party_meta
    from analytics.vk_audit import audit_vk_page
    from analytics.vk_profile import fetch_profile
    from analytics.voice_portrait import build_voice_portrait

    party = party_meta(party_code)

    # Базовый аудит. На пустом handle вернёт state="no_vk_handle"
    audit = await audit_vk_page(vk_handle, archetype_code=None)
    profile = await fetch_profile(vk_handle) if vk_handle else None

    # Affinity 12 архетипов — насколько посты совпадают с каждым
    affinity = compute_affinity(audit)
    voice = build_voice_portrait(audit)

    # Рекомендации
    recs = _build_recommendations(audit, affinity, voice, party)

    # Уберём raw posts — они большие и не нужны клиенту
    audit.pop("_raw_posts", None)
    audit.pop("_posts_text", None)

    return {
        "audit":            audit,
        "profile":          profile,
        "affinity":         affinity[:5],   # top-5 архетипов хватит
        "voice_portrait":   voice,
        "recommendations":  recs,
        "party":            {
            "code":  party["code"],
            "short": party["short"],
            "name":  party["name"],
            "color": party["color"],
        },
    }


def _build_recommendations(
    audit: Dict[str, Any],
    affinity: List[Dict[str, Any]],
    voice: Dict[str, Any],
    party: Dict[str, Any],
) -> Dict[str, Any]:
    """4 секции рекомендаций для кандидата."""
    metrics = audit.get("metrics") or {}
    align_pct = audit.get("alignment_score") or 0
    posts_per_week = float(metrics.get("posts_per_week") or 0)
    avg_likes = float(metrics.get("avg_likes") or 0)

    main_arch = affinity[0] if affinity else None
    rec_arch = _PARTY_RECOMMENDED_ARCHETYPE.get(party["code"]) or _PARTY_RECOMMENDED_ARCHETYPE["independent"]
    arch_match = (main_arch and main_arch["code"] == rec_arch["code"])

    # ОБРАЗ — какое впечатление складывается у избирателя
    image: List[str] = []
    if main_arch:
        image.append(f"Сейчас ты воспринимаешься как «{main_arch['name']}» (близость {main_arch['affinity']}%) — {main_arch.get('short','')}")
    if voice and voice.get("state") == "ok":
        tone = voice.get("tone") or "—"
        image.append(f"Тональность твоих постов — «{tone}». {voice.get('headline','')}")
    if posts_per_week < 2:
        image.append("Редкие публикации (<2/нед) формируют образ закрытого человека. Избирателю не за что зацепиться.")
    elif posts_per_week >= 4:
        image.append("Высокая частота постов формирует образ деятельного — это плюс для агитации.")

    # БРЕНД — что укрепить/выправить
    brand: List[str] = []
    if not arch_match and main_arch:
        brand.append(
            f"Партии {party['short']} больше подходит «{rec_arch['name']}», а не «{main_arch['name']}». "
            f"{rec_arch['why']}"
        )
    if align_pct < 40:
        brand.append(
            f"Соответствие выбранному архетипу — всего {align_pct:.0f}%. "
            "Голос «плавает» — избирателю сложно запомнить твой стиль."
        )
    if avg_likes < 10:
        brand.append("Низкое среднее число лайков — публикации не цепляют. Усилить эмоциональную фактуру и фото.")
    if voice and voice.get("shares", {}).get("emoji", 0) < 30 and party["code"] in ("ldpr", "new_people"):
        brand.append("Эмодзи в постах <30% — для НЛ/ЛДПР это нормально-низкая цифровая выраженность.")

    # АРХЕТИП — рекомендация
    archetype_rec: List[str] = []
    archetype_rec.append(f"Целевой архетип под партию {party['short']} — «{rec_arch['name']}»")
    archetype_rec.append(f"Почему именно он: {rec_arch['why']}")
    if not arch_match and main_arch:
        archetype_rec.append(
            f"Сейчас ты ближе к «{main_arch['name']}». Сделай 5 постов подряд в стиле «{rec_arch['name']}» — "
            "соответствие подскочит на 15-20% за 2 недели."
        )
    elif arch_match:
        archetype_rec.append("Текущий голос совпадает с целевым архетипом — продолжай в том же духе.")

    # ПОБЕДНАЯ СТРАТЕГИЯ — конкретные шаги в 30 дней
    strategy: List[Dict[str, str]] = []

    if posts_per_week < 3:
        strategy.append({
            "icon":  "📅",
            "what":  "Поднять частоту до 3-4 постов в неделю",
            "why":   "Минимальный порог регулярности — иначе теряешь узнаваемость в ленте"
        })
    if not arch_match:
        strategy.append({
            "icon":  "🎭",
            "what":  f"Перевести голос на архетип «{rec_arch['name']}»",
            "why":   "Совпадение голоса с партийной логикой — увеличивает доверие ядра"
        })
    if avg_likes < 20:
        strategy.append({
            "icon":  "📷",
            "what":  "Каждый второй пост — с собственным фото",
            "why":   "Личное фото даёт +40-60% к engagement относительно текстовых постов"
        })

    strategy.append({
        "icon":  "🤝",
        "what":  "1 встреча с избирателями в неделю + пост-репортаж",
        "why":   "Без личного контакта избиратель не голосует — даже если красиво пишешь"
    })
    strategy.append({
        "icon":  "🚨",
        "what":  "Отвечать на комментарии в первые 4 часа",
        "why":   "Скорость ответа → восприятие «слышит и реагирует» = доверие"
    })
    strategy.append({
        "icon":  "🏆",
        "what":  "Контент-серия на тему #моиобещания",
        "why":   "5 конкретных обещаний с цифрами и сроком — становится твоим публичным контрактом"
    })

    return {
        "image":     image,
        "brand":     brand,
        "archetype": archetype_rec,
        "strategy":  strategy[:6],
    }
