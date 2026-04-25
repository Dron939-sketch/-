"""Async query helpers for the deputy agenda module.

Mirrors the patterns in `db/queries.py`:
- Every helper is fail-safe: missing pool / failed query → empty result
  (None / [] / 0). The web tier never crashes on a dead DB.
- All writes use parameterised SQL; no string interpolation.
- JSONB columns serialised via `json.dumps(..., ensure_ascii=False)` so
  Cyrillic round-trips cleanly.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .pool import get_pool

logger = logging.getLogger(__name__)


def _loads(value: Any, default: Any) -> Any:
    """asyncpg returns JSONB as str on plain Postgres; deserialise once."""
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


# ---------------------------------------------------------------------------
# Deputies
# ---------------------------------------------------------------------------

_INSERT_DEPUTY_SQL = """
INSERT INTO deputies
    (city_id, external_id, name, role, district, party, sectors,
     followers, influence_score, telegram, vk, enabled)
VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10, $11, $12)
ON CONFLICT (city_id, external_id) DO UPDATE SET
    name            = EXCLUDED.name,
    role            = EXCLUDED.role,
    district        = EXCLUDED.district,
    party           = EXCLUDED.party,
    sectors         = EXCLUDED.sectors,
    followers       = EXCLUDED.followers,
    influence_score = EXCLUDED.influence_score,
    telegram        = EXCLUDED.telegram,
    vk              = EXCLUDED.vk,
    enabled         = EXCLUDED.enabled
