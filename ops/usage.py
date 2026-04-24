"""Usage analytics — captures + aggregates.

Two halves:

1. `log_event(...)` — async non-blocking insert of one request into
   usage_events. Fires on every request from the FastAPI middleware.
   Silent no-op when the DB pool is missing.

2. Aggregation helpers — pure SQL wrappers returning dicts, consumed
   by the admin stats endpoints. Every function has a `days` / `limit`
   cap to prevent runaway scans.

Privacy notes:
- IP is truncated to a /24 prefix (first three octets + ".0") before
  store. No full client IP persisted.
- User-Agent is kept but limited to 200 chars.
- Request bodies are never captured.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from db.pool import get_pool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

async def log_event(
    *,
    path: str,
    method: str,
    status: int,
    response_time_ms: Optional[int] = None,
    user_id: Optional[int] = None,
    session_token_hash: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """Best-effort insert of a usage event. Never raises."""
    pool = get_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO usage_events
                    (user_id, session_token_hash, path, method, status,
                     response_time_ms, ip_prefix, user_agent)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                user_id,
                session_token_hash,
                (path or "")[:500],
                (method or "GET")[:10],
                int(status or 0),
                int(response_time_ms) if response_time_ms is not None else None,
                truncate_ip(ip),
                (user_agent or "")[:200] or None,
            )
    except Exception:  # noqa: BLE001
        logger.debug("usage log_event failed", exc_info=False)


def truncate_ip(ip: Optional[str]) -> Optional[str]:
    """Return IPv4 /24 prefix or IPv6 /48 prefix — никогда не возвращаем full address."""
    if not ip:
        return None
    ip = ip.strip()
    # IPv6 with colon — take first 3 groups (48 bits).
    if ":" in ip:
        parts = ip.split(":")
        head = [p for p in parts if p][:3]
        return ":".join(head) + "::/48"
    parts = ip.split(".")
    if len(parts) != 4:
        return None
    return ".".join(parts[:3]) + ".0/24"


# ---------------------------------------------------------------------------
# Aggregations
# ---------------------------------------------------------------------------

async def top_users(days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
    """Return top N authenticated users by event count over the window."""
    pool = get_pool()
    if pool is None:
        return []
    days = max(1, min(365, int(days)))
    limit = max(1, min(100, int(limit)))
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT u.id AS user_id,
                       u.email,
                       u.full_name,
                       u.role,
                       COUNT(*)           AS events,
                       MIN(e.created_at)  AS first_seen,
                       MAX(e.created_at)  AS last_seen
                FROM usage_events e
                JOIN users u ON u.id = e.user_id
                WHERE e.user_id IS NOT NULL AND e.created_at >= $1
                GROUP BY u.id, u.email, u.full_name, u.role
                ORDER BY events DESC
                LIMIT $2
                """,
                since, limit,
            )
        return [
            {
                "user_id": r["user_id"],
                "email": r["email"],
                "full_name": r["full_name"],
                "role": r["role"],
                "events": int(r["events"]),
                "first_seen": r["first_seen"].isoformat() if r["first_seen"] else None,
                "last_seen": r["last_seen"].isoformat() if r["last_seen"] else None,
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        logger.warning("top_users failed", exc_info=False)
        return []


async def top_endpoints(days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
    """Return top N endpoints by total hits."""
    pool = get_pool()
    if pool is None:
        return []
    days = max(1, min(365, int(days)))
    limit = max(1, min(100, int(limit)))
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT path,
                       COUNT(*)                        AS hits,
                       COUNT(DISTINCT user_id)         AS distinct_users,
                       ROUND(AVG(response_time_ms))::INT AS avg_ms,
                       SUM(CASE WHEN status >= 500 THEN 1 ELSE 0 END) AS errors_5xx,
                       SUM(CASE WHEN status BETWEEN 400 AND 499 THEN 1 ELSE 0 END) AS errors_4xx
                FROM usage_events
                WHERE created_at >= $1
                GROUP BY path
                ORDER BY hits DESC
                LIMIT $2
                """,
                since, limit,
            )
        return [
            {
                "path": r["path"],
                "hits": int(r["hits"]),
                "distinct_users": int(r["distinct_users"] or 0),
                "avg_ms": int(r["avg_ms"]) if r["avg_ms"] is not None else None,
                "errors_5xx": int(r["errors_5xx"]),
                "errors_4xx": int(r["errors_4xx"]),
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        logger.warning("top_endpoints failed", exc_info=False)
        return []


async def daily_counts(days: int = 30) -> List[Dict[str, Any]]:
    """Return per-day event counts + distinct users over the window."""
    pool = get_pool()
    if pool is None:
        return []
    days = max(1, min(365, int(days)))
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DATE(created_at AT TIME ZONE 'Europe/Moscow') AS day,
                       COUNT(*)                                      AS hits,
                       COUNT(DISTINCT user_id)                       AS users,
                       COUNT(DISTINCT session_token_hash)             AS sessions
                FROM usage_events
                WHERE created_at >= $1
                GROUP BY day
                ORDER BY day ASC
                """,
                since,
            )
        return [
            {
                "day": r["day"].isoformat() if r["day"] else None,
                "hits": int(r["hits"]),
                "users": int(r["users"] or 0),
                "sessions": int(r["sessions"] or 0),
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        return []


async def user_timeline(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Per-user activity log — last N events, newest first."""
    pool = get_pool()
    if pool is None:
        return []
    limit = max(1, min(500, int(limit)))
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT path, method, status, response_time_ms, created_at
                FROM usage_events
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                int(user_id), limit,
            )
        return [
            {
                "path": r["path"],
                "method": r["method"],
                "status": int(r["status"]),
                "response_time_ms": r["response_time_ms"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        return []


async def summary(days: int = 7) -> Dict[str, Any]:
    """Overall summary: total events, authenticated vs anon, errors."""
    pool = get_pool()
    empty = {
        "window_days": days, "total_events": 0, "authenticated_events": 0,
        "anonymous_events": 0, "distinct_users": 0, "distinct_sessions": 0,
        "errors_5xx": 0, "errors_4xx": 0, "avg_response_ms": None,
    }
    if pool is None:
        return empty
    days = max(1, min(365, int(days)))
    since = datetime.now(tz=timezone.utc) - timedelta(days=days)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    COUNT(*)                                                  AS total,
                    SUM(CASE WHEN user_id IS NOT NULL THEN 1 ELSE 0 END)      AS auth,
                    SUM(CASE WHEN user_id IS NULL THEN 1 ELSE 0 END)          AS anon,
                    COUNT(DISTINCT user_id)                                   AS users,
                    COUNT(DISTINCT session_token_hash)                        AS sessions,
                    SUM(CASE WHEN status >= 500 THEN 1 ELSE 0 END)            AS e5,
                    SUM(CASE WHEN status BETWEEN 400 AND 499 THEN 1 ELSE 0 END) AS e4,
                    ROUND(AVG(response_time_ms))::INT                         AS avg_ms
                FROM usage_events
                WHERE created_at >= $1
                """,
                since,
            )
        if row is None:
            return {**empty, "window_days": days}
        return {
            "window_days": days,
            "total_events": int(row["total"] or 0),
            "authenticated_events": int(row["auth"] or 0),
            "anonymous_events": int(row["anon"] or 0),
            "distinct_users": int(row["users"] or 0),
            "distinct_sessions": int(row["sessions"] or 0),
            "errors_5xx": int(row["e5"] or 0),
            "errors_4xx": int(row["e4"] or 0),
            "avg_response_ms": int(row["avg_ms"]) if row["avg_ms"] is not None else None,
        }
    except Exception:  # noqa: BLE001
        return {**empty, "window_days": days}
