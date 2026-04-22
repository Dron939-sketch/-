"""City registry.

Six pilot cities. Adding more = one entry in `CITIES` plus a matching
`CitySources` bundle in `config/sources.py`. Slugs are the stable
identifier used in URLs (`/api/city/by-slug/kolomna`).

Per the TZ, cities carry a few brand fields (emoji, accent_color) so the
frontend can render the premium city selector without hitting the DB.
"""

from __future__ import annotations

from typing import Dict, List, TypedDict


class Coordinates(TypedDict):
    lat: float
    lon: float


class CityConfig(TypedDict, total=False):
    slug: str
    name: str
    region: str
    emoji: str
    accent_color: str  # premium accent, hex
    population: int
    coordinates: Coordinates
    timezone: str
    districts: List[str]
    key_problems: List[str]
    is_pilot: bool


# ---------------------------------------------------------------------------
# Pilot — first city fully wired to TG / VK sources
# ---------------------------------------------------------------------------

KOLOMNA: CityConfig = {
    "slug": "kolomna",
    "name": "Коломна",
    "region": "Московская область",
    "emoji": "🏰",
    "accent_color": "#C5A059",
    "population": 144_589,
    "coordinates": {"lat": 55.1025, "lon": 38.7531},
    "timezone": "Europe/Moscow",
    "districts": [
        "Центральный",
        "Запрудня",
        "Голутвин",
        "Колычёво",
        "Щурово",
        "Малаховка",
        "Пески",
        "Станкостроитель",
    ],
    "key_problems": [
        "транспортная доступность до Москвы",
        "состояние дорог",
        "развитие туристической инфраструктуры",
        "благоустройство исторического центра",
    ],
    "is_pilot": True,
}


# ---------------------------------------------------------------------------
# Federal demo cities — minimal configs (no TG/VK handles yet, only RSS).
# ---------------------------------------------------------------------------

MOSKVA: CityConfig = {
    "slug": "moskva",
    "name": "Москва",
    "region": "Москва",
    "emoji": "🏙️",
    "accent_color": "#D4AF37",
    "population": 13_010_000,
    "coordinates": {"lat": 55.7558, "lon": 37.6173},
    "timezone": "Europe/Moscow",
    "districts": ["ЦАО", "САО", "СВАО", "ВАО", "ЮВАО", "ЮАО", "ЮЗАО", "ЗАО", "СЗАО", "ЗелАО", "ТиНАО"],
    "key_problems": [
        "транспортная перегрузка",
        "доступность жилья",
        "качество воздуха",
        "миграционная нагрузка",
    ],
    "is_pilot": False,
}


SPB: CityConfig = {
    "slug": "spb",
    "name": "Санкт-Петербург",
    "region": "Санкт-Петербург",
    "emoji": "🏛️",
    "accent_color": "#C5A059",
    "population": 5_600_000,
    "coordinates": {"lat": 59.9311, "lon": 30.3609},
    "timezone": "Europe/Moscow",
    "districts": [
        "Центральный", "Адмиралтейский", "Василеостровский", "Петроградский",
        "Выборгский", "Калининский", "Московский", "Невский", "Приморский",
    ],
    "key_problems": [
        "состояние исторической застройки",
        "паводки и уровень воды",
        "транспортная связность окраин",
        "туристическая нагрузка на центр",
    ],
    "is_pilot": False,
}


KAZAN: CityConfig = {
    "slug": "kazan",
    "name": "Казань",
    "region": "Республика Татарстан",
    "emoji": "🕌",
    "accent_color": "#C5A059",
    "population": 1_300_000,
    "coordinates": {"lat": 55.7961, "lon": 49.1064},
    "timezone": "Europe/Moscow",
    "districts": ["Вахитовский", "Кировский", "Московский", "Ново-Савиновский", "Приволжский", "Советский", "Авиастроительный"],
    "key_problems": [
        "развитие IT-кластера",
        "туристическая инфраструктура",
        "межконфессиональный диалог",
        "экология Волги",
    ],
    "is_pilot": False,
}


EKATERINBURG: CityConfig = {
    "slug": "ekaterinburg",
    "name": "Екатеринбург",
    "region": "Свердловская область",
    "emoji": "⛰️",
    "accent_color": "#C5A059",
    "population": 1_540_000,
    "coordinates": {"lat": 56.8389, "lon": 60.6057},
    "timezone": "Asia/Yekaterinburg",
    "districts": ["Верх-Исетский", "Железнодорожный", "Кировский", "Ленинский", "Октябрьский", "Орджоникидзевский", "Чкаловский"],
    "key_problems": [
        "реиндустриализация промзон",
        "качество воздуха",
        "транспортное кольцо",
        "городская среда центра",
    ],
    "is_pilot": False,
}


NOVOSIBIRSK: CityConfig = {
    "slug": "novosibirsk",
    "name": "Новосибирск",
    "region": "Новосибирская область",
    "emoji": "🌨️",
    "accent_color": "#C5A059",
    "population": 1_635_000,
    "coordinates": {"lat": 55.0084, "lon": 82.9357},
    "timezone": "Asia/Novosibirsk",
    "districts": ["Центральный", "Железнодорожный", "Заельцовский", "Калининский", "Кировский", "Ленинский", "Октябрьский", "Первомайский", "Советский", "Дзержинский"],
    "key_problems": [
        "транспортный каркас",
        "развитие Академгородка",
        "ЖКХ в зимний период",
        "демография и миграция",
    ],
    "is_pilot": False,
}


CITIES: Dict[str, CityConfig] = {
    KOLOMNA["name"]: KOLOMNA,
    MOSKVA["name"]: MOSKVA,
    SPB["name"]: SPB,
    KAZAN["name"]: KAZAN,
    EKATERINBURG["name"]: EKATERINBURG,
    NOVOSIBIRSK["name"]: NOVOSIBIRSK,
}


def get_city(name: str) -> CityConfig:
    """Look up a city by its Russian name (raises KeyError if unknown)."""
    try:
        return CITIES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown city: {name!r}. Available: {list(CITIES)}") from exc


def get_city_by_slug(slug: str) -> CityConfig:
    """Look up a city by its URL slug (`kolomna`, `moskva`, ...)."""
    slug = slug.strip().lower()
    for cfg in CITIES.values():
        if cfg.get("slug") == slug:
            return cfg
    raise KeyError(f"Unknown city slug: {slug!r}")
