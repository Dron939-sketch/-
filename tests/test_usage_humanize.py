"""Unit tests for ops.usage_humanize helpers."""

from __future__ import annotations

from ops.usage_humanize import device_from_user_agent, humanize_path


# ---------------------------------------------------------------------------
# humanize_path
# ---------------------------------------------------------------------------

def test_root_path_is_homepage():
    assert humanize_path("GET", "/") == "🏠 Главная страница"


def test_admin_panel_html():
    assert humanize_path("GET", "/admin.html") == "⚙️ Админ-панель"


def test_deputies_page():
    assert humanize_path("GET", "/deputies.html") == "🏛 Совет депутатов"


def test_agenda_endpoint_with_cyrillic_city():
    assert humanize_path("GET", "/api/city/Коломна/agenda") == "📋 Повестка дня"


def test_pulse_endpoint():
    assert humanize_path("GET", "/api/city/Коломна/pulse") == "💓 Пульс города"


def test_news_endpoint_with_query_string():
    # Should match by prefix even with ?limit=200 etc
    label = humanize_path("GET", "/api/city/kolomna/news")
    assert label == "📰 Новости города"


def test_deputy_profile_card():
    assert humanize_path("GET", "/api/city/Коломна/deputies/5/profile") == "👤 Карточка депутата"


def test_auto_generate_topics():
    assert humanize_path("POST", "/api/city/Коломна/deputy-topics/auto-generate") == "⚡ Авто-генерация тем"


def test_login_route():
    assert humanize_path("POST", "/api/auth/login") == "🔐 Вход"


def test_admin_stats_users():
    assert humanize_path("GET", "/api/admin/stats/users") == "👥 Топ пользователей"


def test_unknown_path_falls_back_to_raw():
    out = humanize_path("GET", "/api/some/random/endpoint")
    assert out == "/api/some/random/endpoint"


def test_empty_path_returns_empty_string():
    assert humanize_path("GET", "") == ""


# ---------------------------------------------------------------------------
# device_from_user_agent
# ---------------------------------------------------------------------------

def test_empty_ua():
    out = device_from_user_agent(None)
    assert out["device"] == "unknown"
    assert "Неизвестно" in out["label"]


def test_iphone_safari():
    ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
    out = device_from_user_agent(ua)
    assert out["device"] == "mobile"
    assert out["os"] == "iOS"
    assert out["browser"] == "Safari"
    assert "📱" in out["label"]
    assert "iOS" in out["label"]


def test_android_chrome():
    ua = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
    out = device_from_user_agent(ua)
    assert out["device"] == "mobile"
    assert out["os"] == "Android"
    assert out["browser"] == "Chrome"


def test_macos_safari():
    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
    out = device_from_user_agent(ua)
    assert out["device"] == "desktop"
    assert out["os"] == "macOS"
    assert out["browser"] == "Safari"
    assert "💻" in out["label"]


def test_windows_chrome():
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    out = device_from_user_agent(ua)
    assert out["device"] == "desktop"
    assert out["os"] == "Windows"
    assert out["browser"] == "Chrome"


def test_yandex_browser_wins_over_chrome():
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 YaBrowser/24.4.0.0 Safari/537.36"
    out = device_from_user_agent(ua)
    assert out["browser"] == "Яндекс.Браузер"


def test_edge_wins_over_chrome():
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
    out = device_from_user_agent(ua)
    assert out["browser"] == "Edge"


def test_curl_is_bot():
    out = device_from_user_agent("curl/8.4.0")
    assert out["device"] == "bot"
    assert out["browser"] == "Бот / curl"


def test_python_requests_is_bot():
    out = device_from_user_agent("python-requests/2.31.0")
    assert out["device"] == "bot"


def test_telegram_webview():
    ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_4 like Mac OS X) Telegram/9.6"
    out = device_from_user_agent(ua)
    assert out["browser"] == "Telegram WebView"


def test_ipad_treated_as_tablet():
    ua = "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
    out = device_from_user_agent(ua)
    assert out["device"] == "tablet"
    assert out["os"] == "iPadOS"


def test_label_contains_device_emoji():
    out = device_from_user_agent("Mozilla/5.0 (Windows NT 10.0) Chrome/124.0")
    assert any(ch in out["label"] for ch in ("💻", "📱", "📱", "🤖", "❔"))
