"""Unit tests for the usage analytics layer."""

from __future__ import annotations

import pytest

from ops.usage import truncate_ip


# ---------------------------------------------------------------------------
# truncate_ip — IP privacy guard
# ---------------------------------------------------------------------------

def test_truncate_ipv4_keeps_three_octets():
    assert truncate_ip("192.168.1.42") == "192.168.1.0/24"
    assert truncate_ip("10.0.0.5") == "10.0.0.0/24"


def test_truncate_ipv6_keeps_three_groups():
    out = truncate_ip("2001:db8:1234:5678::1")
    assert out.startswith("2001:db8:1234")
    assert out.endswith("/48")


def test_truncate_ip_handles_short_ipv6():
    # Less than 3 groups → still emits a prefix string, never crashes.
    result = truncate_ip("::1")
    assert result is not None
    assert "/48" in result or "/24" in result


def test_truncate_ip_none_returns_none():
    assert truncate_ip(None) is None
    assert truncate_ip("") is None


def test_truncate_ip_whitespace_stripped():
    assert truncate_ip("  10.1.2.3  ") == "10.1.2.0/24"


def test_truncate_ip_invalid_returns_none():
    assert truncate_ip("not-an-ip") is None
    assert truncate_ip("1.2.3") is None        # only 3 parts
    assert truncate_ip("1.2.3.4.5") is None    # 5 parts


def test_truncate_ip_never_leaks_full_address():
    """Contract: output must NEVER equal the full input address."""
    for ip in ["192.168.1.42", "10.0.0.5", "255.255.255.255"]:
        assert truncate_ip(ip) != ip


def test_truncate_ip_public_ipv4_truncation_consistent():
    # Same /24 should produce the same prefix regardless of last octet.
    assert truncate_ip("203.0.113.7") == truncate_ip("203.0.113.200")