RETURNING id
"""


async def upsert_deputy(city_id: int, payload: Dict[str, Any]) -> Optional[int]:
    pool = get_pool()
    if pool is None:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                _INSERT_DEPUTY_SQL,
                city_id,
                payload.get("external_id"),
                payload["name"],
                payload.get("role", "sector_lead"),
                payload.get("district"),
                payload.get("party"),
                json.dumps(list(payload.get("sectors") or []), ensure_ascii=False),
                int(payload.get("followers", 0)),
                float(payload.get("influence_score", 0.5)),
                payload.get("telegram"),
                payload.get("vk"),
                bool(payload.get("enabled", True)),
            )
            return int(row["id"]) if row else None
    except Exception:  # noqa: BLE001
        logger.warning("upsert_deputy failed for city %s", city_id, exc_info=False)
        return None


async def list_deputies(city_id: int) -> List[Dict[str, Any]]:
    pool = get_pool()
    if pool is None:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, external_id, name, role, district, party, sectors,
                       followers, influence_score, telegram, vk, enabled, created_at
                FROM deputies
                WHERE city_id = $1
                ORDER BY enabled DESC, name
                """,
                city_id,
            )
    except Exception:  # noqa: BLE001
        logger.warning("list_deputies failed for city %s", city_id, exc_info=False)
        return []

    return [
        {
            "id": r["id"],
            "external_id": r["external_id"],
            "name": r["name"],
            "role": r["role"],
            "district": r["district"],
            "party": r["party"],
            "sectors": _loads(r["sectors"], []),
            "followers": r["followers"],
            "influence_score": r["influence_score"],
            "telegram": r["telegram"],
            "vk": r["vk"],
            "enabled": r["enabled"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


async def delete_deputy(city_id: int, deputy_id: int) -> bool:
    pool = get_pool()
    if pool is None:
        return False
    try:
        async with pool.acquire() as conn:
            res = await conn.execute(
                "DELETE FROM deputies WHERE city_id = $1 AND id = $2",
                city_id, deputy_id,
            )
            return res.endswith(" 1")
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

_INSERT_TOPIC_SQL = """
INSERT INTO deputy_topics
    (city_id, title, description, priority, target_tone, key_messages,
     talking_points, target_audience, assignees, required_posts, status,
     source, deadline)
VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8::jsonb, $9::jsonb,
        $10, $11, $12, $13)
RETURNING id
"""


async def insert_topic(city_id: int, payload: Dict[str, Any]) -> Optional[int]:
    pool = get_pool()
    if pool is None:
        return None
    deadline = payload.get("deadline")
    if isinstance(deadline, str):
        deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
    if deadline is None:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                _INSERT_TOPIC_SQL,
                city_id,
                payload["title"],
                payload.get("description", ""),
                payload.get("priority", "medium"),
                payload.get("target_tone", "neutral"),
                json.dumps(list(payload.get("key_messages") or []), ensure_ascii=False),
                json.dumps(list(payload.get("talking_points") or []), ensure_ascii=False),
                json.dumps(list(payload.get("target_audience") or ["all"]), ensure_ascii=False),
                json.dumps(list(payload.get("assignees") or []), ensure_ascii=False),
                int(payload.get("required_posts", 5)),
                payload.get("status", "active"),
                payload.get("source", "manual"),
                deadline,
            )
            return int(row["id"]) if row else None
    except Exception:  # noqa: BLE001
        logger.warning("insert_topic failed for city %s", city_id, exc_info=False)
        return None


async def list_topics(
    city_id: int, *, status: Optional[str] = "active", limit: int = 50,
) -> List[Dict[str, Any]]:
    pool = get_pool()
    if pool is None:
        return []
    sql = """
        SELECT id, title, description, priority, target_tone, key_messages,
               talking_points, target_audience, assignees, required_posts,
               completed_posts, status, source, deadline, created_at
        FROM deputy_topics
        WHERE city_id = $1
    """
    params: List[Any] = [city_id]
    if status is not None:
        sql += " AND status = $2"
        params.append(status)
    sql += " ORDER BY deadline ASC LIMIT $%d" % (len(params) + 1,)
    params.append(int(limit))

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
    except Exception:  # noqa: BLE001
        logger.warning("list_topics failed for city %s", city_id, exc_info=False)
        return []

    return [_topic_row_to_dict(r) for r in rows]


async def get_topic(city_id: int, topic_id: int) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    if pool is None:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, title, description, priority, target_tone, key_messages,
                       talking_points, target_audience, assignees, required_posts,
                       completed_posts, status, source, deadline, created_at
                FROM deputy_topics
                WHERE city_id = $1 AND id = $2
                """,
                city_id, topic_id,
            )
    except Exception:  # noqa: BLE001
        return None
    return _topic_row_to_dict(row) if row else None


def _topic_row_to_dict(row: Any) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "priority": row["priority"],
        "target_tone": row["target_tone"],
        "key_messages": _loads(row["key_messages"], []),
        "talking_points": _loads(row["talking_points"], []),
        "target_audience": _loads(row["target_audience"], ["all"]),
        "assignees": _loads(row["assignees"], []),
        "required_posts": row["required_posts"],
        "completed_posts": row["completed_posts"],
        "status": row["status"],
        "source": row["source"],
        "deadline": row["deadline"].isoformat() if row["deadline"] else None,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


async def update_topic_assignees(
    city_id: int, topic_id: int, assignees: List[int],
) -> bool:
    pool = get_pool()
    if pool is None:
        return False
    try:
        async with pool.acquire() as conn:
            res = await conn.execute(
                """
                UPDATE deputy_topics
                SET assignees = $3::jsonb
                WHERE city_id = $1 AND id = $2
                """,
                city_id, topic_id,
                json.dumps([int(x) for x in assignees]),
            )
            return res.endswith(" 1")
    except Exception:  # noqa: BLE001
        return False


async def update_topic_status(
    city_id: int, topic_id: int, status: str,
) -> bool:
    pool = get_pool()
    if pool is None:
        return False
    try:
        async with pool.acquire() as conn:
            res = await conn.execute(
                "UPDATE deputy_topics SET status = $3 WHERE city_id = $1 AND id = $2",
                city_id, topic_id, status,
            )
            return res.endswith(" 1")
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

_INSERT_POST_SQL = """
INSERT INTO deputy_posts
    (city_id, deputy_id, topic_id, platform, url, content, published_at,
     views, likes, comments, reposts)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
RETURNING id
"""


async def insert_post(city_id: int, payload: Dict[str, Any]) -> Optional[int]:
    pool = get_pool()
    if pool is None:
        return None
    published_at = payload.get("published_at") or datetime.now(timezone.utc)
    if isinstance(published_at, str):
        published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    _INSERT_POST_SQL,
                    city_id,
                    int(payload["deputy_id"]),
                    int(payload["topic_id"]) if payload.get("topic_id") else None,
                    payload["platform"],
                    payload.get("url"),
                    payload.get("content"),
                    published_at,
                    int(payload.get("views", 0)),
                    int(payload.get("likes", 0)),
                    int(payload.get("comments", 0)),
                    int(payload.get("reposts", 0)),
                )
                if payload.get("topic_id"):
                    await conn.execute(
                        """
                        UPDATE deputy_topics
                        SET completed_posts = completed_posts + 1
                        WHERE city_id = $1 AND id = $2
                        """,
                        city_id, int(payload["topic_id"]),
                    )
            return int(row["id"]) if row else None
    except Exception:  # noqa: BLE001
        logger.warning("insert_post failed for city %s", city_id, exc_info=False)
        return None


async def list_posts_for_topic(
    city_id: int, topic_id: int, limit: int = 100,
) -> List[Dict[str, Any]]:
    pool = get_pool()
    if pool is None:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT p.id, p.deputy_id, p.platform, p.url, p.content,
                       p.published_at, p.views, p.likes, p.comments, p.reposts,
                       d.name AS deputy_name
                FROM deputy_posts p
                LEFT JOIN deputies d ON d.id = p.deputy_id
                WHERE p.city_id = $1 AND p.topic_id = $2
                ORDER BY p.published_at DESC
                LIMIT $3
                """,
                city_id, topic_id, int(limit),
            )
    except Exception:  # noqa: BLE001
        return []
    return [
        {
            "id": r["id"],
            "deputy_id": r["deputy_id"],
            "deputy_name": r["deputy_name"],
            "platform": r["platform"],
            "url": r["url"],
            "content": r["content"],
            "published_at": r["published_at"].isoformat() if r["published_at"] else None,
            "views": r["views"],
            "likes": r["likes"],
            "comments": r["comments"],
            "reposts": r["reposts"],
        }
        for r in rows
    ]
