"""Redis-backed response cache for DeepSeek calls.

Most `/agenda` requests within the same hour see overlapping batches of
news items, so the same prompt hits DeepSeek again and again. This
module hashes (system + user + model) → SHA256 and stores the JSON
response in Redis with a TTL (default 24 h), saving 80%+ of token spend.

The cache is best-effort:
- if `REDIS_URL` is missing or the connection fails, every operation is
  a silent no-op (`get` returns None, `set` does nothing);
- callers never see Redis errors, only missed hits.

A duck-typed `RedisLike` interface is also accepted so unit tests can
inject an in-memory fake without bringing up a real broker.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Optional, Protocol

from config.settings import settings

logger = logging.getLogger(__name__)


class RedisLike(Protocol):
    async def get(self, key: str) -> Optional[bytes | str]: ...
    async def set(self, key: str, value: str, ex: Optional[int] = None) -> Any: ...


def make_cache_key(system: str, user: str, model: str) -> str:
    """Return a stable cache key for a (system, user, model) triple."""
    digest = hashlib.sha256(
        f"{model}\x00{system}\x00{user}".encode("utf-8")
    ).hexdigest()
    return f"citymind:ds:{digest}"


class ResponseCache:
    """Thin wrapper around redis.asyncio with safe fallbacks.

    Pass `redis=` an instance for tests; production calls
    `ResponseCache.from_settings()` which lazily connects to
    `REDIS_URL`.
    """

    def __init__(
        self,
        redis: Optional[RedisLike] = None,
        *,
        ttl_seconds: int = 24 * 3600,
        namespace: str = "citymind:ds:",
    ):
        self._redis = redis
        self.ttl_seconds = ttl_seconds
        self.namespace = namespace

    @property
    def enabled(self) -> bool:
        return self._redis is not None

    @classmethod
    def from_settings(cls) -> "ResponseCache":
        """Build a cache pointing at `REDIS_URL`. Returns a no-op cache if
        the redis package is missing or the URL is empty."""
        ttl = max(0, settings.enrichment_cache_ttl_hours) * 3600
        if not settings.redis_url:
            return cls(redis=None, ttl_seconds=ttl)
        try:
            from redis.asyncio import Redis  # type: ignore
        except ImportError:
            logger.warning("redis package not installed — DeepSeek cache disabled")
            return cls(redis=None, ttl_seconds=ttl)
        try:
            client = Redis.from_url(settings.redis_url, decode_responses=False)
        except Exception:  # noqa: BLE001
            logger.exception("Cannot init Redis client at %s", settings.redis_url)
            return cls(redis=None, ttl_seconds=ttl)
        return cls(redis=client, ttl_seconds=ttl)

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        if self._redis is None:
            return None
        try:
            raw = await self._redis.get(key)
        except Exception:  # noqa: BLE001
            logger.warning("Redis GET failed for %s", key, exc_info=False)
            return None
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Cached payload for %s is not valid JSON; ignoring", key)
            return None

    async def set(self, key: str, value: Dict[str, Any]) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.set(
                key,
                json.dumps(value, ensure_ascii=False),
                ex=self.ttl_seconds or None,
            )
        except Exception:  # noqa: BLE001
            logger.warning("Redis SET failed for %s", key, exc_info=False)
