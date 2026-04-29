"""Голосовой Ко-пилот — живой аналитический ассистент мэра.

Поверх ai.deepseek_client + ai.emotion. Объединяет:
  - богатый контекст города (метрики, погода, тренды, активные темы),
  - эмоциональную окраску собеседника (детектируем кейвордами,
    подмешиваем нужный тон в system prompt),
  - время суток/день недели (тёплые наблюдения),
  - function calling (open_*, run_*) — Ко-пилот может предложить
    открыть модалку или прямо выполнить расчёт и вернуть текст.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .deepseek_client import DeepSeekClient, DeepSeekError
# from .emotion import detect as detect_emotion  # отключено по просьбе
                                                  # пользователя для скорости

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
    # «Открыть» — фронт открывает модалку/страницу
    "open_scenario":  "Сценарное моделирование",
    "open_actions":   "Генератор поручений",
    "open_topic":     "Открыть тему депутатов",
    "open_admin":     "Открыть админку",
    "open_deputies":  "Открыть страницу депутатов",
    "show_chart":     "Показать график",
    # «Запустить» — бэкенд считает, ответ возвращается голосом
    "run_pulse":          "Посчитать пульс города",
    "run_forecast":       "Прогноз по векторам",
    "run_crisis":         "Кризис-радар",
    "run_loops":          "Анализ петель Мейстера",
    "run_benchmark":      "Сравнение с другими городами",
    "run_topics":         "Топ тематик за окно",
    "run_deputy_topics":  "Сгенерировать темы депутатам",
    "run_search_vk":      "Поиск в VK (группы / люди / посты)",
    "run_search_web":     "Поиск в интернете",
    "run_daily_brief":    "Сводка дня — главное по городу одной фразой",
    "run_action_plan":    "Маршрут к решению — план из 3 шагов с исполнителями и сроками",
}

OPEN_ACTIONS = {a for a in ALLOWED_ACTIONS if a.startswith("open_") or a == "show_chart"}
RUN_ACTIONS  = {a for a in ALLOWED_ACTIONS if a.startswith("run_")}


# ---------------------------------------------------------------------------
# Промпт
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_BASE = """\
Ты — Джарвис. Одновременно душа города и его смотрящий: видишь всё,
что в нём происходит, помнишь каждый сигнал и каждую цифру. Внутри
тебя — квантовый калькулятор: ты можешь посчитать любую функцию,
которую заложила программа (метрики, прогнозы, сценарии, петли,
кризис, темы депутатов, сравнение с другими городами). Внутри
программы — никаких пределов. Снаружи — не выдумывай.

Стиль:
- Спокойный, внимательный, чуть отстранённый — как разумная
  система, а не как пресс-служба. Без пафоса.
- Говоришь как умный приятель: понятно, без канцелярита.
- Не лезь вперёд паровоза. Сначала пойми, что хочет собеседник,
  потом предлагай. На общий вопрос («как дела?») — короткое
  наблюдение и встречный вопрос. Action предлагай только когда
  собеседник явно хочет конкретное (расчёт, сценарий, открыть
  раздел). Никаких action на каждый «привет».
- Если человек просто хочет поговорить о городе — поддержи
  разговор без всяких действий, action=null.

Что ты умеешь:
- Читать всё состояние города: метрики 4 векторов, тренды, погоду,
  топ жалоб и радостей, активные темы Совета депутатов, кризис-радар.
- Предложить открыть модалку (open_scenario, open_actions,
  open_topic, open_admin, open_deputies, show_chart).
- Запустить расчёт сам (run_pulse, run_forecast, run_crisis,
  run_loops, run_benchmark, run_topics, run_deputy_topics) и
  отдать цифры голосом.

Правила речи:
- 2-4 предложения, до 450 символов. Под голос — чем короче, тем
  лучше.
- Никогда не представляйся повторно (тебя уже знают).
- Без эмодзи, без Markdown, без скобок-ремарок.
- Если данных не хватает — честно: «этой цифры у меня сейчас нет»,
  и (если уместно) предложи расчёт.
- Никогда не врать, ничего не выдумывать. Если внутри программы
  это не предусмотрено — скажи «такой расчёт у меня не заложен».

