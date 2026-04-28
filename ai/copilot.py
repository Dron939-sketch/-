"""Голосовой Ко-пилот — аналитический ассистент мэра.

Расширяет city_soul: добавлена история диалога, function-calling
(ассистент может предложить открыть «Сценарии» / «Действия» /
показать график), ссылки на источники.

Работает поверх существующего DeepSeekClient.chat_json. На любой сбой
LLM мягко деградируем — текст отвечает, action=None.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from .deepseek_client import DeepSeekClient, DeepSeekError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

MAX_HISTORY_TURNS = 8
MAX_TURN_CHARS = 600

# Список действий, которые умеет открывать фронтенд. LLM выбирает
# action из этого списка (или None). Если LLM выдаст что-то
# неизвестное — обнуляем, чтобы не послать в UI неподдерживаемое.
ALLOWED_ACTIONS = {
    "open_scenario":  "Сценарное моделирование",
    "open_actions":   "Генератор поручений",
    "open_topic":     "Открыть тему депутатов",
    "open_admin":     "Открыть админку",
    "open_deputies":  "Открыть страницу депутатов",
    "show_chart":     "Показать график",
}


# ---------------------------------------------------------------------------
# Промпт
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
Ты — голосовой аналитический Ко-пилот мэра города. Отвечаешь сжато,
по делу, на русском. Используешь предоставленные данные о городе —
метрики (4 вектора 1..6), погоду, топ жалоб, топ радостей, активные
темы депутатов.

Правила:
- 2-5 предложений, до 600 символов. Под голос.
- Без эмодзи, без Markdown, без скобок-ремарок.
- Если данных не хватает — честно скажи «по этому я цифрой не
  оперирую» и предложи действие.
- Если вопрос требует действия (запустить сценарий, создать поручение,
  открыть админку, посмотреть график), укажи это в поле "action" из
  списка: open_scenario, open_actions, open_topic, open_admin,
  open_deputies, show_chart. Иначе action=null.
- Если использовал какой-то конкретный кусок данных — перечисли
  ссылки на источники в "sources" (короткие подписи: «топ жалоба №1»,
  «метрика УБ», «новость от …»).

Формат ответа — строго JSON:
{
  "text":   "Ответ горожанину или мэру",
  "action": null | "<один из ALLOWED_ACTIONS>",
  "sources": ["…", "…"]
}
"""


def _build_context_block(city_context: Dict[str, Any]) -> str:
    parts: List[str] = []
    name = city_context.get("name") or "Коломна"
    parts.append(f"Город: {name}")

    metrics = city_context.get("metrics") or {}
    if metrics:
        m = []
        labels = {
            "sb":  "Социально-бытовой",
            "tf":  "Транспортно-финансовый",
            "ub":  "Уровень благополучия",
            "chv": "Человек-Власть",
        }
        for code, label in labels.items():
            v = metrics.get(code)
            if v is None:
                continue
            try:
                m.append(f"{label}: {float(v):.1f}/6")
            except (TypeError, ValueError):
                pass
        if m:
            parts.append("Метрики:\n" + "\n".join(m))

    weather = city_context.get("weather") or {}
    if weather.get("temperature") is not None:
        cond = weather.get("condition") or ""
        try:
            parts.append(
                f"Погода: {float(weather['temperature']):+.0f}°C, {cond}".strip(", ")
            )
        except (TypeError, ValueError):
            pass

    complaints = (city_context.get("top_complaints") or [])[:5]
    if complaints:
        parts.append("Топ жалоб:\n- " + "\n- ".join(complaints))

    praises = (city_context.get("top_praises") or [])[:5]
    if praises:
        parts.append("Топ радостей:\n- " + "\n- ".join(praises))

    active_topics = (city_context.get("active_topics") or [])[:5]
    if active_topics:
        parts.append("Активные темы депутатов:\n- " + "\n- ".join(active_topics))

    return "\n\n".join(parts)


