"""Route /api/copilot/chat — голосовой Ко-пилот.

Принимает текст + историю + city slug. Собирает богатый контекст
(метрики, погода, топ жалоб/радостей, активные темы депутатов,
ключевые слова → выборка из новостей за окно), отдаёт в `ai.copilot.chat`,
возвращает {text, action, sources, audio?, audio_mime?}.

Если есть Fish Audio (FISH_AUDIO_API_KEY + FISH_AUDIO_VOICE_ID) и
запрос пришёл с `speak: true` — синтезируем MP3 и кладём base64 рядом
с текстом. Фронтенд предпочитает MP3, при его отсутствии возвращается
к браузерному speechSynthesis.
"""

from __future__ import annotations

import base64
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai.copilot import chat as copilot_chat
from ai.fish_audio_service import is_configured as fish_configured, synthesize as fish_synthesize
from config.cities import get_city, get_city_by_slug

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/copilot", tags=["copilot"])


class HistoryTurn(BaseModel):
    role: str = Field(..., pattern=r"^(user|assistant)$")
    text: str = Field("", max_length=1500)


class CopilotIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=1500)
    city: str = Field("Коломна", max_length=120)
    history: List[HistoryTurn] = Field(default_factory=list, max_length=20)
    speak: bool = Field(True, description="Если есть Fish Audio — вернуть MP3 в base64")
    identity: str = Field("", max_length=80, description="UUID Джарвиса (anon ID для памяти)")


def _resolve_city_safe(name_or_slug: str) -> Dict[str, Any]:
    try:
        return get_city(name_or_slug)
    except KeyError:
        pass
    try:
        return get_city_by_slug(name_or_slug)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# Эвристика по ключевым словам — какие категории новостей подсветить
_CATEGORY_KEYWORDS = {
    "utilities":  re.compile(r"жкх|тепло|вод|свет|труб|канализ|подъезд|двор", re.I),
    "transport":  re.compile(r"транспорт|дорог|автобус|пробк|трамвай|метро", re.I),
    "healthcare": re.compile(r"поликлин|больниц|врач|медиц|здоров", re.I),
    "education":  re.compile(r"школ|детск|образован|учител|садик", re.I),
    "social":     re.compile(r"социал|пенси|пособи|инвалид|многодет|защит", re.I),
    "culture":    re.compile(r"культур|музей|театр|выставк|концерт", re.I),
    "sport":      re.compile(r"спорт|стадион|тренаж|футбол|бассейн", re.I),
}


def _interesting_categories(question: str) -> List[str]:
    out = []
    for cat, rx in _CATEGORY_KEYWORDS.items():
        if rx.search(question):
            out.append(cat)
    return out


async def _build_context(city_name: str, question: str) -> Dict[str, Any]:
    """Готовим context dict для ai.copilot.chat.

    Все источники независимы — запускаем их параллельно через
    asyncio.gather, чтобы суммарное время свелось к самому медленному.
    Раньше последовательный вариант съедал ~5-7 round-trip'ов в БД.
    """
    import asyncio

    ctx: Dict[str, Any] = {"name": city_name}

    # Сначала — единственная зависимость: city_id (нужен большинству
    # последующих запросов). Параллельно с этим запускаем crisis и
    # agenda — они идут через city_name, не нуждаются в cid.
    cid: Optional[int] = None
    cats = _interesting_categories(question)

    try:
        from db.seed import city_id_by_name
        cid = await city_id_by_name(city_name)
    except Exception:  # noqa: BLE001
        cid = None

    async def _safe(coro):
        """Вспомогательная обёртка: ловим исключение и возвращаем None."""
        try:
            return await coro
        except Exception:  # noqa: BLE001
            return None

    # Параллельные источники
    tasks: Dict[str, Any] = {}
    if cid is not None:
        try:
            from db.queries import (
                latest_metrics, latest_weather, news_window, metrics_trend_7d,
            )
            from db import deputy_queries as q
            tasks["metrics"] = _safe(latest_metrics(cid))
            tasks["weather"] = _safe(latest_weather(cid))
            tasks["trend"]   = _safe(metrics_trend_7d(cid))
            tasks["topics"]  = _safe(q.list_topics(cid, status="active", limit=5))
            if cats:
                tasks["news"] = _safe(news_window(cid, hours=168))
        except Exception:  # noqa: BLE001
            pass

    try:
        from api.routes import city_crisis, _build_agenda  # type: ignore
        tasks["crisis"] = _safe(city_crisis(city_name))
        tasks["agenda"] = _safe(_build_agenda({"name": city_name}, 0.0))
    except Exception:  # noqa: BLE001
        pass

    if tasks:
        results = await asyncio.gather(*tasks.values())
        results_map = dict(zip(tasks.keys(), results))
    else:
        results_map = {}

    # Сборка результатов
    m = results_map.get("metrics")
    if m:
        ctx["metrics"] = {
            "sb": m.get("sb"), "tf": m.get("tf"),
            "ub": m.get("ub"), "chv": m.get("chv"),
        }
    w = results_map.get("weather")
    if w:
        ctx["weather"] = {
            "temperature": w.get("temperature"),
            "condition":   w.get("condition"),
        }
    t = results_map.get("trend")
    if t:
        ctx["trend_7d"] = {
            "sb": t.get("sb"), "tf": t.get("tf"),
            "ub": t.get("ub"), "chv": t.get("chv"),
        }

    # Топ-новости по категориям-маркерам
    items = results_map.get("news") or []
    if items and cats:
        top_titles: List[str] = []
        for it in items:
            if (it.category or "").lower() in cats:
                title = (it.title or "").strip()
                if title and title not in top_titles:
                    top_titles.append(title[:140])
            if len(top_titles) >= 5:
                break
        if top_titles:
            ctx["top_complaints"] = top_titles

    # Активные темы депутатов
    topics = results_map.get("topics") or []
    if topics:
        entries: List[str] = []
        for tp in topics[:5]:
            title = tp.get("title")
            if not title:
                continue
            done = int(tp.get("completed_posts") or 0)
            req = int(tp.get("required_posts") or 0)
            if req > 0:
                entries.append(f"{title} ({done}/{req} постов)")
            else:
                entries.append(title)
        if entries:
            ctx["active_topics"] = entries

    # Кризис-радар
    crisis = results_map.get("crisis")
    if isinstance(crisis, dict):
        level = crisis.get("level") or crisis.get("status")
        alerts = crisis.get("alerts") or []
        if level or alerts:
            ctx["crisis"] = {
                "level":  level,
                "alerts": [
                    a.get("title") if isinstance(a, dict) else str(a)
                    for a in alerts[:3]
                ],
            }

    # Agenda → top_complaints (если эвристика по категории не сработала) + top_praises
    agenda_resp = results_map.get("agenda")
    if agenda_resp:
        tc = list(getattr(agenda_resp, "top_complaints", []) or [])[:5]
        tp = list(getattr(agenda_resp, "top_praises", []) or [])[:5]
        if tc and not ctx.get("top_complaints"):
            ctx["top_complaints"] = tc
        if tp:
            ctx["top_praises"] = tp

    return ctx


