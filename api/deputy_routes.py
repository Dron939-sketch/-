"""HTTP routes for the Deputy Agenda module.

All write endpoints gated behind `require_role("admin", "editor")`.
Read endpoints — `require_user` (any logged-in user).

Endpoints:
  GET    /api/city/{name}/deputies                — список депутатов города
  POST   /api/city/{name}/deputies                — добавить/обновить депутата
  DELETE /api/city/{name}/deputies/{deputy_id}    — удалить депутата

  GET    /api/city/{name}/deputy-topics           — список тем
  POST   /api/city/{name}/deputy-topics           — создать тему
  GET    /api/city/{name}/deputy-topics/{id}      — детали темы (+ посты)
  POST   /api/city/{name}/deputy-topics/{id}/assign — назначить депутатов
                                                     (auto или явный список)
  POST   /api/city/{name}/deputy-topics/{id}/status — поменять статус
  POST   /api/city/{name}/deputy-topics/{id}/draft  — черновик публикации
                                                      для конкретного депутата
  POST   /api/city/{name}/deputy-topics/{id}/posts  — зарегистрировать
                                                      опубликованный пост

  GET    /api/city/{name}/deputy-dashboard        — сводка координатора

Persistence: `db/deputy_queries.py`. Все write/read fail-safe — если pool
не поднялся, ручка возвращает 503 (а не 500) и фронт показывает плашку
"БД недоступна".
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from config.cities import get_city, get_city_by_slug
from db.pool import get_pool
from db.seed import city_id_by_name
from db import deputy_queries as q
from deputy_agenda_manager import (
    Deputy,
    DeputyAgendaManager,
    DeputyRole,
    MessageTone,
    Platform,
    TopicTask,
)

from .auth_routes import require_role, require_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/city/{name}", tags=["deputies"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_city(name_or_slug: str):
    try:
        return get_city(name_or_slug)
    except KeyError:
        pass
    try:
        return get_city_by_slug(name_or_slug)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


async def _city_id_or_503(name: str) -> int:
    cid = await city_id_by_name(name)
    if cid is None:
        raise HTTPException(status_code=503, detail="База недоступна.")
    return cid


def _require_pool() -> None:
    if get_pool() is None:
        raise HTTPException(status_code=503, detail="База недоступна.")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_ALLOWED_ROLES = {"speaker", "sector_lead", "district_rep", "support", "neutral"}
_ALLOWED_TONES = {"positive", "neutral", "protective", "explanatory", "mobilizing"}
_ALLOWED_PRIORITIES = {"critical", "high", "medium", "low"}
_ALLOWED_STATUSES = {"active", "paused", "completed"}
_ALLOWED_PLATFORMS = {"telegram", "vk", "ok", "website", "media", "meeting"}


class DeputyIn(BaseModel):
    external_id: Optional[str] = Field(None, max_length=120)
    name: str = Field(..., min_length=1, max_length=200)
    role: str = "sector_lead"
    district: Optional[str] = Field(None, max_length=200)
    party: Optional[str] = Field(None, max_length=200)
    sectors: List[str] = Field(default_factory=list)
    followers: int = 0
    influence_score: float = 0.5
    telegram: Optional[str] = Field(None, max_length=200)
    vk: Optional[str] = Field(None, max_length=200)
    enabled: bool = True

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        if v not in _ALLOWED_ROLES:
            raise ValueError(f"role must be one of {sorted(_ALLOWED_ROLES)}")
        return v


class TopicIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str = ""
    priority: str = "medium"
    target_tone: str = "neutral"
    key_messages: List[str] = Field(default_factory=list)
    talking_points: List[str] = Field(default_factory=list)
    target_audience: List[str] = Field(default_factory=lambda: ["all"])
    assignees: List[int] = Field(default_factory=list)
    required_posts: int = 5
    deadline: Optional[datetime] = None
    source: str = "manual"

    @field_validator("priority")
    @classmethod
    def _priority(cls, v: str) -> str:
        if v not in _ALLOWED_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(_ALLOWED_PRIORITIES)}")
        return v

    @field_validator("target_tone")
    @classmethod
    def _tone(cls, v: str) -> str:
        if v not in _ALLOWED_TONES:
            raise ValueError(f"target_tone must be one of {sorted(_ALLOWED_TONES)}")
        return v


class AssignIn(BaseModel):
    deputy_ids: Optional[List[int]] = None
    auto: bool = True
    max_assignees: int = 5


class StatusIn(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        if v not in _ALLOWED_STATUSES:
            raise ValueError(f"status must be one of {sorted(_ALLOWED_STATUSES)}")
        return v


class DraftIn(BaseModel):
    deputy_id: int
    platform: Optional[str] = None

    @field_validator("platform")
    @classmethod
    def _platform(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _ALLOWED_PLATFORMS:
            raise ValueError(f"platform must be one of {sorted(_ALLOWED_PLATFORMS)}")
        return v


class PostIn(BaseModel):
    deputy_id: int
    platform: str
    url: Optional[str] = Field(None, max_length=600)
    content: Optional[str] = Field(None, max_length=5000)
    published_at: Optional[datetime] = None
    views: int = 0
    likes: int = 0
    comments: int = 0
    reposts: int = 0

    @field_validator("platform")
    @classmethod
    def _platform(cls, v: str) -> str:
        if v not in _ALLOWED_PLATFORMS:
            raise ValueError(f"platform must be one of {sorted(_ALLOWED_PLATFORMS)}")
        return v


# ---------------------------------------------------------------------------
# Routes — deputies
# ---------------------------------------------------------------------------


@router.get("/deputies")
async def deputies_list(name: str, _u: dict = Depends(require_user)) -> dict:
    cfg = _resolve_city(name)
    _require_pool()
    cid = await _city_id_or_503(cfg["name"])
    return {
        "city": cfg["name"],
        "deputies": await q.list_deputies(cid),
    }


@router.post("/deputies")
async def deputies_upsert(
    name: str, payload: DeputyIn,
    _u: dict = Depends(require_role("admin", "editor")),
) -> dict:
    cfg = _resolve_city(name)
    _require_pool()
    cid = await _city_id_or_503(cfg["name"])
    deputy_id = await q.upsert_deputy(cid, payload.model_dump())
    if deputy_id is None:
        raise HTTPException(status_code=500, detail="Не удалось сохранить депутата.")
    return {"city": cfg["name"], "deputy_id": deputy_id}


@router.delete("/deputies/{deputy_id}")
async def deputies_delete(
    name: str, deputy_id: int,
    _u: dict = Depends(require_role("admin", "editor")),
) -> dict:
    cfg = _resolve_city(name)
    _require_pool()
    cid = await _city_id_or_503(cfg["name"])
    if not await q.delete_deputy(cid, deputy_id):
        raise HTTPException(status_code=404, detail="Депутат не найден.")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Routes — topics
# ---------------------------------------------------------------------------


@router.get("/deputy-topics")
async def topics_list(
    name: str, status: Optional[str] = "active",
    _u: dict = Depends(require_user),
) -> dict:
    cfg = _resolve_city(name)
    _require_pool()
    cid = await _city_id_or_503(cfg["name"])
    if status is not None and status not in _ALLOWED_STATUSES:
        raise HTTPException(status_code=422, detail="invalid status filter")
    return {
        "city": cfg["name"],
        "topics": await q.list_topics(cid, status=status),
    }


@router.post("/deputy-topics")
async def topics_create(
    name: str, payload: TopicIn,
    _u: dict = Depends(require_role("admin", "editor")),
) -> dict:
    cfg = _resolve_city(name)
    _require_pool()
    cid = await _city_id_or_503(cfg["name"])
    body = payload.model_dump()
    if body.get("deadline") is None:
        body["deadline"] = datetime.now(timezone.utc) + timedelta(days=3)
    topic_id = await q.insert_topic(cid, body)
    if topic_id is None:
        raise HTTPException(status_code=500, detail="Не удалось создать тему.")
    return {"city": cfg["name"], "topic_id": topic_id}


@router.get("/deputy-topics/{topic_id}")
async def topic_detail(
    name: str, topic_id: int, _u: dict = Depends(require_user),
) -> dict:
    cfg = _resolve_city(name)
    _require_pool()
    cid = await _city_id_or_503(cfg["name"])
    topic = await q.get_topic(cid, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Тема не найдена.")
    posts = await q.list_posts_for_topic(cid, topic_id)
    return {"city": cfg["name"], "topic": topic, "posts": posts}


@router.post("/deputy-topics/{topic_id}/assign")
async def topic_assign(
    name: str, topic_id: int, payload: AssignIn,
    _u: dict = Depends(require_role("admin", "editor")),
) -> dict:
    cfg = _resolve_city(name)
    _require_pool()
    cid = await _city_id_or_503(cfg["name"])
    topic = await q.get_topic(cid, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Тема не найдена.")

    if payload.deputy_ids is not None:
        chosen = [int(x) for x in payload.deputy_ids]
    elif payload.auto:
        # Use the in-memory manager to do the matching, then persist.
        deputies = await q.list_deputies(cid)
        mgr = _hydrate_manager(cfg["name"], deputies, [topic])
        chosen_str = mgr.assign_deputies(
            f"db_{topic_id}", auto=True, max_assignees=payload.max_assignees,
        )
        # Manager works with string ids; we used "db_<int>" as the key.
        chosen = [int(x.removeprefix("db_")) for x in chosen_str]
    else:
        chosen = []

    if not await q.update_topic_assignees(cid, topic_id, chosen):
        raise HTTPException(status_code=500, detail="Не удалось обновить.")
    return {"topic_id": topic_id, "assignees": chosen}


@router.post("/deputy-topics/{topic_id}/status")
async def topic_status(
    name: str, topic_id: int, payload: StatusIn,
    _u: dict = Depends(require_role("admin", "editor")),
) -> dict:
    cfg = _resolve_city(name)
    _require_pool()
    cid = await _city_id_or_503(cfg["name"])
    if not await q.update_topic_status(cid, topic_id, payload.status):
        raise HTTPException(status_code=404, detail="Тема не найдена.")
    return {"topic_id": topic_id, "status": payload.status}


@router.post("/deputy-topics/{topic_id}/draft")
async def topic_draft(
    name: str, topic_id: int, payload: DraftIn,
    _u: dict = Depends(require_role("admin", "editor")),
) -> dict:
    cfg = _resolve_city(name)
    _require_pool()
    cid = await _city_id_or_503(cfg["name"])
    topic = await q.get_topic(cid, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Тема не найдена.")
    deputies = await q.list_deputies(cid)
    if not any(d["id"] == payload.deputy_id for d in deputies):
        raise HTTPException(status_code=404, detail="Депутат не найден.")

    mgr = _hydrate_manager(cfg["name"], deputies, [topic])
    platform = Platform(payload.platform) if payload.platform else None
    draft = mgr.suggest_draft(
        f"db_{topic_id}", f"db_{payload.deputy_id}", platform=platform,
    )
    return {
        "topic_id": topic_id,
        "deputy_id": payload.deputy_id,
        "is_draft": draft.is_draft,
        "note": draft.note,
        "suggested_text": draft.suggested_text,
        "talking_points": draft.talking_points,
        "tone": draft.tone,
        "suggested_platform": draft.suggested_platform,
        "hashtags": draft.hashtags,
    }


@router.post("/deputy-topics/{topic_id}/posts")
async def topic_register_post(
    name: str, topic_id: int, payload: PostIn,
    _u: dict = Depends(require_role("admin", "editor")),
) -> dict:
    cfg = _resolve_city(name)
    _require_pool()
    cid = await _city_id_or_503(cfg["name"])
    topic = await q.get_topic(cid, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Тема не найдена.")
    body = payload.model_dump()
    body["topic_id"] = topic_id
    post_id = await q.insert_post(cid, body)
    if post_id is None:
        raise HTTPException(status_code=500, detail="Не удалось зарегистрировать пост.")
    return {"post_id": post_id, "topic_id": topic_id}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/deputy-dashboard")
async def deputy_dashboard(
    name: str, _u: dict = Depends(require_user),
) -> dict:
    cfg = _resolve_city(name)
    _require_pool()
    cid = await _city_id_or_503(cfg["name"])
    active = await q.list_topics(cid, status="active")
    completed = await q.list_topics(cid, status="completed", limit=5)
    deputies = await q.list_deputies(cid)
    total_completed = sum(t["completed_posts"] for t in active)
    total_required = sum(t["required_posts"] for t in active) or 1
    return {
        "city": cfg["name"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "deputies": len([d for d in deputies if d["enabled"]]),
            "active_topics": len(active),
            "completed_topics_recent": len(completed),
            "completion_rate": round(total_completed / total_required, 2),
        },
        "active_topics": active,
        "recent_completed": completed,
    }


# ---------------------------------------------------------------------------
# Bridge: hydrate the in-memory manager from DB rows
# ---------------------------------------------------------------------------


def _hydrate_manager(
    city_name: str,
    deputies_rows: List[dict],
    topic_rows: List[dict],
) -> DeputyAgendaManager:
    """Construct a fresh manager from DB state for the duration of one request.

    Manager keys: deputies use "db_<id>", topics use "db_<id>". This way the
    in-memory matching code stays untouched and we don't need to migrate it
    to integer ids.
    """
    mgr = DeputyAgendaManager(city_name)
    for d in deputies_rows:
        mgr.add_deputy(Deputy(
            id=f"db_{d['id']}",
            name=d["name"],
            role=DeputyRole(d["role"]),
            district=d.get("district") or "",
            party=d.get("party") or "",
            sectors=list(d.get("sectors") or []),
            followers=d.get("followers", 0),
            influence_score=d.get("influence_score", 0.5),
            telegram_channel=d.get("telegram"),
            vk_page=d.get("vk"),
        ))
    for t in topic_rows:
        deadline = t.get("deadline")
        if isinstance(deadline, str):
            deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        mgr.create_topic({
            "id": f"db_{t['id']}",
            "title": t["title"],
            "description": t.get("description", ""),
            "priority": t.get("priority", "medium"),
            "target_tone": MessageTone(t.get("target_tone", "neutral")),
            "key_messages": list(t.get("key_messages") or []),
            "talking_points": list(t.get("talking_points") or []),
            "target_audience": list(t.get("target_audience") or ["all"]),
            "deadline": deadline,
            "required_posts": t.get("required_posts", 5),
            "source": t.get("source", "manual"),
        })
    return mgr
