"""Environment-driven application settings.

Reads values from `.env` (or the process environment) and exposes them as a
single frozen `settings` object used across the service. Keep secrets out of
code — only the schema lives here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: List[str] | None = None) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    # --- General ---
    env: str = _env("ENV", "development")
    debug: bool = _env_bool("DEBUG", True)
    default_city: str = _env("DEFAULT_CITY", "Коломна")

    # --- API ---
    api_host: str = _env("API_HOST", "0.0.0.0")
    api_port: int = _env_int("API_PORT", 8000)
    secret_key: str = _env("SECRET_KEY", "dev-insecure-change-me")
    # Required to call POST /api/auth/register. Prevents unattended signup on
    # a public deploy — the first admin is bootstrapped by a trusted operator.
    auth_registration_code: str = _env("AUTH_REGISTRATION_CODE", "")
    # httpOnly cookie should go over HTTPS in production; dev keeps it permissive.
    cookie_secure: bool = _env("COOKIE_SECURE", "false").lower() in ("1", "true", "yes")
    # Default admin seeded on first startup (идемпотентно — если email
    # уже есть, пароль не переписывается, только роль повышается до admin).
    # ВНИМАНИЕ: дефолт оставлен только для быстрого первого входа —
    # смените пароль в Render env (DEFAULT_ADMIN_PASSWORD) после первой
    # авторизации и/или удалите из git, потому что значение будет в
    # публичной истории репозитория.
    default_admin_email: str = _env("DEFAULT_ADMIN_EMAIL", "dron939@yandex.ru")
    default_admin_password: str = _env("DEFAULT_ADMIN_PASSWORD", "10041987")
    cors_origins: List[str] = field(
        default_factory=lambda: _env_list("CORS_ORIGINS", ["*"])
    )

    # --- Database ---
    database_url: str = _env(
        "DATABASE_URL",
        "postgresql+asyncpg://citymind:citymind@localhost:5432/citymind",
    )

    # --- Redis / Celery ---
    redis_url: str = _env("REDIS_URL", "redis://localhost:6379/0")
    celery_broker_url: str = _env("CELERY_BROKER_URL", "redis://localhost:6379/1")

    # --- External APIs ---
    openweather_api_key: str = _env("OPENWEATHER_API_KEY", "")
    vk_api_token: str = _env("VK_API_TOKEN", "")
    telegram_api_id: str = _env("TELEGRAM_API_ID", "")
    telegram_api_hash: str = _env("TELEGRAM_API_HASH", "")
    telegram_session: str = _env("TELEGRAM_SESSION", "citymind")
    yandex_api_key: str = _env("YANDEX_API_KEY", "")
    deepgram_api_key: str = _env("DEEPGRAM_API_KEY", "")
    gosuslugi_api_key: str = _env("GOSUSLUGI_API_KEY", "")

    # --- DeepSeek LLM (news enrichment) ---
    deepseek_api_key: str = _env("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    deepseek_model: str = _env("DEEPSEEK_MODEL", "deepseek-chat")
    enrichment_batch_size: int = _env_int("ENRICHMENT_BATCH_SIZE", 10)
    enrichment_max_items: int = _env_int("ENRICHMENT_MAX_ITEMS", 30)
    enrichment_cache_ttl_hours: int = _env_int("ENRICHMENT_CACHE_TTL_HOURS", 24)

    # --- Collector behaviour ---
    # Demo-режим (бережный): интервалы в 2× длиннее, окна и батчи в 2×
    # меньше боевых, чтобы не сжигать токены DeepSeek и трафик API при
    # показе системы. Все значения override'ятся env'ом — на проде
    # выставляется COLLECTION_INTERVAL_MIN=30, NEWS_LOOKBACK_HOURS=24,
    # WEATHER_INTERVAL_S=3600, SNAPSHOT_INTERVAL_S=3600,
    # DEPUTY_TOPICS_INTERVAL_S=86400, ENRICHMENT_BATCH_SIZE=20.
    collection_interval_minutes: int = _env_int("COLLECTION_INTERVAL_MIN", 960)  # 16ч (×4 от 240)
    news_lookback_hours: int = _env_int("NEWS_LOOKBACK_HOURS", 12)

    # --- ML ---
    sentiment_model: str = _env(
        "SENTIMENT_MODEL", "blanchefort/rubert-base-cased-sentiment"
    )


settings = Settings()