class ExecuteIn(BaseModel):
    action: str = Field(..., pattern=r"^run_[a-z_]+$")
    city: str = Field("Коломна", max_length=120)
    speak: bool = Field(True)


@router.post("/execute")
async def copilot_execute(payload: ExecuteIn) -> dict:
    """Прямой запуск аналитической функции по action.

    Возвращает {text, action, sources, audio?} — фронт показывает
    как обычный ответ ассистента, обернёт в bubble и озвучит.
    """
    cfg = _resolve_city_safe(payload.city)
    cid: Optional[int] = None
    try:
        from db.seed import city_id_by_name
        cid = await city_id_by_name(cfg["name"])
    except Exception:  # noqa: BLE001
        pass

    text, sources = await _execute_action(payload.action, cfg["name"], cid)

    response: Dict[str, Any] = {
        "city": cfg["name"], "text": text,
        "action": payload.action, "sources": sources,
        "tts_engine": "browser", "audio": None, "audio_mime": None,
    }
    if payload.speak and fish_configured():
        try:
            mp3 = await fish_synthesize(text)
            if mp3:
                response["audio"] = base64.b64encode(mp3).decode("ascii")
                response["audio_mime"] = "audio/mpeg"
                response["tts_engine"] = "fish"
        except Exception:  # noqa: BLE001
            logger.exception("fish_synthesize failed in /execute")
    return response


async def _execute_action(
    action: str, city_name: str, city_id: Optional[int],
    query: Optional[str] = None,
) -> tuple[str, List[str]]:
    """Pure async «функциональный switch» — каждый action возвращает
    короткий human-readable текст для голоса + список sources.
    Все ошибки заглушаются в honest fallback-сообщение.
    Returnable-тексты прогоняются через expand_temperatures + expand_units
    — «+12°C» становится «плюс 12 градусов Цельсия», «25%» → «25 процентов»."""
    from ai.voice_service import expand_temperatures, expand_units

    try:
        if action == "run_pulse":
            text, src = await _run_pulse(city_name, city_id)
        elif action == "run_forecast":
            text, src = await _run_forecast(city_name, city_id)
        elif action == "run_crisis":
            text, src = await _run_crisis(city_name)
        elif action == "run_loops":
            text, src = await _run_loops(city_name, city_id)
        elif action == "run_benchmark":
            text, src = await _run_benchmark(city_name)
        elif action == "run_topics":
            text, src = await _run_topics(city_name)
        elif action == "run_deputy_topics":
            text, src = await _run_deputy_topics(city_name, city_id)
        elif action == "run_search_vk":
            text, src = await _run_search_vk(query or city_name)
        elif action == "run_search_web":
            text, src = await _run_search_web(query or city_name)
        elif action == "run_daily_brief":
            text, src = await _run_daily_brief(city_name, city_id)
        elif action == "run_action_plan":
            text, src = await _run_action_plan(city_name, city_id, query)
        else:
            text, src = (
                f"Расчёт «{action}» у меня не заложен.",
                [],
            )
        return (expand_units(expand_temperatures(text)), src)
    except Exception:  # noqa: BLE001
        logger.exception("execute action %s failed", action)

    return (
        f"Не получилось выполнить расчёт «{action}» прямо сейчас. "
        "Попробуй переформулировать или открой соответствующий раздел дашборда.",
        [],
    )


async def _run_daily_brief(city_name: str, cid: Optional[int]) -> tuple[str, List[str]]:
    """Сводка дня — короткая фраза о состоянии города.

    Все 5 источников (пульс, метрики, кризис, темы депутатов, новости)
    запускаются параллельно через asyncio.gather — суммарное время =
    время самого медленного, а не сумма.
    """
    import asyncio

    async def _safe(coro):
        try:
            return await coro
        except Exception:  # noqa: BLE001
            return None

    tasks: Dict[str, Any] = {}
    try:
        from api.routes import city_pulse, city_crisis  # type: ignore
        tasks["pulse"]  = _safe(city_pulse(city_name))
        tasks["crisis"] = _safe(city_crisis(city_name))
    except Exception:  # noqa: BLE001
        pass

    if cid is not None:
        try:
            from db.queries import latest_metrics, news_window
            from db import deputy_queries as q
            tasks["metrics"] = _safe(latest_metrics(cid))
            tasks["topics"]  = _safe(q.list_topics(cid, status="active", limit=20))
            tasks["news"]    = _safe(news_window(cid, hours=24))
        except Exception:  # noqa: BLE001
            pass

    results = await asyncio.gather(*tasks.values()) if tasks else []
    rmap = dict(zip(tasks.keys(), results))

    bits: List[str] = []

    p = rmap.get("pulse")
    if isinstance(p, dict):
        score = p.get("score") or p.get("pulse_score")
        if score is not None:
            try:
                bits.append(f"пульс {round(float(score))} из 100")
            except Exception:  # noqa: BLE001
                pass

    m = rmap.get("metrics")
    if m:
        low_vec = []
        for code, label in (("sb", "СБ"), ("tf", "ТФ"),
                            ("ub", "УБ"), ("chv", "ЧВ")):
            v = m.get(code)
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if fv < 3.0:
                low_vec.append(f"{label} {fv:.1f}")
        if low_vec:
            bits.append("просели: " + ", ".join(low_vec))

    c = rmap.get("crisis")
    if isinstance(c, dict):
        alerts = c.get("alerts") or []
        if alerts:
            bits.append(f"кризис-алертов: {len(alerts)}")
        else:
            bits.append("кризис-радар чист")

    topics = rmap.get("topics") or []
    if topics:
        bits.append(f"у депутатов {len(topics)} активных тем")

    news = rmap.get("news") or []
    if news:
        bits.append(f"свежих новостей: {len(news)}")

    if not bits:
        return ("Сегодня по городу пока тихо — данных у меня мало.", ["daily_brief"])
    return ("Сводка дня: " + "; ".join(bits) + ".", ["daily_brief"])


