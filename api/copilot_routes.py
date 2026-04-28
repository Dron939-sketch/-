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
    """Готовим context dict для ai.copilot.chat. Все источники fail-safe."""
    ctx: Dict[str, Any] = {"name": city_name}
    cid: Optional[int] = None
    try:
        from db.queries import (
            latest_metrics, latest_weather, news_window, metrics_trend_7d,
        )
        from db.seed import city_id_by_name

        cid = await city_id_by_name(city_name)
        if cid is not None:
            m = await latest_metrics(cid)
            if m:
                ctx["metrics"] = {
                    "sb": m.get("sb"), "tf": m.get("tf"),
                    "ub": m.get("ub"), "chv": m.get("chv"),
                }
            w = await latest_weather(cid)
            if w:
                ctx["weather"] = {
                    "temperature": w.get("temperature"),
                    "condition":   w.get("condition"),
                }

            # Тренды за неделю — Ко-пилот может говорить «на этой неделе УБ
            # подрос», что делает его «живым».
            try:
                t = await metrics_trend_7d(cid)
                if t:
                    ctx["trend_7d"] = {
                        "sb": t.get("sb"), "tf": t.get("tf"),
                        "ub": t.get("ub"), "chv": t.get("chv"),
                    }
            except Exception:  # noqa: BLE001
                pass

            # Если в вопросе упоминается категория — поднимаем top-news
            # из неё за последнюю неделю как источник.
            cats = _interesting_categories(question)
            if cats:
                items = await news_window(cid, hours=168)
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
    except Exception:  # noqa: BLE001
        pass

    # Активные темы депутатов с прогрессом — Ко-пилот видит, что закрывается.
    if cid is not None:
        try:
            from db import deputy_queries as q
            topics = await q.list_topics(cid, status="active", limit=5)
            entries = []
            for t in (topics or [])[:5]:
                title = t.get("title")
                if not title:
                    continue
                done = int(t.get("completed_posts") or 0)
                req  = int(t.get("required_posts") or 0)
                if req > 0:
                    entries.append(f"{title} ({done}/{req} постов)")
                else:
                    entries.append(title)
            if entries:
                ctx["active_topics"] = entries
        except Exception:  # noqa: BLE001
            pass

    # Снимок кризис-радара — если есть. Не зависит от cid (ползёт
    # через city_name и pure-analytics).
    try:
        from api.routes import city_crisis  # type: ignore
        crisis = await city_crisis(city_name)
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
    except Exception:  # noqa: BLE001
        pass

    # Пробуем ещё агрегированную повестку (top complaints/praises) — она
    # уже отфильтрована и валидирована.
    try:
        from api.routes import _build_agenda  # type: ignore
        agenda_resp = await _build_agenda({"name": city_name}, 0.0)
        if agenda_resp:
            tc = list(getattr(agenda_resp, "top_complaints", []) or [])[:5]
            tp = list(getattr(agenda_resp, "top_praises", []) or [])[:5]
            # Если по эвристике уже что-то нашли — оставим, иначе
            # возьмём из agenda.
            if tc and not ctx.get("top_complaints"):
                ctx["top_complaints"] = tc
            if tp:
                ctx["top_praises"] = tp
    except Exception:  # noqa: BLE001
        pass

    # Активные темы депутатов — по 5 самых ближайших по сроку.
    try:
        from db import deputy_queries as q
        from db.seed import city_id_by_name as _cid

        cid = await _cid(city_name)
        if cid is not None:
            topics = await q.list_topics(cid, status="active", limit=5)
            titles = [t.get("title") for t in (topics or []) if t.get("title")]
            if titles:
                ctx["active_topics"] = titles
    except Exception:  # noqa: BLE001
        pass

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
    """Сводка дня — короткая фраза о состоянии города. Собирает:
    пульс, текущие 4 вектора, кризис-радар (count алертов), активные
    темы депутатов, новости за сутки. Всё в одну голосовую фразу."""
    bits: List[str] = []

    # 1. Пульс (если получится)
    try:
        from api.routes import city_pulse  # type: ignore
        p = await city_pulse(city_name)
        if isinstance(p, dict):
            score = p.get("score") or p.get("pulse_score")
            if score is not None:
                bits.append(f"пульс {round(float(score))} из 100")
    except Exception:  # noqa: BLE001
        pass

    # 2. Просевшие метрики
    try:
        if cid is not None:
            from db.queries import latest_metrics
            m = await latest_metrics(cid)
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
    except Exception:  # noqa: BLE001
        pass

    # 3. Кризис-радар
    try:
        from api.routes import city_crisis  # type: ignore
        c = await city_crisis(city_name)
        if isinstance(c, dict):
            alerts = c.get("alerts") or []
            if alerts:
                bits.append(f"кризис-алертов: {len(alerts)}")
            else:
                bits.append("кризис-радар чист")
    except Exception:  # noqa: BLE001
        pass

    # 4. Темы депутатов
    try:
        if cid is not None:
            from db import deputy_queries as q
            topics = await q.list_topics(cid, status="active", limit=20)
            if topics:
                bits.append(f"у депутатов {len(topics)} активных тем")
    except Exception:  # noqa: BLE001
        pass

    # 5. Новости за сутки
    try:
        if cid is not None:
            from db.queries import news_window
            items = await news_window(cid, hours=24)
            if items:
                bits.append(f"свежих новостей: {len(items)}")
    except Exception:  # noqa: BLE001
        pass

    if not bits:
        return ("Сегодня по городу пока тихо — данных у меня мало.", ["daily_brief"])
    return ("Сводка дня: " + "; ".join(bits) + ".", ["daily_brief"])


async def _run_search_vk(query: str) -> tuple[str, List[str]]:
    """Поиск VK: люди + группы + свежие посты. Сжимаем в одну фразу
    под голос (3-5 фактов)."""
    from collectors.vk_discover import search_groups, search_news, search_users

    groups = await search_groups(query, limit=3)
    users = await search_users(query, limit=3)
    posts = await search_news(query, count=3)

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


@router.get("/greeting")
async def copilot_greeting() -> dict:
    """Короткое приветствие Джарвиса. Используется фронтом через
    10 секунд после первой загрузки страницы (один раз за сессию).

    Текст единый — озвучивается Fish Audio'м, если он настроен. Иначе
    фронт деградирует к speechSynthesis.
    """
    from ai.copilot import GREETING_TEXT

    response: Dict[str, Any] = {
        "text": GREETING_TEXT,
        "tts_engine": "browser",
        "audio": None,
        "audio_mime": None,
    }
    if fish_configured():
        try:
            mp3 = await fish_synthesize(GREETING_TEXT)
            if mp3:
                response["audio"] = base64.b64encode(mp3).decode("ascii")
                response["audio_mime"] = "audio/mpeg"
                response["tts_engine"] = "fish"
        except Exception:  # noqa: BLE001
            logger.exception("greeting fish_synthesize failed")
    return response


@router.post("/chat")
async def copilot_chat_endpoint(payload: CopilotIn) -> dict:
    cfg = _resolve_city_safe(payload.city)
    ctx = await _build_context(cfg["name"], payload.message)

    # Долговременная память — подмешиваем 2-4 строки в context
    if payload.identity:
        try:
            from ai.jarvis_memory import build_memory_lines
            mem_lines = await build_memory_lines(payload.identity)
            if mem_lines:
                ctx["memory"] = mem_lines
        except Exception:  # noqa: BLE001
            logger.exception("memory load failed")

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
