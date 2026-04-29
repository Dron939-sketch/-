"""Async client для Max API (https://platform-api.max.ru).

Адаптировано из Frederick (services/bot_service.py). Поддерживает:
  - send_message(chat_id, text)        — POST /messages
  - subscribe_webhook(url)             — POST /subscriptions

ENV:
  MAX_BOT_TOKEN     — Bearer-токен бота (получается у Max через @MasterBot)
  MAX_BOT_USERNAME  — username бота (без @), для генерации deeplink
                      https://max.ru/<username>?start=web_<identity>

Все методы fail-safe: на отсутствующий токен — None / False, без
бросков. Голосовой UX никогда не должен ждать или падать из-за Max.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

MAX_API_BASE = "https://platform-api.max.ru"
_TIMEOUT_S = 10.0


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def is_configured() -> bool:
    return bool(_env("MAX_BOT_TOKEN"))


def bot_username() -> str:
    """Для генерации deeplink на фронте."""
    return _env("MAX_BOT_USERNAME", "")


def deeplink_for(identity: str) -> Optional[str]:
    """Ссылка на бота с auto-payload web_<identity>. Пользователь
    кликает → переходит в Max → нажимает «Старт» → бот получает
    bot_started с payload и привязывает identity ↔ chat_id."""
    if not identity:
        return None
    name = bot_username()
    if not name:
        return None
    return f"https://max.ru/{name}?start=web_{identity}"


async def send_message(chat_id: str, text: str) -> bool:
    """Отправить текст в чат бота. True/False — успех."""
    token = _env("MAX_BOT_TOKEN")
    if not token or not chat_id or not text:
        return False
    url = f"{MAX_API_BASE}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }
    params = {"chat_id": str(chat_id)}
    payload = {"text": text[:4000]}
    try:
        timeout = aiohttp.ClientTimeout(total=_TIMEOUT_S)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                url, headers=headers, params=params, json=payload,
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.warning("Max send_message %s: %s", resp.status, body[:200])
                    return False
                return True
    except Exception:  # noqa: BLE001
        logger.exception("Max send_message exception")
        return False


async def subscribe_webhook(webhook_url: str) -> bool:
    """Подписать бота на webhook. Вызывается один раз при старте
    приложения в production. Если приложение не доступно по HTTPS —
    Max откажет."""
    token = _env("MAX_BOT_TOKEN")
    if not token or not webhook_url:
        return False
    url = f"{MAX_API_BASE}/subscriptions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }
    payload = {"url": webhook_url, "version": "0.0.1"}
    try:
        timeout = aiohttp.ClientTimeout(total=_TIMEOUT_S)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.warning("Max subscribe_webhook %s: %s", resp.status, body[:200])
                    return False
                return True
    except Exception:  # noqa: BLE001
        logger.exception("Max subscribe_webhook exception")
        return False


async def broadcast(chat_ids: List[str], text: str) -> int:
    """Разослать одно и то же сообщение списку чатов. Возвращает
    количество успешных отправок. Sequential (Max API не любит
    параллельные запросы от одного бота — могут прилететь rate-limit'ы)."""
    if not chat_ids or not text:
        return 0
    sent = 0
    for cid in chat_ids:
        if await send_message(cid, text):
            sent += 1
    return sent


# ---------------------------------------------------------------------------
# Helpers для обработки webhook payload
# ---------------------------------------------------------------------------

def parse_bot_started(event: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """Из webhook-event с update_type=bot_started достать
    {chat_id, payload, user_name}.

    Согласно Max-API формату:
      event.update_type == "bot_started"
      event.chat_id или event.payload.chat_id
      event.payload.payload — строка с deeplink-payload (web_<identity>)
      event.user.name — имя пользователя
    """
    if not isinstance(event, dict):
        return None
    if event.get("update_type") != "bot_started":
        return None
    chat_id = event.get("chat_id")
    if chat_id is None:
        chat_id = (event.get("payload") or {}).get("chat_id")
    if chat_id is None:
        return None
    payload = (event.get("payload") or {}).get("payload") or event.get("start_payload") or ""
    user = event.get("user") or {}
    user_name = user.get("name") or user.get("first_name") or ""
    return {
        "chat_id":   str(chat_id),
        "payload":   str(payload),
        "user_name": str(user_name)[:120],
    }


def extract_identity_from_payload(payload: str) -> Optional[str]:
    """payload = "web_<identity>" → "<identity>". Иначе None."""
    if not payload or not isinstance(payload, str):
        return None
    s = payload.strip()
    prefix = "web_"
    if not s.startswith(prefix):
        return None
    identity = s[len(prefix):].strip()
    if 16 <= len(identity) <= 80:
        return identity
    return None