async def _run_action_plan(
    city_name: str, cid: Optional[int], query: Optional[str],
) -> tuple[str, List[str]]:
    """Маршрут к решению — план из 3 шагов с исполнителями и сроками.

    Использует analytics.action_generator.ActionGenerator + текущие
    метрики/тренды/жалобы. На вход: query (из голоса/текста — например
    «как поднять УБ?»). Возвращает голосовое резюме плана.
    """
    import asyncio as _asyncio

    try:
        from analytics.action_generator import ActionGenerator
    except Exception:  # noqa: BLE001
        return ("Action-генератор сейчас недоступен.", [])

    # Параллельно подтягиваем метрики, тренды и top complaints — нужны
    # все три для создания осмысленного плана.
    async def _safe(coro):
        try:
            return await coro
        except Exception:  # noqa: BLE001
            return None

    metrics_task = None
    trend_task = None
    agenda_task = None

    if cid is not None:
        try:
            from db.queries import latest_metrics, metrics_trend_7d
            metrics_task = _safe(latest_metrics(cid))
            trend_task = _safe(metrics_trend_7d(cid))
        except Exception:  # noqa: BLE001
            pass
    try:
        from api.routes import _build_agenda  # type: ignore
        agenda_task = _safe(_build_agenda({"name": city_name}, 0.0))
    except Exception:  # noqa: BLE001
        pass

    metrics_row, trend_row, agenda_resp = await _asyncio.gather(
        metrics_task or _asyncio.sleep(0, result=None),
        trend_task   or _asyncio.sleep(0, result=None),
        agenda_task  or _asyncio.sleep(0, result=None),
    )

    # Подготовка проблем
    problems: List[str] = []
    if query:
        problems.append(query.strip())
    if agenda_resp:
        complaints = list(getattr(agenda_resp, "top_complaints", []) or [])[:3]
        for c in complaints:
            if c and c not in problems:
                problems.append(c)
    if not problems:
        # Дефолт — общий запрос на улучшение
        problems = ["Что улучшить в городе сейчас"]

    # Метрики на 0..1 шкале (action_generator ожидает unit-масштаб)
    metrics_unit: Optional[Dict[str, Optional[float]]] = None
    if metrics_row:
        def _to_unit(v):
            return None if v is None else round(float(v) / 6.0, 3)
        metrics_unit = {
            "safety":  _to_unit(metrics_row.get("sb")),
            "economy": _to_unit(metrics_row.get("tf")),
            "quality": _to_unit(metrics_row.get("ub")),
            "social":  _to_unit(metrics_row.get("chv")),
        }

    trends: Optional[Dict[str, Optional[float]]] = None
    if trend_row:
        trends = {
            "safety":  trend_row.get("sb"),
            "economy": trend_row.get("tf"),
            "quality": trend_row.get("ub"),
            "social":  trend_row.get("chv"),
        }

    # Генерация
    try:
        plan = ActionGenerator(city_name).create_daily_plan(
            problems=problems, metrics=metrics_unit, trends=trends,
        )
    except Exception:  # noqa: BLE001
        logger.exception("action_plan generation failed")
        return ("Не получилось построить маршрут к решению — попробуй позже.", [])

    # Берём топ-3 для голоса (план может содержать больше)
    top_actions = plan.actions[:3] if plan.actions else []
    if not top_actions:
        return (
            "По текущим данным конкретных шагов не вижу. Сформулируй проблему ещё раз.",
            [],
        )

    bits: List[str] = []
    for i, a in enumerate(top_actions, 1):
        responsible_role = (
            a.responsible.role if hasattr(a.responsible, "role")
            else str(a.responsible)
        )
        bits.append(
            f"Шаг {i}: {a.title}. "
            f"Ответственный — {responsible_role}, срок — {a.deadline_days} дн."
        )
    summary = " ".join(bits)
    if plan.summary:
        # plan.summary содержит эмодзи — Джарвис их не озвучивает,
        # они отфильтруются в expand_temperatures+expand_units → normalize.
        summary = f"{plan.summary}. {summary}"

    return (summary, ["action_generator"])


async def _run_search_vk(query: str) -> tuple[str, List[str]]:
    """Поиск VK: люди + группы + свежие посты. Параллельно три VK API
    вызова через asyncio.gather, потом сжимаем в одну фразу."""
    import asyncio
    from collectors.vk_discover import search_groups, search_news, search_users

    groups, users, posts = await asyncio.gather(
        search_groups(query, limit=3),
        search_users(query, limit=3),
        search_news(query, count=3),
        return_exceptions=False,
    )

    if not (groups or users or posts):
        return (f"В VK по запросу «{query}» ничего не нашёл.", ["vk"])

    parts: List[str] = [f"Поиск в VK по «{query}»:"]
    if users:
        names = ", ".join(f"{u['name']} ({u['domain']})" for u in users[:3])
        parts.append(f"Люди: {names}.")
    if groups:
        names = "; ".join(
            f"{g['name']} ({g.get('members_count') or 0} участников)"
            for g in groups[:3]
        )
        parts.append(f"Группы: {names}.")
    if posts:
        snip = "; ".join(p["text"][:80] for p in posts[:2])
        parts.append(f"Свежие посты: {snip}.")
    return (" ".join(parts), ["vk"])


async def _run_search_web(query: str) -> tuple[str, List[str]]:
    """Поиск в интернете через DuckDuckGo. Возвращает 3 топ-результата
    в одной фразе под голос."""
    from ai.web_search import search

    results = await search(query, limit=3)
    if not results:
        return (
            f"В интернете по запросу «{query}» ничего полезного не нашёл.",
            ["web"],
        )
    bits = "; ".join(
        f"{r['title']} — {r['snippet'][:120]}"
        for r in results[:3] if r.get("title")
    )
    return (f"Нашёл в интернете по «{query}»: {bits}", ["web"])


async def _run_pulse(city_name: str, cid: Optional[int]) -> tuple[str, List[str]]:
    from api.routes import city_pulse  # type: ignore
    p = await city_pulse(city_name)
    if not isinstance(p, dict):
        return ("Пульс пока не считается.", [])
    score = p.get("score") or p.get("pulse_score")
    grade = p.get("grade") or p.get("status")
    if score is None:
        return ("Пульс пока не считается — данных мало.", [])
    msg = f"Пульс города {grade or ''}: {round(float(score))} из 100.".strip()
    if p.get("breakdown"):
        bits = []
        for k, v in (p.get("breakdown") or {}).items():
            try:
                bits.append(f"{k}: {round(float(v))}")
            except Exception:  # noqa: BLE001
                pass
        if bits:
            msg += " Разбивка: " + ", ".join(bits[:4]) + "."
    return (msg, ["pulse"])


