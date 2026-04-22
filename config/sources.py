"""Source registry for data collectors.

Pilot city Kolomna has a full set of TG / VK / RSS sources. Other cities
start with just a Google News RSS feed — administrators plug in TG / VK
handles as we roll out per-city onboarding (TZ §4.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class Source:
    kind: str  # "telegram" | "vk" | "news_rss" | "gosuslugi"
    name: str
    handle: str
    category: str
    priority: str = "P1"
    notes: str = ""


@dataclass(frozen=True)
class CitySources:
    telegram: List[Source] = field(default_factory=list)
    vk: List[Source] = field(default_factory=list)
    news_rss: List[Source] = field(default_factory=list)
    gosuslugi: List[Source] = field(default_factory=list)


def _google_news_rss(city_ru: str, query_encoded: str) -> Source:
    """Google News RSS feed for an arbitrary Russian-language query."""
    url = (
        f"https://news.google.com/rss/search?q={query_encoded}"
        "&hl=ru&gl=RU&ceid=RU:ru"
    )
    return Source("news_rss", f"Google News — {city_ru}", url, "news", "P1")


KOLOMNA_SOURCES = CitySources(
    telegram=[
        Source("telegram", "Администрация Коломны", "gorodkolomna", "official", "P0"),
        Source("telegram", "Коломна LIVE", "kolomna_live", "city", "P0"),
        Source("telegram", "ЧП Коломна", "kolomna_chp", "incidents", "P0"),
        Source("telegram", "Подслушано Коломна", "kolomna_overs", "complaints", "P0"),
        Source("telegram", "Коломна. Новости", "kolomna_news", "news", "P1"),
        Source("telegram", "Коломна Транспорт", "kolomna_transport", "transport", "P1"),
        Source("telegram", "Коломна ЖКХ", "kolomna_zhkh", "utilities", "P1"),
        Source("telegram", "Культура Коломна", "kolomna_culture", "culture", "P2"),
        Source("telegram", "Спорт Коломна", "kolomna_sport", "sport", "P2"),
        Source("telegram", "Бизнес Коломна", "kolomna_business", "business", "P2"),
    ],
    vk=[
        Source("vk", "Типичная Коломна", "typical_kolomna", "complaints", "P0"),
        Source("vk", "Коломна Сегодня", "kolomna_today", "news", "P0"),
        Source("vk", "Администрация Коломны", "kolomna_adm", "official", "P0"),
        Source("vk", "Коломна 360", "kolomna360", "city", "P1"),
        Source("vk", "Коломна Онлайн", "kolomna_online", "news", "P1"),
    ],
    news_rss=[
        _google_news_rss("Коломна", "%D0%9A%D0%BE%D0%BB%D0%BE%D0%BC%D0%BD%D0%B0"),
    ],
    gosuslugi=[
        Source(
            "gosuslugi",
            "Обращения граждан Коломны",
            "kolomna",
            "appeals",
            "P2",
            notes="Нужен ключ API; пока используется stub-коллектор.",
        ),
    ],
)

MOSKVA_SOURCES = CitySources(
    news_rss=[_google_news_rss("Москва", "%D0%9C%D0%BE%D1%81%D0%BA%D0%B2%D0%B0")],
)

SPB_SOURCES = CitySources(
    news_rss=[
        _google_news_rss(
            "Санкт-Петербург",
            "%D0%A1%D0%B0%D0%BD%D0%BA%D1%82-%D0%9F%D0%B5%D1%82%D0%B5%D1%80%D0%B1%D1%83%D1%80%D0%B3",
        )
    ],
)

KAZAN_SOURCES = CitySources(
    news_rss=[_google_news_rss("Казань", "%D0%9A%D0%B0%D0%B7%D0%B0%D0%BD%D1%8C")],
)

EKATERINBURG_SOURCES = CitySources(
    news_rss=[
        _google_news_rss(
            "Екатеринбург",
            "%D0%95%D0%BA%D0%B0%D1%82%D0%B5%D1%80%D0%B8%D0%BD%D0%B1%D1%83%D1%80%D0%B3",
        )
    ],
)

NOVOSIBIRSK_SOURCES = CitySources(
    news_rss=[
        _google_news_rss(
            "Новосибирск",
            "%D0%9D%D0%BE%D0%B2%D0%BE%D1%81%D0%B8%D0%B1%D0%B8%D1%80%D1%81%D0%BA",
        )
    ],
)


SOURCES: Dict[str, CitySources] = {
    "Коломна": KOLOMNA_SOURCES,
    "Москва": MOSKVA_SOURCES,
    "Санкт-Петербург": SPB_SOURCES,
    "Казань": KAZAN_SOURCES,
    "Екатеринбург": EKATERINBURG_SOURCES,
    "Новосибирск": NOVOSIBIRSK_SOURCES,
}


def get_sources_for_city(city_name: str) -> CitySources:
    try:
        return SOURCES[city_name]
    except KeyError as exc:
        raise KeyError(
            f"No sources registered for city {city_name!r}. "
            f"Known cities: {list(SOURCES)}"
        ) from exc


def iter_all_sources(city_name: str) -> List[Source]:
    bundle = get_sources_for_city(city_name)
    flat = [*bundle.telegram, *bundle.vk, *bundle.news_rss, *bundle.gosuslugi]
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    return sorted(flat, key=lambda s: priority_order.get(s.priority, 99))
