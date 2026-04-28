"""HTTP routes for login / logout / registration / profile."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from auth import (
    SESSION_TTL_HOURS,
    authenticate,
    create_session,
    create_user,
    get_user_by_email,
    get_user_by_token,
    revoke_session,
)
from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE_NAME = "citymind_session"
_COOKIE_MAX_AGE = SESSION_TTL_HOURS * 3600


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=200)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=200)
    full_name: Optional[str] = Field(None, max_length=120)
    registration_code: str = Field(..., min_length=1, max_length=200)
    role: str = Field("viewer", pattern="^(viewer|editor|admin)$")


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------

def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/login")
async def login(payload: LoginRequest, response: Response) -> dict:
    user = await authenticate(payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Неверный email или пароль.")

    token = await create_session(user["id"])
    if token is None:
        # DB down — we can't persist the session. Surface as 503 rather than 500.
        raise HTTPException(status_code=503, detail="База недоступна, попробуйте позже.")

    _set_session_cookie(response, token)
    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user.get("full_name"),
        "role": user.get("role"),
    }


@router.post("/logout")
async def logout(
    response: Response,
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> dict:
    if session_token:
        await revoke_session(session_token)
    _clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/me")
async def me(
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> dict:
    if not session_token:
        return {"authenticated": False}
    user = await get_user_by_token(session_token)
    if user is None:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "id": user["id"],
        "email": user["email"],
        "full_name": user.get("full_name"),
        "role": user.get("role"),
    }


@router.post("/register")
async def register(payload: RegisterRequest, response: Response) -> dict:
    """Bootstrap user registration, gated by AUTH_REGISTRATION_CODE env."""
    expected_code = settings.auth_registration_code
    if not expected_code:
        raise HTTPException(
            status_code=403,
            detail="Регистрация отключена (AUTH_REGISTRATION_CODE не задан).",
        )
    if payload.registration_code != expected_code:
        # Sleep a bit to discourage brute force — асинк, не блокирующий.
        import asyncio
        await asyncio.sleep(0.5)
        raise HTTPException(status_code=403, detail="Неверный код регистрации.")

    existing = await get_user_by_email(payload.email)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Пользователь с таким email уже существует.")

    created = await create_user(
        payload.email,
        payload.password,
        full_name=payload.full_name,
        role=payload.role,
    )
    if created is None:
        raise HTTPException(status_code=503, detail="Не удалось создать пользователя (БД).")

    # Auto-login after registration.
    token = await create_session(created["id"])
    if token is not None:
        _set_session_cookie(response, token)
    return created


# ---------------------------------------------------------------------------
# FastAPI dependency for gating routes
# ---------------------------------------------------------------------------

async def require_user(
    request: Request,
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> dict:
    """Return the authenticated user or raise 401.

    Usage:
        @router.post("/protected")
        async def handler(user = Depends(require_user)):
            ...
    """
    if not session_token:
        raise HTTPException(status_code=401, detail="Требуется авторизация.")
    user = await get_user_by_token(session_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Сессия истекла или недействительна.")
    return user


def require_role(*allowed_roles: str):
    """Factory: returns a dependency that allows only specified roles."""

    async def _dep(user: dict = None) -> dict:
        # user is filled by require_user via Depends chain
        from fastapi import Depends  # noqa: F401 — imported for clarity
        return user

    # Actual implementation uses a wrapper since FastAPI Depends chaining
    # is simpler when we just check the role inline after require_user.
    async def checker(
        session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    ) -> dict:
        if not session_token:
            raise HTTPException(status_code=401, detail="Требуется авторизация.")
        user = await get_user_by_token(session_token)
        if user is None:
            raise HTTPException(status_code=401, detail="Сессия истекла.")
        if user.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Недостаточно прав.")
        return user

    return checker
