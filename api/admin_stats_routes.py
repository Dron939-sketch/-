"""Admin-only usage statistics endpoints.

Every route gated behind `require_role("admin")` — viewer / editor cannot
see who-did-what. Queries are capped (days ≤ 365, limit ≤ 100) at the
aggregator layer so a hostile admin can't DOS the DB with huge windows.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from ops.usage import daily_counts, summary, top_endpoints, top_users, user_timeline

from .auth_routes import require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/stats", tags=["admin", "stats"])


@router.get("/summary")
async def stats_summary(days: int = 7, _user: dict = Depends(require_role("admin"))) -> dict:
    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        **(await summary(days=days)),
    }


@router.get("/users")
async def stats_users(
    days: int = 30, limit: int = 20,
    _user: dict = Depends(require_role("admin")),
) -> dict:
    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "window_days": days,
        "users": await top_users(days=days, limit=limit),
    }


@router.get("/endpoints")
async def stats_endpoints(
    days: int = 30, limit: int = 20,
    _user: dict = Depends(require_role("admin")),
) -> dict:
    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "window_days": days,
        "endpoints": await top_endpoints(days=days, limit=limit),
    }


@router.get("/daily")
async def stats_daily(days: int = 30, _user: dict = Depends(require_role("admin"))) -> dict:
    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "window_days": days,
        "days": await daily_counts(days=days),
    }


@router.get("/user/{user_id}")
async def stats_one_user(
    user_id: int, limit: int = 50,
    _user: dict = Depends(require_role("admin")),
) -> dict:
    if user_id < 1:
        raise HTTPException(status_code=422, detail="user_id must be positive")
    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "user_id": user_id,
        "events": await user_timeline(user_id=user_id, limit=limit),
    }
