"""Smoke tests for the new home screen static assets.

Verifies:
- `/` returns the new compact index.html (hero zone present, NOT the
  legacy 24-section dashboard).
- `/full-dashboard.html` is reachable and contains the legacy widgets.
- `/home.css` and `/home.js` are served.
- Anchor IDs that the home tiles link to exist in full-dashboard.html
  (regression guard — if a tile points to #foo and #foo doesn't exist,
  the user clicks and lands at the top of the page silently).
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_root_serves_new_home(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    # New home markers
    assert 'class="home-page"' in body or 'class="home-main"' in body
    assert 'id="hero"' in body
    assert 'id="hero-pulse"' in body
    assert "/home.js" in body
    # Should NOT be the legacy 24-card dashboard
    assert 'id="crisis-strip"' not in body, \
        "/ must serve the new compact home, not the legacy dashboard"


def test_full_dashboard_reachable(client):
    r = client.get("/full-dashboard.html")
    assert r.status_code == 200
    body = r.text
    assert 'id="crisis-strip"' in body
    # Back-link to home
    assert 'href="/"' in body


def test_home_assets_served(client):
    css = client.get("/home.css")
    assert css.status_code == 200
    assert ".hero" in css.text or ".home-main" in css.text

    js = client.get("/home.js")
    assert js.status_code == 200
    assert "loadHero" in js.text or "hero-pulse" in js.text


def test_tile_anchors_exist_in_full_dashboard(client):
    """If a tile on the home points to /full-dashboard.html#foo, then #foo
    must exist there — otherwise users click and land at the page top."""
    r = client.get("/full-dashboard.html")
    body = r.text
    expected_ids = [
        "crisis-strip", "weather", "vectors-card", "model-graph",
        "trust-happy", "reputation", "investment", "happiness-events",
        "task-manager", "foresight", "benchmark", "agenda",
    ]
    for aid in expected_ids:
        assert f'id="{aid}"' in body, f"missing anchor id={aid} in full-dashboard.html"


def test_deputies_page_still_reachable(client):
    """Sanity: previous PR's standalone page wasn't broken by the restructure."""
    r = client.get("/deputies.html")
    assert r.status_code == 200
    assert "повестк" in r.text.lower() or "депутат" in r.text.lower()
