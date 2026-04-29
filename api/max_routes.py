"""HTTP routes для интеграции с Max messenger.

Эндпоинты:
  POST /api/max/webhook       — Max API → нам (события bot_started, message_created)
  GET  /api/max/status        — фронт спрашивает: привязан ли identity?
                                  возвращает {linked, prefs, deeplink}
  POST /api/max/prefs         — обновить prefs текущего identity
  POST /api/max/unlink        — отвязать (удалить подписку)

Без auth — identity достаточно (anon UUID на стороне клиента).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from db.jarvis_max_queries import (
    delete_subscription, get_by_identity, update_prefs, upsert_subscription,
)
from notify import max_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/max", tags=["max"])


# ---------------------------------------------------------------------------
# Webhook от Max API
# ---------------------------------------------------------------------------

@router.post("/webhook")
async def max_webhook(request: Request) -> dict:
    """Max шлёт сюда события. Поддерживаем bot_started для привязки и
    message_created (просто log, отвечаем приветствием)."""
    try:
        event = await request.json()
    except Exception:  # noqa: BLE001
        return {"ok": False, "reason": "bad json"}

    if not isinstance(event, dict):
        return {"ok": False}

    update_type = event.get("update_type") or ""

    # 1) bot_started — пользователь только что нажал «Старт» в Max
    if update_type == "bot_started":
        parsed = max_client.parse_bot_started(event)
        if not parsed:
            return {"ok": False, "reason": "cannot parse bot_started"}
        chat_id = parsed["chat_id"]
        identity = max_client.extract_identity_from_payload(parsed["payload"])
        if not identity:
            # Без identity (например, пользователь нашёл бота в поиске и нажал
            # старт вне deeplink'а) — отвечаем подсказкой и не привязываем.
            await max_client.send_message(
                chat_id,
                "Привет! Чтобы Джарвис писал именно вам, "
                "нажмите кнопку «Привязать Max» в виджете на сайте.",
            )
            return {"ok": True, "linked": False}
        await upsert_subscription(
            identity=identity, max_chat_id=chat_id,
            user_name=parsed.get("user_name") or None,
        )
        await max_client.send_message(
            chat_id,
            "Связь установлена. Я буду писать сюда о критичных событиях "
            "по городу. Настройки уведомлений — в виджете на сайте.",
        )
        return {"ok": True, "linked": True}

    # 2) message_created — пользователь пишет боту
    if update_type == "message_created":
        msg = event.get("message") or {}
        chat_id = msg.get("recipient", {}).get("chat_id") or msg.get("chat_id")
        text = (msg.get("body") or {}).get("text") or msg.get("text") or ""
        if chat_id and text:
            # Простой echo с подсказкой — голосового диалога через Max
            # пока нет, основное — нотификации.
            await max_client.send_message(
                chat_id,
                "Я слышу вас. Полный диалог удобнее голосом в виджете "
                "на сайте, а сюда я присылаю только важные события.",
            )
        return {"ok": True}

    return {"ok": True, "ignored": update_type}


# ---------------------------------------------------------------------------
# Endpoints для фронта (привязка / prefs)
# ---------------------------------------------------------------------------

class PrefsIn(BaseModel):
    identity: str = Field(..., min_length=16, max_length=80)
    prefs: Dict[str, bool]


class IdentityIn(BaseModel):
    identity: str = Field(..., min_length=16, max_length=80)


@router.get("/status")
async def max_status(identity: str = "") -> dict:
    """Состояние привязки + deeplink для подписки.

    Если идентифицируется как привязанный — возвращаем prefs,
    иначе deeplink на бота (если configured).
    """
    if not identity or len(identity) < 16:
        return {
            "configured": max_client.is_configured(),
            "linked":     False,
            "deeplink":   None,
            "prefs":      None,
        }
    sub = await get_by_identity(identity)
    return {
        "configured": max_client.is_configured(),
        "bot_username": max_client.bot_username(),
        "linked":      sub is not None,
        "user_name":   sub.get("user_name") if sub else None,
        "prefs":       sub.get("prefs") if sub else None,
        "deeplink":    max_client.deeplink_for(identity)
                       if not sub and max_client.is_configured()
                       else None,
    }


@router.post("/prefs")
async def max_update_prefs(payload: PrefsIn) -> dict:
    ok = await update_prefs(payload.identity, payload.prefs)
    if not ok:
        raise HTTPException(status_code=404, detail="Подписка не найдена.")
    sub = await get_by_identity(payload.identity)
    return {"ok": True, "prefs": sub.get("prefs") if sub else None}


@router.post("/unlink")
async def max_unlink(payload: IdentityIn) -> dict:
    ok = await delete_subscription(payload.identity)
    return {"ok": bool(ok)}
