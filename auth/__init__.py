"""Authentication: email+password login + session cookies + middleware."""

from .security import (
    constant_time_equal,
    hash_password,
    hash_token,
    new_session_token,
    verify_password,
)
from .store import (
    SESSION_TTL_HOURS,
    authenticate,
    create_session,
    create_user,
    get_user_by_email,
    get_user_by_token,
    purge_expired_sessions,
    revoke_session,
)

__all__ = [
    # security
    "hash_password", "verify_password", "hash_token",
    "new_session_token", "constant_time_equal",
    # store
    "get_user_by_email", "create_user", "authenticate",
    "create_session", "get_user_by_token", "revoke_session",
    "purge_expired_sessions", "SESSION_TTL_HOURS",
]
