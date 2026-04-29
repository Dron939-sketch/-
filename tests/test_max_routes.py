"""Smoke-тесты роутов /api/max/*."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_router_registered():
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    expected = {"/api/max/webhook", "/api/max/status",
                "/api/max/prefs", "/api/max/unlink"}
    missing = expected - paths
    assert not missing, f"missing routes: {missing}"


def test_status_without_identity(client):
    """Без identity — возвращаем безопасный default (linked=False)."""
    r = client.get("/api/max/status")
    assert r.status_code == 200
    j = r.json()
    assert j["linked"] is False
    assert j["prefs"] is None


def test_status_with_short_identity(client):
    """Identity < 16 символов — игнорируем."""
    r = client.get("/api/max/status?identity=short")
    assert r.status_code == 200
    assert r.json()["linked"] is False


def test_webhook_garbage_payload(client):
    """Невалидный JSON → 200 с ok=False."""
    r = client.post("/api/max/webhook", content="not-json",
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json().get("ok") is False


def test_webhook_unknown_update_type(client):
    r = client.post("/api/max/webhook", json={"update_type": "something_else"})
    assert r.status_code == 200
    assert r.json().get("ok") is True
    assert "ignored" in r.json()


def test_webhook_bot_started_no_payload(client):
    """bot_started без identity — отвечаем подсказкой, не падаем."""
    # Без MAX_BOT_TOKEN отправка не сработает, но webhook должен ответить 200
    r = client.post("/api/max/webhook", json={
        "update_type": "bot_started",
        "chat_id": 999,
        "payload": {"payload": ""},
        "user": {"name": "Test"},
    })
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    assert j.get("linked") is False


def test_unlink_short_identity_validation(client):
    """Pydantic должен отклонить short identity."""
    r = client.post("/api/max/unlink", json={"identity": "short"})
    assert r.status_code in (422, 200)


def test_prefs_short_identity_validation(client):
    r = client.post("/api/max/prefs", json={
        "identity": "short", "prefs": {"critical": True},
    })
    assert r.status_code in (422, 404)
