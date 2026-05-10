"""Thin async DeepSeek client.

DeepSeek exposes an OpenAI-compatible Chat Completions endpoint, so this
module stays minimal — a single `chat_json()` method that forces
`response_format={"type": "json_object"}` and decodes the reply.

Features:
- configurable base_url / model / timeout
- Bearer auth via `DEEPSEEK_API_KEY`
- one retry on 429 / 5xx / transient network errors
- raises `DeepSeekError` on final failure so callers can decide whether
  to fall back or surface the error
- optional Redis-backed response cache (see `ai/cache.py`); when a hit
  is found we skip the network call entirely
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

import aiohttp

from config.settings import settings

from .cache import ResponseCache, make_cache_key

logger = logging.getLogger(__name__)


class DeepSeekError(RuntimeError):
    """Raised when DeepSeek fails after all retries."""


class DeepSeekClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_s: float = 30.0,
        cache: Optional[ResponseCache] = None,
    ):
        self.api_key = api_key if api_key is not None else settings.deepseek_api_key
        self.base_url = (base_url or settings.deepseek_base_url).rstrip("/")
        self.model = model or settings.deepseek_model
        self.timeout = aiohttp.ClientTimeout(total=timeout_s, connect=10)
        self.cache = cache  # may be None — caching is optional

    @property
    def enabled(self) -> bool:
        # В демо-режиме клиент маскируется под «не сконфигурирован»: все
        # callers уже проверяют .enabled и берут fallback из кеша/БД.
        if getattr(settings, "demo_mode", False):
            return False
        return bool(self.api_key)

    async def chat_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """Send a chat completion and return the decoded JSON body.

        When `use_cache=True` (default) and a cache instance is attached,
        we look up a SHA256(model+system+user) key in Redis first and
        return the stored payload on hit — no network call, no tokens.

        Raises `DeepSeekError` if the API is unreachable after one retry or
        if the model returns non-JSON content.
        """
        if not self.enabled:
            raise DeepSeekError("DEEPSEEK_API_KEY is not configured")

        cache_key = (
            make_cache_key(system, user, self.model)
            if (use_cache and self.cache is not None and self.cache.enabled)
            else None
        )
        if cache_key is not None:
            cached = await self.cache.get(cache_key)
            if cached is not None:
                logger.debug("DeepSeek cache HIT %s", cache_key[-8:])
                # Учёт Redis cache hit'а — токенов не потратили, но факт
                # обращения логируем для статистики «было сэкономлено N
                # вызовов».
                try:
                    from ops.deepseek_usage import log_call as _log_call
                    await _log_call(
                        model=self.model, cached_from_redis=True,
                        prompt_tokens=0, completion_tokens=0, total_tokens=0,
                        cost_usd=0.0,
                    )
                except Exception:  # noqa: BLE001
                    pass
                return cached

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        last_exc: Optional[BaseException] = None
        result: Optional[Dict[str, Any]] = None
        for attempt in range(2):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.post(url, json=payload, headers=headers) as resp:
                        if resp.status == 429 or resp.status >= 500:
                            body = await resp.text()
                            raise DeepSeekError(
                                f"DeepSeek transient {resp.status}: {body[:200]}"
                            )
                        if resp.status >= 400:
                            body = await resp.text()
                            raise DeepSeekError(
                                f"DeepSeek HTTP {resp.status}: {body[:200]}"
                            )
                        data = await resp.json()
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exc = exc
                logger.warning("DeepSeek attempt %d failed (%s)", attempt + 1, exc)
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            except DeepSeekError as exc:
                last_exc = exc
                if "transient" in str(exc) and attempt == 0:
                    logger.warning("DeepSeek retrying after %s", exc)
                    await asyncio.sleep(0.5)
                    continue
                raise

            try:
                content = data["choices"][0]["message"]["content"]
                result = json.loads(content)
                break
            except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
                raise DeepSeekError(f"Bad DeepSeek response shape: {exc}") from exc

        if result is None:
            raise DeepSeekError(f"DeepSeek unreachable: {last_exc}")

        # Учёт расхода — fail-safe, не блокирует основной поток.
        try:
            from ops.deepseek_usage import log_call as _log_call
            from .deepseek_pricing import compute_cost_usd as _compute_cost
            usage = (data or {}).get("usage") or {}
            prompt_tok = int(usage.get("prompt_tokens", 0))
            completion_tok = int(usage.get("completion_tokens", 0))
            total_tok = int(usage.get("total_tokens", prompt_tok + completion_tok))
            cache_hit = int(usage.get("prompt_cache_hit_tokens", 0))
            cache_miss = int(usage.get("prompt_cache_miss_tokens", max(0, prompt_tok - cache_hit)))
            cost = _compute_cost(
                model=self.model,
                prompt_tokens=prompt_tok,
                completion_tokens=completion_tok,
                prompt_cache_hit_tokens=cache_hit,
                prompt_cache_miss_tokens=cache_miss,
            )
            await _log_call(
                model=self.model,
                prompt_tokens=prompt_tok,
                completion_tokens=completion_tok,
                total_tokens=total_tok,
                prompt_cache_hit_tokens=cache_hit,
                prompt_cache_miss_tokens=cache_miss,
                cost_usd=cost,
                cached_from_redis=False,
            )
        except Exception:  # noqa: BLE001
            pass

        if cache_key is not None:
            await self.cache.set(cache_key, result)
        return result

    @staticmethod
    def usage_from(data: Dict[str, Any]) -> Dict[str, int]:
        """Convenience: pull prompt/completion tokens for logging."""
        usage = data.get("usage") or {}
        return {
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
            "total_tokens": int(usage.get("total_tokens", 0)),
        }