async def _run_forecast(city_name: str, cid: Optional[int]) -> tuple[str, List[str]]:
    from api.routes import city_deep_forecast  # type: ignore
    df = await city_deep_forecast(city_name)
    if not isinstance(df, dict):
        return ("Прогноз пока не готов.", [])
    texts: List[str] = []
    for vec_code in ("sb", "tf", "ub", "chv"):
        v = (df.get(vec_code) or {})
        delta_30 = v.get("delta_30") or v.get("delta_30d")
        if delta_30 is None:
            continue
        try:
            d = float(delta_30)
            label = {"sb": "СБ", "tf": "ТФ", "ub": "УБ", "chv": "ЧВ"}[vec_code]
            sign = "+" if d > 0 else ""
            texts.append(f"{label} {sign}{d:.1f} за 30 дней")
        except Exception:  # noqa: BLE001
            pass
    if not texts:
        return ("Прогноз: всё в зоне неопределённости, цифр пока мало.", [])
    return ("Прогноз на 30 дней: " + "; ".join(texts) + ".", ["deep_forecast"])


async def _run_crisis(city_name: str) -> tuple[str, List[str]]:
    from api.routes import city_crisis  # type: ignore
    c = await city_crisis(city_name)
    if not isinstance(c, dict):
        return ("Кризис-радар не сработал.", [])
    alerts = c.get("alerts") or []
    if not alerts:
        return ("Кризис-радар: всё в норме, алертов нет.", ["crisis"])
    titles = [a.get("title") if isinstance(a, dict) else str(a) for a in alerts[:3]]
    return (
        f"Кризис-радар: {len(alerts)} алертов. Топ: " + "; ".join(titles) + ".",
        ["crisis"],
    )


async def _run_loops(city_name: str, cid: Optional[int]) -> tuple[str, List[str]]:
    from tasks.scheduler import analyze_loops_for_city
    n = await analyze_loops_for_city(city_name)
    if not n:
        return ("Петель Мейстера сейчас не вижу — данных не хватает.", [])
    return (f"Распознано {n} петель Мейстера. Подробности — в админке.", ["loops"])


async def _run_benchmark(city_name: str) -> tuple[str, List[str]]:
    from api.routes import city_benchmark  # type: ignore
    try:
        b = await city_benchmark()
    except TypeError:
        b = await city_benchmark(city_name)
    if not isinstance(b, dict):
        return ("Сравнение городов не готово.", [])
    rows = b.get("rows") or b.get("cities") or []
    me = next((r for r in rows if isinstance(r, dict) and r.get("name") == city_name), None)
    if not me:
        return ("В benchmark меня пока нет.", [])
    rank = me.get("rank") or "—"
    score = me.get("score") or me.get("pulse")
    return (
        f"В сравнении из {len(rows)} городов: место {rank}, балл {score}.",
        ["benchmark"],
    )


async def _run_topics(city_name: str) -> tuple[str, List[str]]:
    from api.routes import city_topics  # type: ignore
    t = await city_topics(city_name)
    if not isinstance(t, dict):
        return ("Топ тематик пока не готов.", [])
    items = t.get("items") or t.get("topics") or []
    if not items:
        return ("За окно ничего не выделяется — день спокойный.", [])
    bits = []
    for it in items[:3]:
        if isinstance(it, dict):
            bits.append(f"{it.get('topic') or it.get('label') or ''} — {it.get('count', '?')}")
    return ("Топ тематик: " + "; ".join(bits) + ".", ["topics"])


async def _run_deputy_topics(city_name: str, cid: Optional[int]) -> tuple[str, List[str]]:
    from tasks.deputy_jobs import run_auto_generate
    if cid is None:
        return ("Город не сидирован в БД.", [])
    res = await run_auto_generate(
        city_name=city_name, city_id=cid, hours=24, deadline_days=5, dry_run=True,
    )
    cands = res.get("candidates") or []
    if not cands:
        return ("Сейчас новых тем для депутатов не предлагаю — сигналов не вижу.", [])
    titles = [c.get("title") for c in cands[:3] if c.get("title")]
    return (
        f"Готов предложить {len(cands)} тем депутатам. Топ: " + "; ".join(titles) + ".",
        ["deputy_topics"],
    )


class ForgetIn(BaseModel):
    identity: str = Field(..., min_length=1, max_length=80)


@router.post("/forget")
async def copilot_forget(payload: ForgetIn) -> dict:
    """Полная очистка долговременной памяти Джарвиса по identity.
    Вызывается с фронта при кнопке «⟳ Очистить»."""
    try:
        from db.jarvis_memory_queries import forget_all
        await forget_all(payload.identity)
    except Exception:  # noqa: BLE001
        logger.exception("forget_all failed")
    return {"ok": True}


@router.get("/alerts")
async def copilot_alerts(
    city: str = "Коломна",
    since_id: int = 0,
    limit: int = 10,
) -> dict:
    """Проактивные алерты Джарвиса. Фронт polling'ит раз в ~90s.

    Возвращает только алерты с id > since_id, чтобы не показывать
    клиенту дважды то же самое. Когда фронт получил алерты, он
    запоминает max(id) в localStorage и при следующем polling'е
    шлёт его как since_id.
    """
    cfg = _resolve_city_safe(city)
    cid: Optional[int] = None
    try:
        from db.seed import city_id_by_name
        cid = await city_id_by_name(cfg["name"])
    except Exception:  # noqa: BLE001
        pass
    if cid is None:
        return {"city": cfg["name"], "alerts": [], "max_id": int(since_id)}
    try:
        from db.jarvis_alerts_queries import list_active_for_city
        alerts = await list_active_for_city(cid, since_id=since_id, limit=limit)
    except Exception:  # noqa: BLE001
        alerts = []
    max_id = max([a["id"] for a in alerts] + [int(since_id)])
    return {"city": cfg["name"], "alerts": alerts, "max_id": max_id}


# ---------------------------------------------------------------------------
# Личная VK-страница пользователя — привязка + аудит
# ---------------------------------------------------------------------------


class VKLinkIn(BaseModel):
    identity:  str = Field(..., min_length=16, max_length=80)
    vk_handle: str = Field(..., min_length=2,  max_length=120)
    archetype: Optional[str] = Field(None, max_length=40)


class VKAuditIn(BaseModel):
    identity: str = Field(..., min_length=16, max_length=80)


@router.get("/vk/status")
async def copilot_vk_status(identity: str = "") -> dict:
    """Привязана ли VK-страница у этого identity. Возвращает
    {linked, vk_handle, vk_url, archetype, last_audit_at}."""
    if not identity or len(identity) < 16:
        return {"linked": False}
    from db.jarvis_user_vk_queries import get_link
    link = await get_link(identity)
    if link is None:
        return {"linked": False}
    return {
        "linked":        True,
        "vk_handle":     link["vk_handle"],
        "vk_url":        f"https://vk.com/{link['vk_handle']}",
        "archetype":     link.get("archetype"),
        "last_audit_at": link.get("last_audit_at"),
    }


