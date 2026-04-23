"""Narrative engineering (ТЗ §17) — AI statement generator.

Given a topic + short situational context, asks DeepSeek to produce
three statement variants the mayor can use as starting drafts:

    formal      — для пресс-релизов и официальных каналов
    empathetic  — для ВК/Telegram: человеческий тон, «мы слышим вас»
    mobilizing  — призыв к действию, фокус на «что делаем»

Fully fail-safe: no DeepSeek key → disabled report; API error / bad
JSON → returns the skeleton with an error note so the UI can render
a helpful message. Reuses the same DeepSeekClient instance from
the enricher layer via the NewsEnricher helper convention.

The legacy `narrative_engineering.py` ships campaign planning + channel
orchestration + budget allocation (§17 full scope). Those are out of
scope for an MVP — the mayor's most common ask is "дай мне черновик
заявления на сейчас", and that's what this module delivers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .deepseek_client import DeepSeekClient, DeepSeekError

logger = logging.getLogger(__name__)


_TONES = [
    {"key": "formal",
     "label": "Официальный",
     "description": "Для пресс-релизов и сайта администрации. Сухо, по делу, без эмоций."},
    {"key": "empathetic",
     "label": "Эмпатичный",
     "description": "Для ВК / Telegram. Человеческий тон: «мы слышим, мы понимаем, мы с вами»."},
    {"key": "mobilizing",
     "label": "Мобилизующий",
     "description": "Прямой призыв к действию. Фокус на «что делаем» и на активной позиции."},
]


_SYSTEM = """Ты — опытный PR-советник мэра города.
По заданной теме пишешь черновики публичных заявлений в трёх регистрах:
официальный, эмпатичный, мобилизующий. Пишешь по-русски, живо, без
канцелярита. Без обещаний, которые нельзя подкрепить фактами из
контекста. Без имён других политиков. Каждый вариант — 2-4 предложения.

Отвечаешь строго одним JSON-объектом, без какого-либо другого текста.
""".strip()


_USER_TEMPLATE = """Город: {city}
Тема: {topic}
Контекст (что произошло / что волнует): {context}

Сгенерируй три варианта заявления:

1) «formal» — официальный, суховатый, для пресс-релиза или сайта.
2) «empathetic» — эмпатичный, для социальных сетей, признать проблемы жителей.
3) «mobilizing» — призыв к действию, сфокусированный на «что мы делаем сейчас».

Формат ответа:
{{"variants": [
  {{"tone": "formal",     "text": "..."}},
  {{"tone": "empathetic", "text": "..."}},
  {{"tone": "mobilizing", "text": "..."}}
]}}
""".strip()


@dataclass
class Variant:
    tone: str
    label: str
    description: str
    text: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tone": self.tone,
            "label": self.label,
            "description": self.description,
            "text": self.text,
            "length_chars": len(self.text),
        }


@dataclass
class NarrativeSet:
    city: str
    topic: str
    context: str
    variants: List[Variant] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "city": self.city,
            "topic": self.topic,
            "context": self.context,
            "variants": [v.to_dict() for v in self.variants],
            "error": self.error,
        }


async def generate(
    city: str,
    topic: str,
    context: str = "",
    *,
    client: Optional[DeepSeekClient] = None,
) -> NarrativeSet:
    """Generate 3 statement variants. Returns a NarrativeSet with .error set
    instead of raising when DeepSeek is unavailable / fails."""
    topic = (topic or "").strip()
    context = (context or "").strip()
    if not topic:
        return NarrativeSet(city=city, topic="", context=context,
                            error="Тема не задана.")

    cli = client or DeepSeekClient()
    if not cli.enabled:
        return NarrativeSet(city=city, topic=topic, context=context,
                            error="DeepSeek отключён — заявки не генерируются.")

    user_prompt = _USER_TEMPLATE.format(
        city=city, topic=topic, context=context or "(контекст не указан)",
    )
    try:
        data = await cli.chat_json(_SYSTEM, user_prompt)
    except DeepSeekError as exc:
        logger.warning("narratives: DeepSeek failed (%s)", exc)
        return NarrativeSet(city=city, topic=topic, context=context,
                            error=f"DeepSeek недоступен: {exc}")

    return _build_variants(city=city, topic=topic, context=context, data=data)


def _build_variants(
    city: str, topic: str, context: str, data: Any,
) -> NarrativeSet:
    variants_out: List[Variant] = []
    raw_variants: List[Dict[str, Any]] = []
    if isinstance(data, dict):
        raw = data.get("variants") or []
        if isinstance(raw, list):
            raw_variants = [v for v in raw if isinstance(v, dict)]

    # Index by tone so we can fall back gracefully if the LLM returns them
    # out of order or drops one.
    by_tone: Dict[str, str] = {}
    for v in raw_variants:
        tone = str(v.get("tone") or "").strip().lower()
        text = str(v.get("text") or "").strip()
        if tone and text and tone not in by_tone:
            by_tone[tone] = text

    for meta in _TONES:
        text = by_tone.get(meta["key"], "")
        variants_out.append(
            Variant(
                tone=meta["key"],
                label=meta["label"],
                description=meta["description"],
                text=text,
            )
        )

    filled = sum(1 for v in variants_out if v.text)
    error = None
    if filled == 0:
        error = "DeepSeek вернул пустой ответ — попробуйте ещё раз."
    return NarrativeSet(
        city=city, topic=topic, context=context,
        variants=variants_out, error=error,
    )
