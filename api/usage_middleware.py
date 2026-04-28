"""ASGI middleware that logs every request into usage_events.

Runs AFTER the endpoint, so it can capture response status + elapsed
time. Scraps user_id from the session cookie by looking up the session
store — when cookie is absent or invalid, the event is still recorded
with user_id=NULL.

Privacy filter:
- IP truncated to /24 (IPv4) / /48 (IPv6) via ops.usage.truncate_ip.
- User-Agent trimmed to 200 chars.
- Paths that carry a session cookie never have the raw token logged;
  we store only its SHA-256 to correlate within a session without
  being able to hijack it from the audit log.

Skip rules:
- /api/health and /api/health/system — too noisy (every minute).
- Static /style.css, /dashboard.js, /favicon.* — not user-intent.
- WebSocket upgrades (not used today, но future-proof).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from auth.security import hash_token
from auth.store import get_user_by_token
from ops.usage import log_event

logger = logging.getLogger(__name__)


_SKIP_PREFIXES = (
    "/api/health",        # root health + /api/health/system
    "/style.css", "/dashboard.js",
    "/favicon", "/static",
    "/favicon.ico", "/favicon.svg",
)
SESSION_COOKIE_NAME = "citymind_session"


class UsageLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any):
        path = request.url.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        token = request.cookies.get(SESSION_COOKIE_NAME)
        user_id = None
        token_hash = None
        if token:
            token_hash = hash_token(token)
            try:
                user = await get_user_by_token(token)
                if user is not None:
                    user_id = user["id"]
            except Exception:  # noqa: BLE001
                pass

        try:
            await log_event(
                path=path,
                method=request.method,
                status=response.status_code,
                response_time_ms=elapsed_ms,
                user_id=user_id,
                session_token_hash=token_hash,
                ip=_client_ip(request),
                user_agent=request.headers.get("user-agent"),
            )
        except Exception:  # noqa: BLE001
            logger.debug("UsageLoggingMiddleware: log_event raised", exc_info=False)

        return response


def _client_ip(request: Request) -> str:
    """Prefer X-Forwarded-For (first hop) over request.client.host."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return ""
