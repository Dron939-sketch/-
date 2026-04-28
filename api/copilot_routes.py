"""Route /api/copilot/chat — голосовой Ко-пилот.

Принимает текст + историю + city slug. Собирает богатый контекст
(метрики, погода, топ жалоб/радостей, активные темы депутатов,
ключевые слова → выборка из новостей за окно), отдаёт в `ai.copilot.chat`,
возвращает {text, action, sources}.

Без auth — Ко-пилот доступен любому посетителю дашборда. Если в
будущем понадобится защита (биллинг по DeepSeek-токенам) — добавим
require_user тут.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai.copilot import chat as copilot_chat
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
    try:
        from db.queries import latest_metrics, latest_weather, news_window
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


@router.post("/chat")
async def copilot_chat_endpoint(payload: CopilotIn) -> dict:
    cfg = _resolve_city_safe(payload.city)
    ctx = await _build_context(cfg["name"], payload.message)
    history = [{"role": t.role, "text": t.text} for t in payload.history]
    result = await copilot_chat(payload.message, ctx, history)
    return {
        "city":    cfg["name"],
        "text":    result["text"],
        "action":  result.get("action"),
        "sources": result.get("sources") or [],
    }
