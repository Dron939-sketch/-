"""Unit tests for the city voice generator + /api/city/{name}/voice endpoint.

Coverage:
- Rules-based fallback always returns a meaningful sentence (never empty,
  never the word "—") for any combination of (pulse, crisis_status, complaint).
- DeepSeek path is short-circuited because the test environment has no API
  key — `cli.enabled` is False and we go straight to fallback.
- The endpoint is registered and reachable (200 even with no DB, no AI key).
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("pydantic")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from ai import voice as ai_voice
from api.main import app


# ---------------------------------------------------------------------------
# Rules-based fallback
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_rules_phrase_never_empty_for_any_state():
    """Across the (pulse, crisis) grid, the fallback always produces non-empty text."""
    for pulse in (None, 0, 25, 45, 60, 85, 100):
        for crisis in (None, "ok", "watch", "attention"):
            v = _run(ai_voice.generate(
                city="TestCity", pulse=pulse, crisis_status=crisis,
            ))
            assert v.source == "rules", "no DeepSeek key → must use rules"
            assert v.phrase, f"empty phrase for pulse={pulse} crisis={crisis}"
            assert len(v.phrase) <= 240, "phrase exceeds hard cap"
            assert v.phrase.strip() != "—"


def test_rules_phrase_uses_complaint_when_attention():
    v = _run(ai_voice.generate(
        city="X", pulse=40, crisis_status="attention",
        top_complaint="Прорыв трубы в Колычёво",
    ))
    assert "колычёво" in v.phrase.lower(), \
        "attention status should surface the complaint to the mayor"


def test_rules_phrase_uses_praise_when_high_pulse_and_calm():
    v = _run(ai_voice.generate(
        city="X", pulse=85, crisis_status="ok",
        top_praise="открыт новый парк",
    ))
    # Praise should appear (case-insensitive, may be lowercased).
    assert "парк" in v.phrase.lower()


def test_rules_phrase_warns_on_low_pulse_without_crisis():
    v = _run(ai_voice.generate(
        city="X", pulse=25, crisis_status="ok",
    ))
    # Should signal "тревожный" / "внимани" mood without claiming crisis.
    lower = v.phrase.lower()
    assert any(w in lower for w in ("тревож", "внимани", "слаб")), \
        f"low pulse + no crisis should produce a watchful tone; got: {v.phrase}"


# ---------------------------------------------------------------------------
# Endpoint smoke
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_voice_endpoint_registered():
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/city/{name}/voice" in paths


def test_voice_endpoint_returns_200_without_db(client):
    """Even with no DB and no AI key, the endpoint must return a valid payload."""
    r = client.get("/api/city/Коломна/voice")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["city"] == "Коломна"
    assert body["phrase"], "phrase must never be empty"
    assert body["source"] in ("ai", "rules")


def test_voice_endpoint_unknown_city_404(client):
    r = client.get("/api/city/CityThatDoesNotExist/voice")
    assert r.status_code == 404
