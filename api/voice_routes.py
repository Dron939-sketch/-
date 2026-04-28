"""Голосовой помощник «Душа города».

Эндпоинты:
  POST /api/city/{name}/voice/ask       (JSON: text → reply + base64 audio)
  POST /api/city/{name}/voice/ask-audio (multipart: audio + format → STT
                                                     → reply + base64 audio)

Поток:
  1. Опционально STT (если пришло аудио).
  2. Собираем контекст города из /agenda + /all_metrics (через DB
     слоистые helpers, без HTTP-запросов внутри).
  3. Отдаём в `ai.city_soul.answer()` → текст-ответ.
  4. Опционально TTS (если у нас есть YANDEX_API_KEY).
  5. Возвращаем JSON с transcript / reply_text / reply_audio_base64.

Без auth — идея в том, что любой горожанин может «поговорить» с городом.
Если запросов будет много, добавим rate-limit.
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ai.city_soul import answer as soul_answer
from ai.voice_service import speech_to_text, text_to_speech
from config.cities import get_city, get_city_by_slug

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/city", tags=["voice"])


class VoiceAskIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=1500)
    speak: bool = Field(True, description="Включить ли TTS в ответе")


def _resolve_city(name_or_slug: str) -> Dict[str, Any]:
    try:
        return get_city(name_or_slug)
    except KeyError:
        pass
    try:
        return get_city_by_slug(name_or_slug)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


async def _build_city_context(city_name: str) -> Dict[str, Any]:
    """Собрать минимальный контекст для Души: метрики + топ-3 жалобы +
    топ-3 похвалы + погода (если есть). Все источники fail-safe.
    """
    ctx: Dict[str, Any] = {"name": city_name}
    try:
        from db.queries import latest_metrics, latest_weather
        from db.seed import city_id_by_name

        cid = await city_id_by_name(city_name)
        if cid is None:
            return ctx
        m = await latest_metrics(cid)
        if m:
            ctx["metrics"] = {
                "sb": m.get("sb"), "tf": m.get("tf"),
                "ub": m.get("ub"), "chv": m.get("chv"),
            }
        w = await latest_weather(cid)
        if w:
            ctx["weather"] = {
                "temperature": w.get("temperature"),
                "condition":   w.get("condition"),
            }
    except Exception:  # noqa: BLE001
        # БД недоступна или функций нет — ну и ладно, ответит без контекста.
        pass
    # Жалобы/похвалы — попытка через agenda. На отсутствие данных не падаем.
    try:
        from api.routes import _build_agenda  # type: ignore
        cfg = {"name": city_name}
        agenda_resp = await _build_agenda(cfg, 0.0)
        if agenda_resp:
            ctx["top_complaints"] = list(getattr(agenda_resp, "top_complaints", []) or [])[:3]
            ctx["top_praises"] = list(getattr(agenda_resp, "top_praises", []) or [])[:3]
    except Exception:  # noqa: BLE001
        pass
    return ctx


async def _make_voice_payload(reply: str, *, speak: bool) -> Dict[str, Any]:
    audio_b64: Optional[str] = None
    if speak:
        audio_bytes = await text_to_speech(reply)
        if audio_bytes:
            audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    return {
        "reply_text": reply,
        "reply_audio_base64": audio_b64,
        "audio_mime": "audio/mpeg" if audio_b64 else None,
    }


@router.post("/{name}/voice/ask")
async def voice_ask_text(name: str, payload: VoiceAskIn) -> dict:
    """Текстовый вопрос → текст + (опц.) MP3."""
    cfg = _resolve_city(name)
    ctx = await _build_city_context(cfg["name"])
    reply = await soul_answer(payload.question, ctx)
    voice = await _make_voice_payload(reply, speak=payload.speak)
    return {
        "city": cfg["name"],
        "transcript": payload.question,
        **voice,
    }


@router.post("/{name}/voice/ask-audio")
async def voice_ask_audio(
    name: str,
    audio: UploadFile = File(...),
    audio_format: str = Form("webm"),
    speak: bool = Form(True),
) -> dict:
    """Аудио вопрос → STT → ответ + (опц.) MP3.

    Защищаемся от больших файлов — > 6 MiB режутся 413, 6 MiB ≈ ~5 минут
    Opus 16kHz mono.
    """
    cfg = _resolve_city(name)
    raw = await audio.read()
    if len(raw) > 6 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Аудио слишком большое (макс 6 MB).")

    transcript = await speech_to_text(raw, audio_format=audio_format)
    if not transcript:
        # STT отвалился — отдаём вежливый ответ от души без вопроса
        reply = "Я не расслышала, повторите, пожалуйста."
        voice = await _make_voice_payload(reply, speak=speak)
        return {
            "city": cfg["name"], "transcript": None, "stt_failed": True, **voice,
        }

    ctx = await _build_city_context(cfg["name"])
    reply = await soul_answer(transcript, ctx)
    voice = await _make_voice_payload(reply, speak=speak)
    return {
        "city": cfg["name"],
        "transcript": transcript,
        **voice,
    }
