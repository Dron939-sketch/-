"""City-specific data.

Coordinates, districts and pre-identified key problems for each supported
city. Kolomna is the pilot city per the project spec. Adding a new city
requires only extending `CITIES` and the matching entries in
`config/sources.py`.
"""

from __future__ import annotations

from typing import Dict, List, TypedDict


class Coordinates(TypedDict):
    lat: float
    lon: float


class CityConfig(TypedDict):
    name: str
    region: str
    population: int
    coordinates: Coordinates
    timezone: str
    districts: List[str]
    key_problems: List[str]


KOLOMNA: CityConfig = {
    "name": "Коломна",
    "region": "Московская область",
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
}


CITIES: Dict[str, CityConfig] = {
    "Коломна": KOLOMNA,
}


def get_city(name: str) -> CityConfig:
    """Return a city config by its Russian name (raises KeyError if unknown)."""
    try:
        return CITIES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown city: {name!r}. Available: {list(CITIES)}") from exc
