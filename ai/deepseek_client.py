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
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import aiohttp

from config.settings import settings

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
    ):
        self.api_key = api_key if api_key is not None else settings.deepseek_api_key
        self.base_url = (base_url or settings.deepseek_base_url).rstrip("/")
        self.model = model or settings.deepseek_model
        self.timeout = aiohttp.ClientTimeout(total=timeout_s, connect=10)

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def chat_json(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """Send a chat completion and return the decoded JSON body.

        Raises `DeepSeekError` if the API is unreachable after one retry or
        if the model returns non-JSON content.
        """
        if not self.enabled:
            raise DeepSeekError("DEEPSEEK_API_KEY is not configured")

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
                logger.warning(
                    "DeepSeek attempt %d failed (%s)", attempt + 1, exc
                )
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            except DeepSeekError as exc:
                last_exc = exc
                if "transient" in str(exc) and attempt == 0:
                    logger.warning("DeepSeek retrying after %s", exc)
                    await asyncio.sleep(0.5)
                    continue
                raise

            # Parse Chat Completion envelope.
            try:
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
            except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
                raise DeepSeekError(f"Bad DeepSeek response shape: {exc}") from exc

        raise DeepSeekError(f"DeepSeek unreachable: {last_exc}")

    @staticmethod
    def usage_from(data: Dict[str, Any]) -> Dict[str, int]:
        """Convenience: pull prompt/completion tokens for logging."""
        usage = data.get("usage") or {}
        return {
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
            "total_tokens": int(usage.get("total_tokens", 0)),
        }
