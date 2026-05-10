"""Fish Audio TTS — облачный синтез речи в премиум-качестве.

Адаптация из проекта Frederick. Конфигурация через env:
  FISH_AUDIO_API_KEY    — Bearer-токен Fish Audio
  FISH_AUDIO_VOICE_ID   — reference_id голоса (выбирается на fish.audio)
  FISH_AUDIO_LATENCY    — balanced (по умолчанию) | normal
  FISH_AUDIO_BITRATE    — 64 / 128 / 192 (kbps), default 128

Без ключей сервис тихо отдаёт None — фронт переключится на
браузерный speechSynthesis. Никаких исключений наружу.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

FISH_AUDIO_URL = "https://api.fish.audio/v1/tts"
_MIN_VALID_BYTES = 100   # ответы меньше — точно не аудио


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def is_configured() -> bool:
    """Доступен ли Fish Audio для этого инстанса (есть ли ключ)."""
    try:
        from config.settings import settings as _settings
        if getattr(_settings, "demo_mode", False):
            return False
    except Exception:  # noqa: BLE001
        pass
    return bool(_env("FISH_AUDIO_API_KEY"))


async def synthesize(text: str) -> Optional[bytes]:
    """Синтез одной фразы. На любую ошибку — None (caller fallback'ится).

    Используется напрямую из api/copilot_routes.py — там же оборачивается
    в try, так что эта функция не должна бросать.
    """
    try:
        from config.settings import settings as _settings
        if getattr(_settings, "demo_mode", False):
            return None
    except Exception:  # noqa: BLE001
        pass
    api_key = _env("FISH_AUDIO_API_KEY")
    voice_id = _env("FISH_AUDIO_VOICE_ID")
    if not api_key or not voice_id:
        return None
    if not text or not text.strip():
        return None
    text = text.strip()
    if len(text) > 4500:
        text = text[:4500]

    try:
        bitrate = int(_env("FISH_AUDIO_BITRATE", "128"))
    except ValueError:
        bitrate = 128
    latency = _env("FISH_AUDIO_LATENCY", "balanced")
    if latency not in {"balanced", "normal"}:
        latency = "balanced"

    payload = {
        "text":         text,
        "reference_id": voice_id,
        "format":       "mp3",
        "mp3_bitrate":  bitrate,
        "normalize":    True,
        "latency":      latency,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(FISH_AUDIO_URL, json=payload, headers=headers)
        if resp.status_code == 402:
            logger.warning("Fish Audio: 402 Payment Required (insufficient balance)")
            return None
        if resp.status_code != 200:
            logger.warning(
                "Fish Audio %s: %s", resp.status_code, resp.text[:200],
            )
            return None
        body = resp.content
        if len(body) < _MIN_VALID_BYTES:
            logger.warning("Fish Audio: ответ слишком короткий (%d байт)", len(body))
            return None
        return body
    except httpx.TimeoutException:
        logger.warning("Fish Audio timeout")
        return None
    except Exception:  # noqa: BLE001
        logger.exception("Fish Audio synthesize failed")
        return None