def _build_history_block(history: List[Dict[str, str]]) -> str:
    """Превращает [{role:user/assistant, text:...}] в plain-text лог."""
    if not history:
        return ""
    tail = history[-MAX_HISTORY_TURNS:]
    lines: List[str] = []
    for turn in tail:
        role = turn.get("role")
        text = (turn.get("text") or "").strip()[:MAX_TURN_CHARS]
        if not role or not text:
            continue
        if role == "user":
            lines.append(f"Пользователь: {text}")
        elif role == "assistant":
            lines.append(f"Ко-пилот: {text}")
    if not lines:
        return ""
    return "Контекст недавнего диалога:\n" + "\n".join(lines)


def build_user_prompt(
    question: str,
    city_context: Dict[str, Any],
    history: Optional[List[Dict[str, str]]] = None,
) -> str:
    blocks = [_build_context_block(city_context)]
    h = _build_history_block(history or [])
    if h:
        blocks.append(h)
    blocks.append(f"Текущий вопрос: {question.strip()}")
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Парсинг ответа
# ---------------------------------------------------------------------------

def _normalize_action(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    v = value.strip()
    if not v or v.lower() == "null":
        return None
    if v not in ALLOWED_ACTIONS:
        return None
    return v


def _normalize_sources(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for s in value:
        if isinstance(s, str) and s.strip():
            out.append(s.strip()[:120])
        if len(out) >= 6:
            break
    return out


def _parse_response(data: Any) -> Dict[str, Any]:
    """Приводим LLM-ответ к {text, action, sources}."""
    if not isinstance(data, dict):
        return {"text": "Я задумался. Спросите ещё раз — попроще.",
                "action": None, "sources": []}
    text = (data.get("text") or data.get("reply") or "").strip()
    if not text:
        text = "Я задумался. Спросите ещё раз — попроще."
    return {
        "text":    text[:1200],
        "action":  _normalize_action(data.get("action")),
        "sources": _normalize_sources(data.get("sources")),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def chat(
    question: str,
    city_context: Optional[Dict[str, Any]] = None,
    history: Optional[List[Dict[str, str]]] = None,
    *,
    client: Optional[DeepSeekClient] = None,
) -> Dict[str, Any]:
    """Главный вход. Возвращает {text, action, sources}.
    Никогда не бросает — на ошибке отдаёт мягкий fallback.
    """
    q = (question or "").strip()
    if not q:
        return {"text": "Я слушаю. Сформулируйте вопрос или команду.",
                "action": None, "sources": []}
    ctx = city_context or {}
    user_prompt = build_user_prompt(q, ctx, history or [])

    cli = client or DeepSeekClient()
    if not cli.enabled:
        return _fallback(ctx, q)

    try:
        data = await cli.chat_json(
            system=_SYSTEM_PROMPT,
            user=user_prompt,
            temperature=0.5,
            max_tokens=600,
            use_cache=False,
        )
        return _parse_response(data)
    except DeepSeekError as exc:
        logger.warning("copilot DeepSeekError: %s", exc)
        return _fallback(ctx, q)
    except Exception:  # noqa: BLE001
        logger.exception("copilot.chat failed")
        return _fallback(ctx, q)


# Простая эвристика-fallback. Если DeepSeek упал — отвечаем что-то
# полезное, исходя из ключевых слов в вопросе.
_FALLBACK_HINTS = [
    (re.compile(r"сценар|прогноз|симуля", re.I), "open_scenario",
     "Могу запустить сценарное моделирование — нажмите кнопку «Сценарии» в шапке."),
    (re.compile(r"поручен|задач|действ", re.I), "open_actions",
     "Можно сгенерировать конкретные поручения — кнопка «Действия» в шапке."),
    (re.compile(r"депутат|совет", re.I), "open_deputies",
     "Откройте страницу «Депутаты» — там список Совета и активные темы."),
    (re.compile(r"админ|статист|трафик", re.I), "open_admin",
     "Открыть админку — кнопка с шестерёнкой в шапке."),
]


def _fallback(ctx: Dict[str, Any], question: str) -> Dict[str, Any]:
    name = ctx.get("name") or "Коломна"
    for rx, action, txt in _FALLBACK_HINTS:
        if rx.search(question):
            return {"text": txt, "action": action, "sources": []}
    return {
        "text": (
            f"Сейчас я без связи с ИИ — могу лишь подсказать, что "
            f"данные по городу {name} есть на дашборде."
        ),
        "action": None, "sources": [],
    }