@router.post("/vk/link")
async def copilot_vk_link(payload: VKLinkIn) -> dict:
    """Привязать VK-страницу к identity. vk_handle нормализуется —
    можно передать URL вида https://vk.com/ivanov или просто ivanov."""
    from db.jarvis_user_vk_queries import normalize_handle, upsert_link

    handle = normalize_handle(payload.vk_handle)
    if handle is None:
        raise HTTPException(
            status_code=422,
            detail="Не получилось распознать VK handle (укажи screen_name "
                   "или ссылку https://vk.com/...).",
        )
    ok = await upsert_link(
        payload.identity, handle, archetype=payload.archetype,
    )
    if not ok:
        raise HTTPException(status_code=503, detail="БД недоступна.")
    return {"ok": True, "vk_handle": handle, "vk_url": f"https://vk.com/{handle}"}


@router.post("/vk/unlink")
async def copilot_vk_unlink(payload: VKAuditIn) -> dict:
    from db.jarvis_user_vk_queries import delete_link
    ok = await delete_link(payload.identity)
    return {"ok": bool(ok)}


@router.post("/vk/audit")
async def copilot_vk_audit(payload: VKAuditIn) -> dict:
    """Запуск аудита привязанной к identity VK-страницы.

    Возвращает тот же формат что deputy audit (см. audit_vk_page).
    """
    from analytics.vk_audit import audit_vk_page
    from db.jarvis_user_vk_queries import get_link, touch_audit

    link = await get_link(payload.identity)
    if not link:
        raise HTTPException(
            status_code=404,
            detail="Сначала привяжите VK-страницу.",
        )
    out = await audit_vk_page(
        link["vk_handle"],
        name=link.get("user_label"),
        archetype_code=link.get("archetype"),
    )
    # Помечаем что аудит был — last_audit_at для UI
    await touch_audit(payload.identity)
    return out


@router.post("/vk/plan")
async def copilot_vk_plan(payload: VKAuditIn) -> dict:
    """Контент-план на неделю для привязанной VK-страницы.
    Возвращает {week_of, items[5], archetype, archetype_name}."""
    from analytics.vk_audit import plan_vk_page
    from db.jarvis_user_vk_queries import get_link

    link = await get_link(payload.identity)
    if not link:
        raise HTTPException(
            status_code=404,
            detail="Сначала привяжите VK-страницу.",
        )
    return await plan_vk_page(
        link["vk_handle"],
        name=link.get("user_label"),
        archetype_code=link.get("archetype"),
    )


@router.get("/vk/archetypes")
async def copilot_vk_archetypes() -> dict:
    """Список 12 архетипов для пикера в виджете SMM-аудита.
    Возвращает только code/name/short — UI не нужен полный voice/do/dont."""
    from config.archetypes import ARCHETYPES
    return {
        "archetypes": [
            {
                "code":  a["code"],
                "name":  a["name"],
                "short": a.get("short", ""),
            }
            for a in ARCHETYPES
        ],
    }


# ---------------------------------------------------------------------------
# Кабинет депутата — для demo-режима «вошёл как депутат → wow-первый экран»
# ---------------------------------------------------------------------------


@router.get("/deputies/list")
async def copilot_deputies_list(city: str = "Коломна") -> dict:
    """Список депутатов для второго шага role-picker'а.
    has_vk=true означает, что у депутата привязана VK-страница и можно
    запустить полноценный аудит/план в его «личном кабинете».
    """
    from config.deputies import deputies_for_city
    out = []
    for d in deputies_for_city(city):
        out.append({
            "external_id": d.get("external_id"),
            "name":        d.get("name"),
            "district":    d.get("district"),
            "sectors":     d.get("sectors") or [],
            "vk":          d.get("vk") or None,
            "has_vk":      bool(d.get("vk")),
            "note":        d.get("note") or None,
        })
    return {"city": city, "deputies": out}


@router.get("/deputy/cabinet")
async def copilot_deputy_cabinet(
    external_id: str, city: str = "Коломна", refresh: bool = False,
) -> dict:
    """Личный кабинет депутата: аудит + план + рейтинг + рекомендации.

    Кэш в БД (`deputy_audit_cache`) с TTL 12 часов. ?refresh=1 форсирует
    пересчёт. Без кэша (когда pool недоступен) — пересчитываем каждый
    раз, как раньше.
    """
    from db.deputy_audit_cache import get_cached, upsert_cache

    if not refresh:
        cached = await get_cached(external_id)
        if cached is not None:
            return cached

    payload = await _build_deputy_cabinet(external_id, city)
    await upsert_cache(external_id, payload)
    payload["_cache"] = {"computed_at": None, "fresh": False}
    return payload


