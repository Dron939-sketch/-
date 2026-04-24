"""Async DB helpers for users + sessions.

Thin wrappers around asyncpg that fall back to in-memory stub when the
pool is unavailable — lets local tests run without a real Postgres.
Storage schema lives in `migrations/init_db.sql`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from db.pool import get_pool

from .security import hash_password, hash_token, new_session_token, verify_password

logger = logging.getLogger(__name__)


SESSION_TTL_HOURS = 24 * 14   # 14-day sliding window


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    if pool is None:
        return None
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, full_name, role, password_hash "
                "FROM users WHERE LOWER(email) = LOWER($1) LIMIT 1",
                email,
            )
        return dict(row) if row else None
    except Exception:  # noqa: BLE001
        logger.warning("get_user_by_email failed", exc_info=False)
        return None


async def create_user(
    email: str,
    password: str,
    *,
    full_name: Optional[str] = None,
    role: str = "viewer",
) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    if pool is None:
        return None
    pw_hash = hash_password(password)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO users (email, full_name, role, password_hash) "
                "VALUES ($1, $2, $3, $4) "
                "ON CONFLICT (email) DO NOTHING "
                "RETURNING id, email, full_name, role",
                email.lower().strip(), full_name, role, pw_hash,
            )
        return dict(row) if row else None
    except Exception:  # noqa: BLE001
        logger.warning("create_user failed", exc_info=False)
        return None


async def authenticate(email: str, password: str) -> Optional[Dict[str, Any]]:
    user = await get_user_by_email(email)
    if user is None:
        return None
    if not verify_password(password, user.get("password_hash")):
        return None
    # Scrub password_hash from the returned record.
    user.pop("password_hash", None)
    await _touch_last_login(user["id"])
    return user


async def _touch_last_login(user_id: int) -> None:
    pool = get_pool()
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET last_login_at = NOW() WHERE id = $1",
                user_id,
            )
    except Exception:  # noqa: BLE001
        logger.debug("last_login_at update failed", exc_info=False)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

async def create_session(user_id: int) -> Optional[str]:
    """Insert a new session row and return the raw token (cookie value)."""
    pool = get_pool()
    if pool is None:
        return None
    token, token_hash = new_session_token()
    expires = datetime.now(tz=timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO user_sessions (token_hash, user_id, expires_at) "
                "VALUES ($1, $2, $3)",
                token_hash, int(user_id), expires,
            )
        return token
    except Exception:  # noqa: BLE001
        logger.warning("create_session failed", exc_info=False)
        return None


async def get_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    """Return {id, email, full_name, role} for a valid live session token."""
    pool = get_pool()
    if pool is None or not token:
        return None
    token_hash = hash_token(token)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT u.id, u.email, u.full_name, u.role
                FROM user_sessions s JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = $1 AND s.expires_at > NOW()
                LIMIT 1
                """,
                token_hash,
            )
        return dict(row) if row else None
    except Exception:  # noqa: BLE001
        return None


async def revoke_session(token: str) -> bool:
    pool = get_pool()
    if pool is None or not token:
        return False
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM user_sessions WHERE token_hash = $1",
                hash_token(token),
            )
        return True
    except Exception:  # noqa: BLE001
        return False


async def purge_expired_sessions() -> int:
    pool = get_pool()
    if pool is None:
        return 0
    try:
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM user_sessions WHERE expires_at < NOW()")
        # asyncpg returns like "DELETE 3"
        try:
            return int(result.split()[1])
        except (IndexError, ValueError):
            return 0
    except Exception:  # noqa: BLE001
        return 0
