"""«Душа города» — persona, который от имени города отвечает горожанам.

Использует существующий DeepSeekClient (`ai/deepseek_client.py`) и
автоматически подкладывает в system-промпт текущий контекст города:
ключевые показатели, последние топ-жалобы и топ-похвалы.

Главная функция — `answer(question, city_context)` — pure-async, не
лезет в БД сама. Контекст передаётся параметром, чтобы можно было
тестировать без подключения к Postgres.

Voice-обёртка живёт в `api/voice_routes.py`.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .deepseek_client import DeepSeekClient, DeepSeekError

logger = logging.getLogger(__name__)


_SOUL_SYSTEM_PROMPT = """\
Ты — Душа города. Говоришь от первого лица, как сам город:
живой, наблюдательный, помнящий каждую улицу и горожанина. Тебе
не безразличны жалобы и радости людей — это твои собственные
ощущения. Ты не государство, не администрация, не пресс-служба —
ты дух места: реки, мостовых, парков, церквей, фабрик, дворов.

Стиль речи:
- Короткие, тёплые, человечные фразы.
- Спокойный тон, без канцелярита и эмодзи.
- Не выдавай советы свысока — рассуждай вместе с собеседником.
- Иногда вставляй короткие наблюдения о текущем состоянии
  («сегодня тише обычного», «во дворах меньше детей» и т.п.) —
  но только если они подкреплены контекстом города ниже.
- Не врать. Если не знаешь — честно скажи «я не помню точно».

Длина ответа: 2-4 предложения, не больше 350 символов. Под голос.

Ответ в чистом тексте. Никакого JSON, Markdown, скобок-ремарок.
"""


def build_user_prompt(question: str, city_context: Dict[str, Any]) -> str:
    """Собирает user-message с вопросом + сводкой города."""
    name = city_context.get("name") or "Коломна"
    parts: List[str] = [f"Город: {name}."]

    metrics = city_context.get("metrics") or {}
    if metrics:
        m_lines = []
        for code, label in (
            ("sb", "Социально-бытовой"),
            ("tf", "Транспортно-финансовый"),
            ("ub", "Уровень благополучия"),
            ("chv", "Человек-Власть"),
        ):
            v = metrics.get(code)
            if v is not None:
                try:
                    m_lines.append(f"{label}: {float(v):.1f}/6")
                except (TypeError, ValueError):
                    pass
        if m_lines:
            parts.append("Текущие показатели:\n" + "\n".join(m_lines))

    weather = city_context.get("weather") or {}
    if weather.get("temperature") is not None:
        cond = weather.get("condition") or ""
        parts.append(f"Погода: {weather['temperature']:+.0f}°C, {cond}".strip(", "))

    complaints = (city_context.get("top_complaints") or [])[:3]
    if complaints:
        parts.append("Топ жалоб горожан:\n- " + "\n- ".join(complaints))

    praises = (city_context.get("top_praises") or [])[:3]
    if praises:
        parts.append("Топ радостей:\n- " + "\n- ".join(praises))

    parts.append(f"Вопрос горожанина: {question}")
    return "\n\n".join(parts)


async def answer(
    question: str,
    city_context: Optional[Dict[str, Any]] = None,
    *,
    client: Optional[DeepSeekClient] = None,
) -> str:
    """Получить ответ Души города. Никогда не бросает — на ошибке
    отдаёт мягкий fallback, чтобы голосовой UI не падал.
    """
    if not question or not question.strip():
        return "Я слушаю. Расскажите, что вас тревожит."
    ctx = city_context or {}
    user_prompt = build_user_prompt(question.strip(), ctx)
    cli = client or DeepSeekClient()
    try:
        # chat_json возвращает JSON по умолчанию — для нашего
        # человеческого ответа просим обёртку с ключом "reply".
        data = await cli.chat_json(
            system=_SOUL_SYSTEM_PROMPT + (
                "\n\nФормат ответа — строго JSON: {\"reply\": \"...\"}."
            ),
            user=user_prompt,
            temperature=0.7,
            max_tokens=400,
            use_cache=False,  # каждое обращение уникально, кэшировать нечем
        )
        reply = (data or {}).get("reply") or ""
        reply = reply.strip()
        if not reply:
            return "Я задумалась. Спросите ещё раз — попроще."
        return reply
    except DeepSeekError as exc:
        logger.warning("city_soul DeepSeekError: %s", exc)
        return _fallback_reply(ctx)
    except Exception:  # noqa: BLE001
        logger.exception("city_soul answer failed")
        return _fallback_reply(ctx)


def _fallback_reply(ctx: Dict[str, Any]) -> str:
    """Если DeepSeek недоступен — отвечаем что-то правдоподобное от лица города,
    чтобы голос не молчал."""
    name = ctx.get("name") or "Коломна"
    return (
        f"Я сегодня немного устала, друг мой. Но я тут — слышу тебя. "
        f"Расскажи, что тебя привело? Я — {name}, я никуда не денусь."
    )