async def _build_deputy_cabinet(external_id: str, city: str) -> dict:
    """Тяжёлый расчёт кабинета — выносим из роута для кэширования."""
    from analytics.deputy_content import recommend_weekly_plan
    from analytics.deputy_missions import build_weekly_missions
    from analytics.vk_audit import audit_deputy
    from analytics.vk_timing import build_timing_heatmap, heatmap_advice
    from config.archetypes import suggest_for_deputy
    from config.deputies import deputies_for_city
    from config.district_calendar import (
        relevance_for_district, upcoming_for,
    )
    from config.reply_templates import complaint_examples

    deputy = next(
        (d for d in deputies_for_city(city) if d.get("external_id") == external_id),
        None,
    )
    if not deputy:
        raise HTTPException(status_code=404, detail="Депутат не найден.")

    archetype = suggest_for_deputy(deputy)
    audit = await audit_deputy(deputy)
    plan = await recommend_weekly_plan(deputy)

    # Heatmap времени публикаций — на основе сырых постов из audit
    raw_posts = audit.pop("_raw_posts", []) or []
    timing_heatmap = build_timing_heatmap(raw_posts)
    timing_tip = heatmap_advice(timing_heatmap)

    # Поводы недели — фиксированные + город + сезонные на 14 дней вперёд
    events = upcoming_for(days=14)
    events = relevance_for_district(events, deputy.get("district"))

    # Composite rating 0..5: alignment / частота / engagement
    metrics = audit.get("metrics") or {}
    align = audit.get("alignment_score") or 0
    pp_week = float(metrics.get("posts_per_week") or 0)
    avg_likes = float(metrics.get("avg_likes") or 0)

    rating_align    = min(align / 100, 1.0)            # 0..1
    rating_freq     = min(pp_week / 3.0, 1.0)          # цель — 3 поста/неделю
    rating_engage   = min(avg_likes / 50.0, 1.0)       # 50 лайков = max
    rating_value    = round((rating_align * 0.4 + rating_freq * 0.35
                             + rating_engage * 0.25) * 5, 1)

    # Недельные миссии — derived из всего audit + timing
    missions = build_weekly_missions(
        audit, archetype,
        timing={"heatmap": timing_heatmap},
        rating_value=rating_value,
    )

    # Категории для шаблонов ответов (тексты ответов рендерятся on-demand)
    complaint_cats = complaint_examples()

    name_parts = (deputy.get("name") or "").split(" ")
    first_name = name_parts[1] if len(name_parts) > 1 else deputy.get("name")

    return {
        "deputy": {
            "external_id": deputy.get("external_id"),
            "name":        deputy.get("name"),
            "first_name":  first_name,
            "district":    deputy.get("district"),
            "sectors":     deputy.get("sectors") or [],
            "vk":          deputy.get("vk"),
            "vk_url":      f"https://vk.com/{deputy['vk']}" if deputy.get("vk") else None,
            "note":        deputy.get("note"),
        },
        "archetype": {
            "code":  archetype.get("code"),
            "name":  archetype.get("name"),
            "short": archetype.get("short"),
            "voice": archetype.get("voice"),
            "do":    archetype.get("do") or [],
            "dont":  archetype.get("dont") or [],
        },
        "audit":  audit,
        "plan":   plan,
        "rating": {
            "value":   rating_value,
            "stars":   round(rating_value),
            "factors": {
                "alignment": round(rating_align * 100),
                "frequency": round(rating_freq * 100),
                "engagement": round(rating_engage * 100),
            },
        },
        "timing": {
            "heatmap": timing_heatmap,
            "tip":     timing_tip,
        },
        "calendar":         events,
        "district_today":   _build_district_today(deputy),
        "missions":         missions,
        "reply_categories": complaint_cats,
    }


def _build_district_today(deputy: dict) -> dict:
    """Стартовая раскладка «округ сегодня»: приоритеты по секторам.
    Шаблонные кейсы — клиенту понятно, что это пример (data_kind="demo").
    Когда появится реальный pipeline комментариев / жалоб с координатами,
    заменим на data_kind="live" без изменения формы ответа.
    """
    sectors = list(deputy.get("sectors") or [])
    district = deputy.get("district") or ""

    # Шаблонные жалобы по сектору — конкретика в текстах
    sector_examples = {
        "ЖКХ":            "Жители просят проверить теплопункт — слышат стук в трубах с понедельника.",
        "благоустройство": "Двор у дома 12 — ямы 6 месяцев, фото жителей закрепили в комментариях.",
        "соцзащита":      "Многодетная семья просит помощь с местом в детском саду.",
        "здравоохранение": "Запись к участковому — очередь на 3 недели, жалоба в чате округа.",
        "молодёжь":       "Площадка для подростков заброшена, нужна инициатива.",
        "образование":    "Школа №5 — родители про охрану на входе.",
        "транспорт":      "Автобус 47 — расписание не выдерживается утром.",
        "ТКО":            "Контейнеры переполнены к понедельнику — нужен второй вывоз.",
    }
    items = []
    for s in sectors[:4]:
        text = sector_examples.get(s)
        if text:
            items.append({"sector": s, "text": text})
    return {
        "data_kind": "demo",
        "district":  district,
        "items":     items,
        "hint":      "Эти карточки — пример приоритетов по секторам округа. "
                     "Когда подключим парсер комментариев, заменим на живые жалобы.",
    }


@router.get("/greeting")
async def copilot_greeting(
    role: Optional[str] = None,
    deputy_id: Optional[str] = None,
    city: str = "Коломна",
) -> dict:
    """Короткое приветствие Джарвиса. Один раз за сессию через 10 секунд
    после загрузки. Если role=deputy и deputy_id задан — приветствие
    персональное: «Привет, Наташа! Я Джарвис, твой помощник по работе с
    округом…» + перечисление возможностей.
    """
    from ai.copilot import GREETING_TEXT

    text = GREETING_TEXT
    if role == "deputy" and deputy_id:
        text = _build_deputy_greeting(deputy_id, city) or GREETING_TEXT

    response: Dict[str, Any] = {
        "text": text,
        "tts_engine": "browser",
        "audio": None,
        "audio_mime": None,
    }
    if fish_configured():
        try:
            mp3 = await fish_synthesize(text)
            if mp3:
                response["audio"] = base64.b64encode(mp3).decode("ascii")
                response["audio_mime"] = "audio/mpeg"
                response["tts_engine"] = "fish"
        except Exception:  # noqa: BLE001
            logger.exception("greeting fish_synthesize failed")
    return response


# Сокращения формальных имён → дружеские формы для приветствия.
# Если депутата нет в маппе — берём отчество как есть, это уже
# по-человечески, но можно когда-нибудь добавить.
_DIMINUTIVES = {
    "Наталья":   "Наташа",
    "Александр": "Саша",
    "Сергей":    "Серёжа",
    "Андрей":    "Андрей",
    "Дмитрий":   "Дима",
    "Алексей":   "Алёша",
    "Михаил":    "Миша",
    "Николай":   "Коля",
    "Виктор":    "Витя",
    "Анатолий":  "Толя",
    "Игорь":     "Игорь",
    "Роман":     "Рома",
    "Валерий":   "Валера",
    "Жанна":     "Жанна",
    "Екатерина": "Катя",
    "Нина":      "Нина",
    "Наталия":   "Наташа",
    "Абдула":    "Абдула",
}


def _build_deputy_greeting(external_id: str, city: str) -> Optional[str]:
    """Собирает персональное приветствие. Имя из config.deputies."""
    from config.deputies import deputies_for_city

    deputy = next(
        (d for d in deputies_for_city(city) if d.get("external_id") == external_id),
        None,
    )
    if not deputy:
        return None
    name_parts = (deputy.get("name") or "").split(" ")
    first = name_parts[1] if len(name_parts) > 1 else (name_parts[0] if name_parts else "")
    diminutive = _DIMINUTIVES.get(first, first)
    district = deputy.get("district") or ""
    return (
        f"Привет, {diminutive}! Я Джарвис, твой помощник по работе с {district}. "
        f"Я уже посмотрел твою страницу и вижу, что можно улучшить. "
        f"Я умею: подготовить пост в твоём стиле, помочь придумать медиаповод, "
        f"показать, что просят жители твоего округа. Просто скажи, что нужно, или жми кнопки."
    )


# ---------------------------------------------------------------------------
# Контент-визард — готовый пост по шагам тип/тема/длина
# ---------------------------------------------------------------------------


