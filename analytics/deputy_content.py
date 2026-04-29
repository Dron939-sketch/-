"""Контент-рекомендации и контент-план для депутатов.

Объединяет архетип депутата + текущий контекст города + запрос (тема,
проблема). Использует DeepSeek через ai.deepseek_client. На отсутствие
LLM — детерминированный fallback с шаблоном архетипа.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from ai.deepseek_client import DeepSeekClient, DeepSeekError
from config.archetypes import suggest_for_deputy

logger = logging.getLogger(__name__)


_POST_SYSTEM = """\
Ты — SMM-помощник депутата. На вход — данные депутата (имя, округ,
секторы, архетип бренда), контекст города и запрос пользователя
(проблема, событие, тема). На выход — один готовый пост в VK от лица
депутата на русском языке.

Правила:
- Тон строго в архетипе из подсказки voice/do/dont.
- 2-4 абзаца, до 800 символов.
- Без эмодзи, без хэштегов, без заглавных слов целиком.
- Без обещаний без срока. Если есть проблема — назови шаг и срок.
- Не выдумывай факты — используй только то, что в контексте.
- Не подписывай «С уважением, …» — депутат сам подпишет.

Формат ответа — строго JSON:
{
  "title":  "короткое сводное название поста (для админа, не для VK)",
  "body":   "текст поста",
  "cta":    "1-2 фразы — призыв к действию или встречный вопрос"
}
"""

_PLAN_SYSTEM = """\
Ты — SMM-стратег. Сформируй контент-план на 7 дней для депутата на
основе его архетипа и контекста города.

Правила:
- 5 постов на неделю (5 рабочих дней).
- Каждый пост — отдельный жанр в рамках архетипа: история, факт,
  обращение, репортаж, рекомендация и т.п.
- Темы — из списка городских триггеров в контексте (топ жалоб, темы
  депутатов, кризис).
- 1 пост обязательно по острой социалке (если есть проблемы), 1 — про
  результаты/благодарность жителям, остальные — на усмотрение.

