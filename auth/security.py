"""Password hashing + session-token utilities.

Uses stdlib `hashlib.scrypt` for password hashing — no external deps
(passlib/bcrypt) to keep the deploy footprint tight. Parameters (n=16384,
r=8, p=1) are the suggested OWASP 2023 minimum for interactive logins.

Session tokens are 32-byte base64 URL-safe strings. We store only the
SHA-256 hash of the token in the DB, so leaking the sessions table
doesn't expose the actual cookies.

All functions are pure / testable. Storage wiring lives in `auth/store.py`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from typing import Optional, Tuple


_SCRYPT_N = 16384   # CPU/memory cost
_SCRYPT_R = 8       # block size
_SCRYPT_P = 1       # parallelisation
_SALT_BYTES = 16
_HASH_BYTES = 32


def hash_password(plain: str) -> str:
    """Return a `scrypt:<salt_b64>:<hash_b64>` string for storage."""
    if not plain:
        raise ValueError("empty password")
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.scrypt(
        plain.encode("utf-8"), salt=salt,
        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
        dklen=_HASH_BYTES,
    )
    return "scrypt:" + base64.b64encode(salt).decode("ascii") + \
           ":" + base64.b64encode(digest).decode("ascii")


def verify_password(plain: str, stored: Optional[str]) -> bool:
    """Constant-time compare `plain` against a stored `scrypt:...` string."""
    if not plain or not stored:
        return False
    try:
        scheme, salt_b64, digest_b64 = stored.split(":", 2)
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    try:
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
    except (ValueError, TypeError):
        return False
    try:
        actual = hashlib.scrypt(
            plain.encode("utf-8"), salt=salt,
            n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
            dklen=len(expected),
        )
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)


def new_session_token() -> Tuple[str, str]:
    """Return (token, token_hash) — token goes in cookie, hash into DB."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    """Return SHA-256 of a session token for DB storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    """Timing-safe equality for arbitrary strings."""
    return hmac.compare_digest(a or "", b or "")