class ContentGenerateIn(BaseModel):
    deputy_id:   str = Field(..., min_length=2, max_length=80)
    post_type:   str = Field(..., min_length=2, max_length=40)
    topic:       str = Field("", max_length=400)
    length:      str = Field("standard", pattern="^(short|standard|long)$")


_POST_TYPE_LABELS = {
    "story":       "история помощи",
    "thanks":      "благодарность жителям",
    "appeal":      "обращение в администрацию",
    "report":      "отчёт о решении",
    "news":        "срочная новость",
    "congrats":    "поздравление",
}

_LENGTH_HINTS = {
    "short":    "короткий — до 350 знаков, один абзац",
    "standard": "стандарт — 600-800 знаков, 2-3 абзаца",
    "long":     "лонгрид — 1200-1500 знаков, 3-4 абзаца с фактурой",
}


@router.post("/content/generate")
async def copilot_content_generate(payload: ContentGenerateIn) -> dict:
    """Готовый пост в архетипе депутата. Использует recommend_post,
    подмешивая в request_text жанр/длину/тему пользователя.
    """
    from analytics.deputy_content import recommend_post
    from config.archetypes import suggest_for_deputy
    from config.deputies import deputies_for_city

    deputy = next(
        (d for d in deputies_for_city("Коломна") if d.get("external_id") == payload.deputy_id),
        None,
    )
    if not deputy:
        raise HTTPException(status_code=404, detail="Депутат не найден.")

    archetype = suggest_for_deputy(deputy)
    type_label = _POST_TYPE_LABELS.get(payload.post_type, payload.post_type)
    length_hint = _LENGTH_HINTS.get(payload.length, _LENGTH_HINTS["standard"])
    request_text = (
        f"Напиши пост типа «{type_label}». "
        f"Тема: {payload.topic.strip() or 'на твой выбор по контексту округа'}. "
        f"Объём: {length_hint}."
    )
    result = await recommend_post(deputy, request_text)

    # Дополняем: 3 варианта заголовка + фото-задание + хэштеги
    title_seed = result.get("title") or type_label
    title_variants = [
        title_seed,
        f"{deputy.get('district') or ''}: {title_seed.lower()}".strip(": "),
        f"Что я сделала по {payload.topic.strip()[:40] or 'просьбе жителей'}",
    ]
    photo_brief = (
        "Сделай фото на месте события: ты в кадре + объект (дом, двор, "
        "ведомство). Естественный свет, без постановочного фона."
    )
    hashtags = "#Коломна #" + (deputy.get("district") or "Округ").replace(" ", "").replace("№", "")

    body = result.get("body") or archetype.get("sample_post") or ""
    cta = result.get("cta") or ""
    full_text = body
    if cta and cta.strip():
        full_text = f"{body}\n\n{cta}"

    vk_compose_url = (
        f"https://vk.com/share.php?url=&title={quote_plus(title_seed[:80])}"
        f"&description={quote_plus(full_text[:1500])}"
    )

    return {
        "title":         title_seed,
        "title_variants": [t for t in title_variants if t][:3],
        "body":          body,
        "cta":           cta,
        "full_text":     full_text,
        "photo_brief":   photo_brief,
        "hashtags":      hashtags,
        "archetype":     archetype.get("name"),
        "vk_compose_url": vk_compose_url,
        "fallback":      bool(result.get("fallback")),
    }


# ---------------------------------------------------------------------------
# Медиаповод-визард — пошаговый сценарий PR-события
# ---------------------------------------------------------------------------


class EventScenarioIn(BaseModel):
    deputy_id: str = Field(..., min_length=2, max_length=80)
    source:    str = Field(..., pattern="^(complaint|result|anniversary|joint)$")
    format:    str = Field(..., pattern="^(meeting|walkaround|live|action)$")
    topic:     str = Field("", max_length=300)


_SOURCE_LABELS = {
    "complaint":   "нерешённой жалобе жителей",
    "result":      "уже сделанной работе",
    "anniversary": "годовщине / памятной дате",
    "joint":       "совместной акции с партнёрами",
}

_FORMAT_BLUEPRINTS = {
    "meeting": {
        "label":  "встреча с жителями",
        "steps":  [
            "За 3 дня: выбери место (двор / общественное пространство), согласуй с УК / администрацией.",
            "За 1 день: обзвон актива + публикация тизера в VK с временем и точкой.",
            "День X: 60 минут вживую — короткое выступление 5 мин, затем Q&A. Видео тизер в первые 15 минут.",
            "После: пост-репортаж в тот же день вечером с 3-5 фотографиями и цитатами от жителей.",
        ],
        "media":  ["3-5 фото с разных ракурсов", "1 короткое видео 30-60 сек",
                   "Запись 1-2 цитат от жителей (можно текстом)"],
        "callto": ["Управляющая компания (вопрос ЖКХ)",
                   "Депутат-сосед по округу (для подкрепления)"],
    },
    "walkaround": {
        "label":  "обход территории",
        "steps":  [
            "За 2 дня: маршрут — 5-7 точек по жалобам, проверь актуальность.",
            "В день обхода: фото каждой точки до начала, заметки.",
            "На месте: 1 короткое видео 30 сек на каждой точке с твоим комментарием.",
            "После: пост-итог обхода в тот же вечер — карта с точками, фотодо/после-обещание.",
        ],
        "media":  ["По 1 фото на точку", "По 30 сек видео на 2-3 ключевых точках",
                   "Карта района с отметками (можно скриншот Яндекс-карт)"],
        "callto": ["ДорСервис / Благоустройство — после обхода передать список",
                   "Жители-инициаторы — пригласить, зафиксировать историю"],
    },
    "live": {
        "label":  "прямой эфир в VK",
        "steps":  [
            "За 2 дня: тема + 5 вопросов от жителей собрать в комментариях.",
            "За 1 час: тестовый прогон, проверь свет/звук, запасной интернет.",
            "Эфир 25-30 мин: 5 мин ввод, 15 мин по вопросам, 5 мин планы и обратная связь.",
            "После: запись закрепить, нарезать 2-3 коротких клипа на популярные вопросы.",
        ],
        "media":  ["Запись эфира", "2-3 клипа по 30-60 сек", "Скриншот пиков просмотров"],
        "callto": ["Партнёр-эксперт (если тема узкая) — приглашение за 2 дня"],
    },
    "action": {
        "label":  "совместная акция / открытие",
        "steps":  [
            "За 7 дней: формат + партнёры (школа / соц.центр / бизнес).",
            "За 3 дня: афиша в VK + расклейка в районе.",
            "За 1 день: пост-напоминание + сторис.",
            "День X: фото/видео процесса + интервью с участниками.",
            "После: благодарственный пост с тегами всех партнёров.",
        ],
        "media":  ["Афиша", "10+ фото", "1 видео-репортаж 60-90 сек"],
        "callto": ["Партнёрская организация", "Местные СМИ — пресс-релиз за 2 дня"],
    },
}


