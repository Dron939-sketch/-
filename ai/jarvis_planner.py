"""Многошаговый планировщик Джарвиса (шаг 3 к агенту).

Идея: на «обзорный» вопрос пользователя («что не так в городе?»,
«как поднять УБ?», «дай полный анализ») Джарвис составляет план из
1-3 действий, исполняет их последовательно через существующие
run_*-функции, потом одним финальным LLM-вызовом синтезирует короткое
резюме под голос.

Безопасность:
  - max 3 шага (whitelisted из ALLOWED_ACTIONS)
  - дубли убираются
  - timeout на весь план
  - всё fail-safe — если LLM не выдал валидный план, возвращаем пустой
    список (route отдаёт обычный chat-ответ)
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .copilot import RUN_ACTIONS
from .deepseek_client import DeepSeekClient, DeepSeekError

logger = logging.getLogger(__name__)


MAX_STEPS = 3
PLAN_TIMEOUT_S = 25


_PLAN_SYSTEM = """\
Ты — планировщик Джарвиса. На «обзорный» вопрос пользователя ты
выбираешь 1-3 функции из white-list, которые нужно выполнить, чтобы
дать осмысленный ответ. Если вопрос узкий и одна функция уже отвечает
— возвращай 1 шаг. Если вопрос про «общее состояние», «полный анализ»
— до 3 шагов. Если на вопрос вообще не нужны функции (просто ответ
текстом) — возвращай пустой список steps.

Доступные функции:
  run_pulse          — текущий пульс города (0..100 + breakdown)
  run_forecast       — прогноз на 30 дней по 4 векторам
  run_crisis         — кризис-радар, активные алерты
  run_loops          — анализ петель Мейстера
  run_benchmark      — сравнение с другими городами
  run_topics         — топ тематик за окно
  run_deputy_topics  — генерация тем депутатам
  run_search_vk      — поиск в VK (люди / группы / свежие посты)
  run_search_web     — поиск в интернете (DuckDuckGo)
  run_daily_brief    — короткая сводка дня (пульс + векторы + кризис +
                       темы депутатов + свежие новости одной фразой)
  run_action_plan    — маршрут к решению: 3 шага с исполнителями и
                       сроками (нужно при «как поднять / что делать /
                       дай план / маршрут к решению»)

Если вопрос содержит «найди / поищи / в вк / в интернете / погугли /
кто такой» — почти всегда нужны run_search_vk или run_search_web.

«Что сегодня важно», «коротко главное», «сводка дня» —
run_daily_brief (один шаг достаточно).

«Как поднять УБ», «что делать с дорогами», «дай план / маршрут» —
run_action_plan (один шаг достаточно).

Формат ответа — строго JSON:
{"steps": ["run_search_vk"]}
"""


_SYNTH_SYSTEM = """\
Ты — Джарвис. Тебе передали 1-3 результата выполненных функций
(пульс, прогноз, кризис и т.д.). Сформулируй ОДИН короткий ответ
для голоса, который связывает результаты в цельную картину.

