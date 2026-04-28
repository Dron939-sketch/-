"""Человекочитаемые метки для usage-событий.

Две независимых функции:

  humanize_path(method, path) → str
      Превращает технический URL вида ``/api/city/Коломна/agenda`` в
      «📋 Открыл повестку дня». Использует regex-маппинг + fallback
      на сырой путь, если паттерн не подошёл.

  device_from_user_agent(ua) → dict
      Парсит User-Agent и возвращает ``{'device': 'mobile', 'os': 'iOS',
      'browser': 'Safari', 'label': '📱 iPhone · Safari'}``. Для пустого
      / неизвестного UA — ``{'device': 'unknown', 'label': 'Неизвестно'}``.

Без внешних зависимостей (никаких ua-parser/woothee) — простой
эвристический парсер, покрывающий 95% реального трафика.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Path → русская метка
# ---------------------------------------------------------------------------

# Список (regex, label). Первый матч выигрывает. Регулярки строят
# вокруг ровного `/api/...` — параметр `name` нормализуется к [^/]+.
_PATH_RULES: List[Tuple[re.Pattern, str]] = [
    # Города + базовые витрины
    (re.compile(r"^/$"),                                       "🏠 Главная страница"),
    (re.compile(r"^/index\.html$"),                            "🏠 Главная страница"),
    (re.compile(r"^/admin\.html$"),                            "⚙️ Админ-панель"),
    (re.compile(r"^/deputies\.html$"),                         "🏛 Совет депутатов"),
    (re.compile(r"^/api/cities$"),                             "📋 Список городов"),
    (re.compile(r"^/api/city/[^/]+/all_metrics$"),             "📊 Сводные метрики города"),
    (re.compile(r"^/api/city/[^/]+/pulse$"),                   "💓 Пульс города"),
    (re.compile(r"^/api/city/[^/]+/agenda$"),                  "📋 Повестка дня"),
    (re.compile(r"^/api/city/[^/]+/news"),                     "📰 Новости города"),
    (re.compile(r"^/api/city/[^/]+/history"),                  "📈 История метрик"),
    (re.compile(r"^/api/city/[^/]+/forecast"),                 "🔮 Прогноз"),
    (re.compile(r"^/api/city/[^/]+/deep_forecast"),            "🔮 Глубокий прогноз"),
    (re.compile(r"^/api/city/[^/]+/crisis"),                   "🚨 Кризис-радар"),
    (re.compile(r"^/api/city/[^/]+/reputation"),               "🪞 Репутация"),
    (re.compile(r"^/api/city/[^/]+/investment"),               "💼 Инвестиции"),
    (re.compile(r"^/api/city/[^/]+/topics"),                   "🗂 Темы повестки"),
    (re.compile(r"^/api/city/[^/]+/market_gaps"),              "🛒 Дыры рынка"),
    (re.compile(r"^/api/city/[^/]+/decisions"),                "✅ Решения"),
    (re.compile(r"^/api/city/[^/]+/tasks"),                    "📝 Задачи"),
    (re.compile(r"^/api/city/[^/]+/eisenhower"),               "🎯 Матрица Эйзенхауэра"),
    (re.compile(r"^/api/city/[^/]+/happiness_events"),         "🎉 События счастья"),
    (re.compile(r"^/api/city/[^/]+/model$"),                   "🧠 Граф Мейстера"),
    (re.compile(r"^/api/benchmark"),                           "📊 Сравнение городов"),
    # Сценарии и действия (модалки в шапке)
    (re.compile(r"^/api/city/[^/]+/scenario$"),                "🎯 Сценарное моделирование"),
    (re.compile(r"^/api/city/[^/]+/actions$"),                 "✓ Генератор действий"),
    (re.compile(r"^/api/city/[^/]+/roadmap$"),                 "🗺 Дорожная карта"),
    # Депутаты
    (re.compile(r"^/api/city/[^/]+/deputies$"),                "🏛 Список депутатов"),
    (re.compile(r"^/api/city/[^/]+/deputies/\d+/profile$"),    "👤 Карточка депутата"),
    (re.compile(r"^/api/city/[^/]+/deputies/\d+$"),            "🏛 Изменение депутата"),
    (re.compile(r"^/api/city/[^/]+/deputy-topics/auto-generate$"), "⚡ Авто-генерация тем"),
    (re.compile(r"^/api/city/[^/]+/deputy-topics/\d+/draft$"), "✍️ Черновик публикации"),
    (re.compile(r"^/api/city/[^/]+/deputy-topics/\d+/posts$"), "📝 Регистрация поста"),
    (re.compile(r"^/api/city/[^/]+/deputy-topics/\d+/assign$"),"👥 Назначение депутатов"),
    (re.compile(r"^/api/city/[^/]+/deputy-topics/\d+/status$"),"🏷 Смена статуса темы"),
    (re.compile(r"^/api/city/[^/]+/deputy-topics/\d+$"),       "🗂 Детали темы"),
    (re.compile(r"^/api/city/[^/]+/deputy-topics$"),           "🗂 Темы депутатов"),
    (re.compile(r"^/api/city/[^/]+/deputy-coverage"),          "📈 Покрытие соц-повестки"),
    (re.compile(r"^/api/city/[^/]+/deputy-dashboard"),         "🏛 Сводка координатора"),
    # Auth
    (re.compile(r"^/api/auth/login"),                          "🔐 Вход"),
    (re.compile(r"^/api/auth/logout"),                         "🚪 Выход"),
    (re.compile(r"^/api/auth/register"),                       "📝 Регистрация"),
    (re.compile(r"^/api/auth/me"),                             "👤 Профиль"),
    (re.compile(r"^/api/auth/refresh"),                        "🔄 Продление сессии"),
    # Admin
    (re.compile(r"^/api/admin/stats/summary"),                 "📊 Сводка использования"),
    (re.compile(r"^/api/admin/stats/users"),                   "👥 Топ пользователей"),
    (re.compile(r"^/api/admin/stats/endpoints"),               "🗂 Топ разделов"),
    (re.compile(r"^/api/admin/stats/daily"),                   "📅 Дневной график"),
    (re.compile(r"^/api/admin/stats/anonymous"),               "🕵 Анонимные посетители"),
    (re.compile(r"^/api/admin/stats/user/\d+"),                "👤 Лента пользователя"),
    (re.compile(r"^/api/admin/vk_discover"),                   "🔍 Поиск VK-групп"),
    (re.compile(r"^/api/admin/collect"),                       "🔄 Ручной сбор"),
    # Health
    (re.compile(r"^/health"),                                  "❤️ Проверка"),
]


def humanize_path(method: str, path: str) -> str:
    """Возвращает человекочитаемую метку или сырой путь, если правила нет."""
    if not path:
        return ""
    for rx, label in _PATH_RULES:
        if rx.match(path):
            return label
    return path


# ---------------------------------------------------------------------------
# User-Agent → устройство / ОС / браузер
# ---------------------------------------------------------------------------

_OS_RULES: List[Tuple[re.Pattern, str, str]] = [
    # (regex, os_name, default_device_if_no_other_signal)
    (re.compile(r"iPhone", re.I),                              "iOS",       "mobile"),
    (re.compile(r"iPad", re.I),                                "iPadOS",    "tablet"),
    (re.compile(r"Android", re.I),                             "Android",   "mobile"),
    (re.compile(r"Windows Phone", re.I),                       "WinPhone",  "mobile"),
    (re.compile(r"Mac OS X|Macintosh", re.I),                  "macOS",     "desktop"),
    (re.compile(r"Windows NT", re.I),                          "Windows",   "desktop"),
    (re.compile(r"X11.*Linux|Ubuntu|Fedora", re.I),            "Linux",     "desktop"),
    (re.compile(r"CrOS", re.I),                                "ChromeOS",  "desktop"),
]

_BROWSER_RULES: List[Tuple[re.Pattern, str]] = [
    # Order matters — Yandex/Edge/Opera спрятаны внутри Chrome UA, ловим раньше.
    (re.compile(r"YaBrowser/", re.I),                          "Яндекс.Браузер"),
    (re.compile(r"Edg(e|A|iOS)?/", re.I),                      "Edge"),
    (re.compile(r"OPR/|Opera/", re.I),                         "Opera"),
    (re.compile(r"FxiOS/|Firefox/", re.I),                     "Firefox"),
    (re.compile(r"CriOS/|Chrome/", re.I),                      "Chrome"),
    (re.compile(r"Version/.*Safari/", re.I),                   "Safari"),
    (re.compile(r"Telegram", re.I),                            "Telegram WebView"),
    (re.compile(r"VK\b|VKAndroid|com\.vkontakte", re.I),       "VK WebView"),
    (re.compile(r"curl|wget|python-requests|httpx|aiohttp", re.I), "Бот / curl"),
]

# Разрешённые табы — для меньшего lable.
_DEVICE_EMOJI = {"mobile": "📱", "tablet": "📱", "desktop": "💻", "bot": "🤖", "unknown": "❔"}
_DEVICE_LABEL_RU = {"mobile": "Мобильный", "tablet": "Планшет", "desktop": "Десктоп",
                    "bot": "Бот", "unknown": "Неизвестно"}


def device_from_user_agent(ua: str | None) -> Dict[str, str]:
    """Эвристический парсер UA. Возвращает device/os/browser/label."""
    if not ua:
        return {"device": "unknown", "os": "—", "browser": "—",
                "label": _DEVICE_LABEL_RU["unknown"]}

    ua_lower = ua.lower()

    # 1. Браузер
    browser = "—"
    for rx, name in _BROWSER_RULES:
        if rx.search(ua):
            browser = name
            break

    # 2. ОС + базовый device-type
    os_name = "—"
    device = "unknown"
    for rx, oname, default_device in _OS_RULES:
        if rx.search(ua):
            os_name = oname
            device = default_device
            break

    # 3. Уточнения по mobile/tablet markers
    if device == "desktop":
        if "Mobile" in ua and "iPad" not in ua:
            device = "mobile"
        elif "Tablet" in ua:
            device = "tablet"
    if browser == "Бот / curl":
        device = "bot"

    # 4. Финальная человекочитаемая метка
    emoji = _DEVICE_EMOJI.get(device, _DEVICE_EMOJI["unknown"])
    if device == "unknown":
        label = "Неизвестное устройство"
    elif os_name == "—":
        label = f"{emoji} {_DEVICE_LABEL_RU[device]}"
    elif browser == "—":
        label = f"{emoji} {os_name}"
    else:
        label = f"{emoji} {os_name} · {browser}"

    return {"device": device, "os": os_name, "browser": browser, "label": label}