class ReplyRenderIn(BaseModel):
    deputy_id: str = Field(..., min_length=2, max_length=80)
    category:  str = Field(..., min_length=2, max_length=40)


@router.post("/reply/render")
async def copilot_reply_render(payload: ReplyRenderIn) -> dict:
    """Готовый ответ-шаблон в архетипе депутата на типовую жалобу.
    Категории см. config.reply_templates.complaint_examples().
    """
    from config.archetypes import suggest_for_deputy
    from config.deputies import deputies_for_city
    from config.reply_templates import render_reply

    deputy = next(
        (d for d in deputies_for_city("Коломна") if d.get("external_id") == payload.deputy_id),
        None,
    )
    if not deputy:
        raise HTTPException(status_code=404, detail="Депутат не найден.")
    archetype = suggest_for_deputy(deputy)
    text = render_reply(payload.category, archetype)
    if not text:
        raise HTTPException(status_code=422, detail="Категория жалобы не распознана.")
    return {
        "category":  payload.category,
        "archetype": archetype.get("name"),
        "text":      text,
    }


@router.post("/event/scenario")
async def copilot_event_scenario(payload: EventScenarioIn) -> dict:
    """Сценарий медиаповода. Шаблоны deterministic — собираются из
    blueprint'ов формата + текстов в архетипе депутата для тизера/
    репортажа/итога. Без LLM на старте — стабильно и быстро.
    """
    from config.archetypes import suggest_for_deputy
    from config.deputies import deputies_for_city

    deputy = next(
        (d for d in deputies_for_city("Коломна") if d.get("external_id") == payload.deputy_id),
        None,
    )
    if not deputy:
        raise HTTPException(status_code=404, detail="Депутат не найден.")
    archetype = suggest_for_deputy(deputy)
    blueprint = _FORMAT_BLUEPRINTS[payload.format]
    source_label = _SOURCE_LABELS[payload.source]
    topic = payload.topic.strip() or "(тема — на твой выбор по контексту округа)"
    voice_short = archetype.get("voice", "")[:120]

    teaser_post = (
        f"Завтра я провожу {blueprint['label']} по {source_label}: {topic}. "
        f"Время и точку публикую за 2 часа. Кому актуально — пишите в комментариях, "
        f"возьму ваши вопросы первыми."
    )
    report_post = (
        f"Сегодня прошла {blueprint['label']}. Тема: {topic}. "
        f"Что увидели и что будем делать — в постах ниже. Спасибо всем, кто пришёл и поделился."
    )
    summary_post = (
        f"По итогам {blueprint['label']} собрала список из конкретных шагов и "
        f"передала ответственным. Срок — 10 рабочих дней. Буду держать в курсе по каждой "
        f"точке. Голос «{archetype.get('name')}» — {voice_short}"
    )

    return {
        "deputy_name":   deputy.get("name"),
        "archetype":     archetype.get("name"),
        "source_label":  source_label,
        "format_label":  blueprint["label"],
        "topic":         topic,
        "steps":         blueprint["steps"],
        "media_checklist": blueprint["media"],
        "callto":        blueprint["callto"],
        "drafts": {
            "teaser":  teaser_post,
            "report":  report_post,
            "summary": summary_post,
        },
    }


@router.post("/chat")
async def copilot_chat_endpoint(payload: CopilotIn) -> dict:
    import asyncio as _asyncio

    cfg = _resolve_city_safe(payload.city)

    # Контекст города и долговременная память собираются параллельно —
    # они никак не зависят друг от друга, последовательно делать не нужно.
    async def _safe_memory():
        if not payload.identity:
            return None
        try:
            from ai.jarvis_memory import build_memory_lines
            return await build_memory_lines(payload.identity)
        except Exception:  # noqa: BLE001
            logger.exception("memory load failed")
            return None

    ctx, mem_lines = await _asyncio.gather(
        _build_context(cfg["name"], payload.message),
        _safe_memory(),
    )
    if mem_lines:
        ctx["memory"] = mem_lines

    # Многошаговое планирование: если вопрос «обзорный» — chain-of-actions.
    # Возвращаем сразу синтезированный ответ, минуя обычный chat-LLM-вызов.
    plan_used = False
    plan_info: Dict[str, Any] = {}
    try:
        from ai.jarvis_planner import is_multistep_question, run_plan
        if is_multistep_question(payload.message):
            cid: Optional[int] = None
            try:
                from db.seed import city_id_by_name
                cid = await city_id_by_name(cfg["name"])
            except Exception:  # noqa: BLE001
                pass

            async def _run(action: str) -> Dict[str, Any]:
                text, src = await _execute_action(
                    action, cfg["name"], cid, query=payload.message,
                )
                return {"text": text, "sources": src}

            plan_info = await run_plan(payload.message, _run)
            if plan_info.get("steps") and plan_info.get("summary"):
                plan_used = True
                result = {
                    "text":    plan_info["summary"],
                    "action":  None,
                    "sources": [s for r in plan_info["results"] for s in (r.get("sources") or [])],
                }
    except Exception:  # noqa: BLE001
        logger.exception("multistep planning failed")

    if not plan_used:
        history = [{"role": t.role, "text": t.text} for t in payload.history]
        result = await copilot_chat(payload.message, ctx, history)

    # Запись turn'а в память — fire-and-forget, не блокирует ответ.
    if payload.identity:
        try:
            import asyncio as _asyncio
            from ai.jarvis_memory import record_user_turn
            _asyncio.create_task(record_user_turn(payload.identity, payload.message))
        except Exception:  # noqa: BLE001
            pass

    response: Dict[str, Any] = {
        "city":    cfg["name"],
        "text":    result["text"],
        "action":  result.get("action"),
        "sources": result.get("sources") or [],
        "tts_engine": "browser",          # default fallback на speechSynthesis
        "audio":      None,
        "audio_mime": None,
        "plan":       plan_info.get("steps") if plan_used else None,
    }

    if payload.speak and fish_configured():
        try:
            mp3 = await fish_synthesize(result["text"])
            if mp3:
                response["audio"] = base64.b64encode(mp3).decode("ascii")
                response["audio_mime"] = "audio/mpeg"
                response["tts_engine"] = "fish"
        except Exception:  # noqa: BLE001
            logger.exception("fish_synthesize failed (will fallback to browser TTS)")

    return response
