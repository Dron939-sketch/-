"""Unit tests for the pure auth utility functions."""

from __future__ import annotations

import pytest

from auth.security import (
    constant_time_equal,
    hash_password,
    hash_token,
    new_session_token,
    verify_password,
)


def test_hash_password_produces_scrypt_format():
    h = hash_password("hunter2")
    assert h.startswith("scrypt:")
    assert h.count(":") == 2


def test_verify_password_round_trip():
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h) is True


def test_verify_password_wrong_input():
    h = hash_password("one")
    assert verify_password("two", h) is False


def test_verify_password_rejects_empty_inputs():
    h = hash_password("abc")
    assert verify_password("", h) is False
    assert verify_password("abc", None) is False
    assert verify_password("abc", "") is False


def test_verify_password_rejects_malformed_stored():
    assert verify_password("abc", "not-a-scrypt-string") is False
    assert verify_password("abc", "scrypt:only-one-colon") is False
    assert verify_password("abc", "bcrypt:x:y") is False   # different scheme


def test_hash_password_different_each_call_due_to_salt():
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2
    # Both still verify the same plaintext.
    assert verify_password("same", h1) is True
    assert verify_password("same", h2) is True


def test_empty_password_rejected_at_hash():
    with pytest.raises(ValueError):
        hash_password("")


def test_new_session_token_returns_token_and_hash():
    token, hash_ = new_session_token()
    assert len(token) >= 32
    assert len(hash_) == 64   # sha256 hex digest
    assert token != hash_


def test_hash_token_deterministic():
    t = "sample-token-xyz"
    assert hash_token(t) == hash_token(t)


def test_hash_token_differs_for_different_tokens():
    assert hash_token("a") != hash_token("b")


def test_constant_time_equal():
    assert constant_time_equal("abc", "abc") is True
    assert constant_time_equal("abc", "abd") is False
    assert constant_time_equal("", "") is True
    assert constant_time_equal("x", "") is False


def test_scrypt_hash_reasonable_length():
    h = hash_password("x")
    # scrypt:base64(16)+":"+base64(32) → salt part ~24 chars, hash part ~44 chars.
    parts = h.split(":")
    assert len(parts) == 3
    assert len(parts[1]) >= 20
    assert len(parts[2]) >= 40