Правила:
- 2-4 предложения, до 450 символов.
- Без эмодзи, без Markdown, без JSON — чистый текст.
- Перечисляй главное, не дублируй цифры из каждого шага дословно.
- Если результаты противоречат — скажи об этом честно.
- Заканчивай рекомендацией или встречным вопросом.
"""


# Эвристика: какой запрос «обзорный» и стоит планировать chain.
_MULTISTEP_TRIGGERS = re.compile(
    r"\b(полный анализ|общая картина|расскажи|что не так|как поднять|"
    r"что у нас|общее состояние|сделай обзор|полный отчёт|общий отчет|"
    r"что тревожит|сводку|где беда|где проблема|"
    r"найди|поищи|погугли|в вк|в интернете|кто такой|кто это|"
    r"сводк|коротко главное|что сегодня важно|что важного|"
    r"что делать|дай план|маршрут|план действий|план к решению)",
    re.IGNORECASE | re.UNICODE,
)


def is_multistep_question(question: str) -> bool:
    """Грубая эвристика — стоит ли вообще привлекать planner. Без неё
    каждый «привет» уходил бы в chain."""
    if not question or len(question) < 10:
        return False
    return bool(_MULTISTEP_TRIGGERS.search(question))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def plan_steps(
    question: str, *, client: Optional[DeepSeekClient] = None,
) -> List[str]:
    """LLM-планировщик. Возвращает список валидных run_*-action'ов
    (≤MAX_STEPS, без дублей). На любую ошибку/невалидный ответ → []."""
    cli = client or DeepSeekClient()
    if not cli.enabled:
        return []
    try:
        data = await cli.chat_json(
            system=_PLAN_SYSTEM,
            user=f"Вопрос пользователя: {question.strip()}\n\nВыбери шаги.",
            temperature=0.2, max_tokens=200, use_cache=False,
        )
        raw = (data or {}).get("steps") or []
        if not isinstance(raw, list):
            return []
        out: List[str] = []
        for item in raw:
            if not isinstance(item, str):
                continue
            step = item.strip()
            if step in RUN_ACTIONS and step not in out:
                out.append(step)
            if len(out) >= MAX_STEPS:
                break
        return out
    except DeepSeekError as exc:
        logger.warning("plan_steps DeepSeekError: %s", exc)
        return []
    except Exception:  # noqa: BLE001
        logger.exception("plan_steps failed")
        return []


async def synthesize(
    question: str,
    step_results: List[Dict[str, Any]],
    *,
    client: Optional[DeepSeekClient] = None,
) -> str:
    """Финальный текст-резюме после исполнения шагов.

    step_results — [{step, text, sources}]. Если LLM упал — собираем
    наивный fallback: «Вот что я выяснил: <step1.text>; <step2.text>».
    """
    cli = client or DeepSeekClient()
    if not cli.enabled or not step_results:
        return _fallback_synth(step_results)

    payload_lines = []
    for r in step_results:
        payload_lines.append(f"[{r.get('step')}] {r.get('text', '')}")
    user_block = (
        f"Вопрос: {question.strip()}\n\n"
        f"Результаты функций:\n" + "\n".join(payload_lines)
    )
    try:
        data = await cli.chat_json(
            system=_SYNTH_SYSTEM
            + "\n\nФормат: {\"text\": \"...\"}",
            user=user_block,
            temperature=0.5, max_tokens=400, use_cache=False,
        )
        text = (data or {}).get("text") or ""
        text = text.strip()
        if text:
            return text[:1200]
    except DeepSeekError:
        pass
    except Exception:  # noqa: BLE001
        logger.exception("synthesize failed")
    return _fallback_synth(step_results)


def _fallback_synth(step_results: List[Dict[str, Any]]) -> str:
    if not step_results:
        return "Я ничего не выяснил."
    bits = [r.get("text", "") for r in step_results if r.get("text")]
    return "Вот что я выяснил: " + " ".join(bits)[:600]


async def run_plan(
    question: str,
    executor: Callable[[str], Awaitable[Dict[str, Any]]],
    *,
    client: Optional[DeepSeekClient] = None,
) -> Dict[str, Any]:
    """Полный цикл: планируем → исполняем → синтезируем.

    `executor(action)` — async функция, исполняющая run_*-action и
    возвращающая {"text": ..., "sources": [...]}. Передаётся снаружи
    (из api/copilot_routes.py), чтобы не тащить router-зависимости
    внутрь pure-модуля.
    """
    steps = await plan_steps(question, client=client)
    if not steps:
        return {"steps": [], "results": [], "summary": ""}

    results: List[Dict[str, Any]] = []
    try:
        async with asyncio.timeout(PLAN_TIMEOUT_S):  # py3.11+
            # Параллелим выполнение шагов — каждый шаг независим, нет
            # cross-dependency между run_*-actions. Время плана = время
            # самого медленного шага, а не сумма.
            outs = await asyncio.gather(
                *(executor(step) for step in steps),
                return_exceptions=True,
            )
            for step, out in zip(steps, outs):
                if isinstance(out, Exception):
                    logger.exception("plan step %s failed", step, exc_info=out)
                    results.append({"step": step, "text": "", "sources": []})
                else:
                    results.append({
                        "step":    step,
                        "text":    (out or {}).get("text", ""),
                        "sources": (out or {}).get("sources", []),
                    })
    except asyncio.TimeoutError:
        logger.warning("run_plan timeout")

    summary = await synthesize(question, results, client=client)
    return {"steps": steps, "results": results, "summary": summary}