Формат ответа — строго JSON:
{
  "week_of":  "YYYY-MM-DD",
  "items": [
    {"day": "пн", "topic": "...", "voice": "...", "draft": "..."},
    ...
  ]
}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def recommend_post(
    deputy: Dict[str, Any],
    request_text: str,
    city_context: Optional[Dict[str, Any]] = None,
    *,
    client: Optional[DeepSeekClient] = None,
    archetype_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Один пост по запросу. Возвращает {title, body, cta, archetype}.
    На сбой LLM — фолбэк на sample_post архетипа."""
    archetype = archetype_override or suggest_for_deputy(deputy)
    cli = client or DeepSeekClient()
    if not cli.enabled or not (request_text or "").strip():
        return _fallback_post(archetype, request_text, deputy)

    user_block = _build_user_block(deputy, archetype, request_text, city_context)
    try:
        data = await cli.chat_json(
            system=_POST_SYSTEM,
            user=user_block,
            temperature=0.65,
            max_tokens=600,
            use_cache=False,
        )
        return {
            "title":         (data or {}).get("title", "")[:200],
            "body":          (data or {}).get("body", "")[:1500],
            "cta":           (data or {}).get("cta", "")[:240],
            "archetype":     archetype.get("code"),
            "archetype_name": archetype.get("name"),
        }
    except DeepSeekError as exc:
        logger.warning("recommend_post DeepSeekError: %s", exc)
    except Exception:  # noqa: BLE001
        logger.exception("recommend_post failed")
    return _fallback_post(archetype, request_text, deputy)


async def recommend_weekly_plan(
    deputy: Dict[str, Any],
    city_context: Optional[Dict[str, Any]] = None,
    *,
    client: Optional[DeepSeekClient] = None,
    archetype_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Контент-план на неделю. Возвращает {week_of, items[5], archetype}."""
    archetype = archetype_override or suggest_for_deputy(deputy)
    cli = client or DeepSeekClient()
    week_of = _next_monday().isoformat()

    if not cli.enabled:
        return _fallback_plan(archetype, week_of, deputy, city_context)

    user_block = _build_user_block(
        deputy, archetype, request_text="Составь контент-план на неделю.",
        city_context=city_context,
    )
    try:
        data = await cli.chat_json(
            system=_PLAN_SYSTEM,
            user=user_block,
            temperature=0.6,
            max_tokens=900,
            use_cache=False,
        )
        items = (data or {}).get("items") or []
        cleaned: List[Dict[str, str]] = []
        for it in items[:5]:
            if not isinstance(it, dict):
                continue
            cleaned.append({
                "day":   str(it.get("day", ""))[:8],
                "topic": str(it.get("topic", ""))[:160],
                "voice": str(it.get("voice", ""))[:160],
                "draft": str(it.get("draft", ""))[:1000],
            })
        if cleaned:
            return {
                "week_of":         (data or {}).get("week_of") or week_of,
                "items":           cleaned,
                "archetype":       archetype.get("code"),
                "archetype_name":  archetype.get("name"),
            }
    except DeepSeekError as exc:
        logger.warning("recommend_weekly_plan DeepSeekError: %s", exc)
    except Exception:  # noqa: BLE001
        logger.exception("recommend_weekly_plan failed")

    return _fallback_plan(archetype, week_of, deputy, city_context)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_user_block(
    deputy: Dict[str, Any], archetype: Dict[str, Any],
    request_text: str, city_context: Optional[Dict[str, Any]],
) -> str:
    parts: List[str] = []
    parts.append("Депутат:")
    parts.append(f"- Имя: {deputy.get('name', '—')}")
    parts.append(f"- Округ: {deputy.get('district', '—')}")
    sectors = ", ".join(deputy.get("sectors") or [])
    parts.append(f"- Сферы: {sectors or '—'}")
    note = deputy.get("note")
    if note:
        parts.append(f"- Должность: {note}")

    parts.append("\nАрхетип бренда:")
    parts.append(f"- Код: {archetype['code']} ({archetype['name']})")
    parts.append(f"- Голос: {archetype.get('voice', '')}")
    parts.append("- Делать: " + "; ".join(archetype.get("do") or []))
    parts.append("- Не делать: " + "; ".join(archetype.get("dont") or []))

    if city_context:
        complaints = (city_context.get("top_complaints") or [])[:3]
        praises = (city_context.get("top_praises") or [])[:3]
        active = (city_context.get("active_topics") or [])[:3]
        crisis = city_context.get("crisis") or {}
        if complaints:
            parts.append("\nТоп жалоб горожан: " + "; ".join(complaints))
        if praises:
            parts.append("Топ радостей: " + "; ".join(praises))
        if active:
            parts.append("Активные темы депутатов: " + "; ".join(active))
        if crisis.get("alerts"):
            parts.append("Кризис-радар: " + "; ".join(
                a for a in crisis["alerts"] if a
            ))

    if request_text:
        parts.append(f"\nЗапрос пользователя: {request_text.strip()}")

    return "\n".join(parts)


def _fallback_post(
    archetype: Dict[str, Any], request_text: str,
    deputy: Dict[str, Any],
) -> Dict[str, Any]:
    body = archetype.get("sample_post") or ""
    return {
        "title": f"{archetype.get('name')} — образец поста",
        "body":  body,
        "cta":   "Если интересно — напишите свой вопрос в комментарии.",
        "archetype":      archetype.get("code"),
        "archetype_name": archetype.get("name"),
        "fallback":       True,
    }


def _fallback_plan(
    archetype: Dict[str, Any], week_of: str,
    deputy: Dict[str, Any], city_context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Шаблон без LLM: 5 постов с типовыми темами в духе архетипа."""
    base_themes = [
        ("пн", "История из округа: что вижу, что меняем"),
        ("вт", "Цифра недели: один факт по городу"),
        ("ср", "Прямая обратная связь: жалоба и шаг к решению"),
        ("чт", "Команда / партнёры: кто помогает в работе"),
        ("пт", "Итоги недели и планы на следующую"),
    ]
    items = []
    for day, topic in base_themes:
        items.append({
            "day":   day,
            "topic": topic,
            "voice": archetype.get("voice", ""),
            "draft": archetype.get("sample_post", "")[:300],
        })
    return {
        "week_of":        week_of,
        "items":          items,
        "archetype":      archetype.get("code"),
        "archetype_name": archetype.get("name"),
        "fallback":       True,
    }


def _next_monday() -> date:
    today = date.today()
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7)
