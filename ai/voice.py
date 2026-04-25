"""Voice of the city — one-liner status phrase for the new home screen.

Produces a single sentence (≤ 200 chars) that captures the city's current
state in plain Russian. Used by the hero zone of the new main screen as
the "WOW" element — replaces a wall of metrics with one human sentence.

Strategy:
1. Try DeepSeek if available — feeds it the pulse + crisis status + top
   complaint + weather, asks for ONE sentence.
2. Fallback to a rules-based generator that picks a template based on the
   pulse band + crisis status. Always produces a meaningful sentence so
   the hero never reads "—".

Fail-safe end-to-end: any exception → rules-based fallback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .deepseek_client import DeepSeekClient, DeepSeekError

logger = logging.getLogger(__name__)


_SYSTEM = """Ты — деловой советник мэра города. По текущему состоянию города
напиши ровно одно предложение (до 200 символов) на русском языке, которое
точно описывает ситуацию и тон дня. Без канцелярита, без обещаний, без
оценочных эпитетов. Если есть конкретный риск — упомяни район или сферу.

Отвечаешь строго одним JSON-объектом: {"phrase": "..."}, без другого текста.
""".strip()


_USER_TEMPLATE = """Город: {city}
Пульс города (0-100): {pulse} ({pulse_label})
Кризисный статус: {crisis}
Главная жалоба за сутки: {complaint}
Главная похвала за сутки: {praise}
Погода: {weather}

Напиши ровно одно предложение (до 200 символов).""".strip()


@dataclass
class CityVoice:
    phrase: str
    source: str   # "ai" | "rules"

    def to_dict(self) -> Dict[str, Any]:
        return {"phrase": self.phrase, "source": self.source}


def _rules_phrase(
    *,
    city: str,
    pulse: Optional[float],
    crisis: Optional[str],
    complaint: Optional[str],
    praise: Optional[str],
) -> str:
    """Deterministic fallback when DeepSeek is unavailable.

    Picks a template based on (crisis_status, pulse_band). Always returns
    a sentence — never empty. Uses pluralisation-safe wording.
    """
    pulse_val = float(pulse) if pulse is not None else 50.0
    band = (
        "high" if pulse_val >= 70
        else "mid" if pulse_val >= 50
        else "low" if pulse_val >= 30
        else "very_low"
    )

    crisis = (crisis or "ok").lower()

    if crisis == "attention":
        if complaint:
            return f"Внимание: {complaint.strip().lower()} — требуется ваше решение сегодня."
        return f"Кризисный сигнал требует вашего решения сегодня."

    if crisis == "watch":
        return f"Город под наблюдением: накапливаются сигналы, стоит проверить ключевые показатели."

    # crisis == "ok"
    if band == "high":
        if praise:
            return f"Город в хорошей форме — заметно выделяется: {praise.strip().lower()}."
        return f"Город в хорошей форме — спокойный день для стратегических решений."
    if band == "mid":
        return f"В целом стабильно. Если есть жалобы — они в фоне, не в авангарде."
    if band == "low":
        if complaint:
            return f"Фон чуть тревожный: {complaint.strip().lower()}. Без острого кризиса, но стоит держать руку на пульсе."
        return f"Фон чуть тревожный — без острого кризиса, но стоит держать руку на пульсе."
    return f"Несколько слабых мест одновременно. Кризиса нет, но день требует внимания."


def _crisis_label(status: Optional[str]) -> str:
    return {
        "attention": "требует внимания",
        "watch": "под наблюдением",
        "ok": "спокойно",
    }.get((status or "ok").lower(), "спокойно")


def _pulse_label(pulse: Optional[float]) -> str:
    if pulse is None:
        return "нет данных"
    p = float(pulse)
    if p >= 70:
        return "высокий"
    if p >= 50:
        return "средний"
    if p >= 30:
        return "пониженный"
    return "низкий"


async def generate(
    *,
    city: str,
    pulse: Optional[float] = None,
    crisis_status: Optional[str] = None,
    top_complaint: Optional[str] = None,
    top_praise: Optional[str] = None,
    weather: Optional[str] = None,
    client: Optional[DeepSeekClient] = None,
) -> CityVoice:
    """Generate one phrase that captures the city's current mood."""
    cli = client or DeepSeekClient()

    if cli.enabled:
        prompt = _USER_TEMPLATE.format(
            city=city,
            pulse=int(pulse) if pulse is not None else "—",
            pulse_label=_pulse_label(pulse),
            crisis=_crisis_label(crisis_status),
            complaint=(top_complaint or "—").strip()[:160],
            praise=(top_praise or "—").strip()[:160],
            weather=(weather or "—").strip()[:120],
        )
        try:
            data = await cli.chat_json(_SYSTEM, prompt)
            if isinstance(data, dict):
                phrase = str(data.get("phrase") or "").strip()
                if phrase:
                    return CityVoice(phrase=phrase[:240], source="ai")
        except DeepSeekError as exc:
            logger.info("voice: DeepSeek unavailable (%s) — falling back to rules", exc)
        except Exception:  # noqa: BLE001
            logger.warning("voice: unexpected DeepSeek failure — using rules", exc_info=False)

    return CityVoice(
        phrase=_rules_phrase(
            city=city, pulse=pulse, crisis=crisis_status,
            complaint=top_complaint, praise=top_praise,
        ),
        source="rules",
    )
