"""City registry — юго-восток Московской области.

Шесть пилотных городов: Коломна (основной), Луховицы, Воскресенск,
Егорьевск, Ступино, Озёры. Добавление нового города = одна запись здесь
+ соответствующий `CitySources` в `config/sources.py`.

Slugs — это стабильные идентификаторы для URL
(`/api/city/by-slug/kolomna`). Поля emoji / accent_color — для премиум-
селектора из ТЗ §4.
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
# Пилот — город, у которого полностью настроены TG / VK источники.
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
# Города-соседи — минимальные конфиги (пока только RSS Google News).
# TG / VK источники добавляются администратором при онбординге.
# ---------------------------------------------------------------------------

LUKHOVITSY: CityConfig = {
    "slug": "lukhovitsy",
    "name": "Луховицы",
    "region": "Московская область",
    "emoji": "🥒",
    "accent_color": "#C5A059",
    "population": 29_300,
    "coordinates": {"lat": 54.9639, "lon": 39.0289},
    "timezone": "Europe/Moscow",
    "districts": [
        "Центральный",
        "Военный городок",
        "Южный",
        "Красная горка",
    ],
    "key_problems": [
        "сохранение огуречного кластера",
        "транспортная доступность до Москвы и Коломны",
        "модернизация медицинской инфраструктуры",
        "благоустройство центра",
    ],
    "is_pilot": False,
}


VOSKRESENSK: CityConfig = {
    "slug": "voskresensk",
    "name": "Воскресенск",
    "region": "Московская область",
    "emoji": "⚗️",
    "accent_color": "#C5A059",
    "population": 75_200,
    "coordinates": {"lat": 55.3189, "lon": 38.6739},
    "timezone": "Europe/Moscow",
    "districts": [
        "Центральный",
        "Колыберево",
        "Москворечье",
        "Лопатинский",
        "Фосфоритный",
    ],
    "key_problems": [
        "экология после химических производств",
        "реконструкция жилого фонда",
        "создание рабочих мест",
        "транспортная связность районов",
    ],
    "is_pilot": False,
}


EGORYEVSK: CityConfig = {
    "slug": "egoryevsk",
    "name": "Егорьевск",
    "region": "Московская область",
    "emoji": "⛪",
    "accent_color": "#C5A059",
    "population": 71_000,
    "coordinates": {"lat": 55.3833, "lon": 39.0333},
    "timezone": "Europe/Moscow",
    "districts": [
        "Центральный",
        "6-й микрорайон",
        "Новый",
        "Михали",
        "Заречный",
    ],
    "key_problems": [
        "сохранение исторического центра",
        "отток молодёжи в Москву",
        "состояние дорог",
        "развитие текстильной отрасли",
    ],
    "is_pilot": False,
}


STUPINO: CityConfig = {
    "slug": "stupino",
    "name": "Ступино",
    "region": "Московская область",
    "emoji": "🏭",
    "accent_color": "#C5A059",
    "population": 64_100,
    "coordinates": {"lat": 54.8833, "lon": 38.0778},
    "timezone": "Europe/Moscow",
    "districts": [
        "Центральный",
        "Новое Ступино",
        "Приокский",
        "Малино",
        "Ситне-Щелканово",
    ],
    "key_problems": [
        "реиндустриализация промзон",
        "транспортный каркас на Каширу и Москву",
        "экология берегов Оки",
        "развитие жилых кварталов",
    ],
    "is_pilot": False,
}


OZYORY: CityConfig = {
    "slug": "ozyory",
    "name": "Озёры",
    "region": "Московская область",
    "emoji": "💧",
    "accent_color": "#C5A059",
    "population": 24_200,
    "coordinates": {"lat": 54.8522, "lon": 38.5544},
    "timezone": "Europe/Moscow",
    "districts": [
        "Центральный",
        "Посёлок 1 Мая",
        "Бояркино",
        "Кудрявцево",
    ],
    "key_problems": [
        "туристический потенциал берегов Оки",
        "дороги и транспорт до райцентров",
        "отток молодёжи",
        "благоустройство набережных",
    ],
    "is_pilot": False,
}


CITIES: Dict[str, CityConfig] = {
    KOLOMNA["name"]: KOLOMNA,
    LUKHOVITSY["name"]: LUKHOVITSY,
    VOSKRESENSK["name"]: VOSKRESENSK,
    EGORYEVSK["name"]: EGORYEVSK,
    STUPINO["name"]: STUPINO,
    OZYORY["name"]: OZYORY,
}


def get_city(name: str) -> CityConfig:
    """Look up a city by its Russian name (raises KeyError if unknown)."""
    try:
        return CITIES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown city: {name!r}. Available: {list(CITIES)}") from exc


def get_city_by_slug(slug: str) -> CityConfig:
    """Look up a city by its URL slug (`kolomna`, `lukhovitsy`, ...)."""
    slug = slug.strip().lower()
    for cfg in CITIES.values():
        if cfg.get("slug") == slug:
            return cfg
    raise KeyError(f"Unknown city slug: {slug!r}")