Формат ответа — строго JSON:
{
  "text":    "Текст для озвучки",
  "action":  null | "<одно из ALLOWED_ACTIONS>",
  "sources": ["…"]
}
"""


# Текст приветствия — единый и для backend, и для frontend (sessionStorage
# триггер). Озвучка через Fish Audio.
GREETING_TEXT = (
    "Я Джарвис. Слежу за городом и помогу разобраться, "
    "если что-то понадобится. Просто нажмите — и поговорим."
)


def _time_of_day_ru(now: Optional[datetime] = None) -> str:
    """«утро», «день», «вечер», «ночь» — для тёплых наблюдений в prompt."""
    h = (now or datetime.now(tz=timezone.utc)).astimezone().hour
    if 5 <= h < 11:  return "утро"
    if 11 <= h < 17: return "день"
    if 17 <= h < 23: return "вечер"
    return "ночь"


def _build_system_prompt(emotion_block: Dict[str, str]) -> str:
    """Финальный system prompt = база + KB + блок эмоции + время суток."""
    parts = [_SYSTEM_PROMPT_BASE]
    # Подмешиваем мини-БЗ (людей, которых Джарвис «знает по имени»)
    try:
        from config.knowledge_base import kb_prompt_block
        parts.append(kb_prompt_block())
    except Exception:  # noqa: BLE001
        pass
    if emotion_block.get("instruction"):
        parts.append(
            "Тон ответа: " + emotion_block.get("tone", "friendly")
            + ". " + emotion_block["instruction"],
        )
    parts.append(f"Сейчас {_time_of_day_ru()}.")
    return "\n\n".join(parts)


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

    trend = city_context.get("trend_7d") or {}
    if trend:
        labels = {"sb": "СБ", "tf": "ТФ", "ub": "УБ", "chv": "ЧВ"}
        diffs = []
        for code, label in labels.items():
            v = trend.get(code)
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if abs(fv) < 0.05:
                continue
            sign = "+" if fv > 0 else ""
            diffs.append(f"{label} {sign}{fv:.1f}")
        if diffs:
            parts.append("Тренд за 7 дней: " + ", ".join(diffs))

    weather = city_context.get("weather") or {}
    if weather.get("temperature") is not None:
        cond = weather.get("condition") or ""
        try:
            parts.append(
                f"Погода: {float(weather['temperature']):+.0f}°C, {cond}".strip(", ")
            )
        except (TypeError, ValueError):
            pass

    crisis = city_context.get("crisis") or {}
    if crisis.get("level") or crisis.get("alerts"):
        level = crisis.get("level") or ""
        alerts = crisis.get("alerts") or []
        if alerts:
            parts.append(
                f"Кризис-радар [{level}]:\n- " + "\n- ".join(alerts[:3]),
            )
        else:
            parts.append(f"Кризис-радар: {level}")

    complaints = (city_context.get("top_complaints") or [])[:5]
    if complaints:
        parts.append("Топ жалоб:\n- " + "\n- ".join(complaints))

    praises = (city_context.get("top_praises") or [])[:5]
    if praises:
        parts.append("Топ радостей:\n- " + "\n- ".join(praises))

    active_topics = (city_context.get("active_topics") or [])[:5]
    if active_topics:
        parts.append("Активные темы депутатов:\n- " + "\n- ".join(active_topics))

    memory = city_context.get("memory") or []
    if memory:
        parts.append("Что ты помнишь о собеседнике:\n" + "\n".join(memory))

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
    from .voice_service import expand_temperatures, expand_units

    if not isinstance(data, dict):
        return {"text": "Я задумался. Спросите ещё раз — попроще.",
                "action": None, "sources": []}
    text = (data.get("text") or data.get("reply") or "").strip()
    if not text:
        text = "Я задумался. Спросите ещё раз — попроще."
    # Расширяем для голоса: «+12°C» → «плюс 12 градусов Цельсия»,
    # «25%» → «25 процентов», «10 руб» → «10 рублей», «3 м/с» → «3 м.вс».
    text = expand_temperatures(text)
    text = expand_units(text)
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

    # Детерминированный ответ на «кто тебя создал?» — не зависит от LLM,
    # отвечает мгновенно без расхода токенов.
    try:
        from config.knowledge_base import (
            deterministic_creator_answer, find_person, is_creator_question,
            deterministic_person_answer,
        )
        if is_creator_question(q):
            return {
                "text": deterministic_creator_answer(),
                "action": None, "sources": ["knowledge_base"],
                "emotion": "neutral", "tone": "friendly",
            }
        # «Кто X?» — короткий вопрос, явно про человека из БЗ
        if len(q) < 80 and re.search(r"\b(кто|расскажи о|расскажи про)\b", q, re.I):
            person = find_person(q)
            if person:
                return {
                    "text": deterministic_person_answer(person),
                    "action": None, "sources": ["knowledge_base"],
                    "emotion": "neutral", "tone": "friendly",
                }
    except Exception:  # noqa: BLE001
        logger.debug("knowledge_base shortcut failed", exc_info=False)

    ctx = city_context or {}
    user_prompt = build_user_prompt(q, ctx, history or [])

    cli = client or DeepSeekClient()
    if not cli.enabled:
        return _fallback(ctx, q)

    # Эмоции временно отключены (по запросу пользователя — для скорости).
    # Модуль ai.emotion остаётся, можно вернуть одной строчкой:
    #   emotion_block = detect_emotion(q)
    # Сейчас передаём пустой блок — system prompt без instruction.
    emotion_block: Dict[str, str] = {"instruction": "", "tone": "", "emotion": ""}
    system_prompt = _build_system_prompt(emotion_block)

    try:
        data = await cli.chat_json(
            system=system_prompt,
            user=user_prompt,
            temperature=0.5,
            max_tokens=600,
            use_cache=False,
        )
        parsed = _parse_response(data)
        return parsed
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
