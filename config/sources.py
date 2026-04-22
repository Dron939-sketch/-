"""Source registry for data collectors.

Maps city name → list of sources for Telegram, VK, News RSS and
Gosuslugi. Entries are annotated with a priority (P0/P1/P2) so collectors can
back off gracefully under rate limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class Source:
    kind: str  # "telegram" | "vk" | "news_rss" | "gosuslugi"
    name: str
    handle: str  # channel username, public id, or URL
    category: str  # "official" | "city" | "incidents" | "complaints" | ...
    priority: str = "P1"  # "P0" | "P1" | "P2"
    notes: str = ""


@dataclass(frozen=True)
class CitySources:
    telegram: List[Source] = field(default_factory=list)
    vk: List[Source] = field(default_factory=list)
    news_rss: List[Source] = field(default_factory=list)
    gosuslugi: List[Source] = field(default_factory=list)


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
        # Google News ru RSS — живой публичный фид без ключей. Старый
        # https://news.yandex.ru/Kolomna/index.rss ушёл в Дзен и отвечает
        # таймаутом, поэтому заменён на Google News.
        Source(
            "news_rss",
            "Google News — Коломна",
            "https://news.google.com/rss/search?q=%D0%9A%D0%BE%D0%BB%D0%BE%D0%BC%D0%BD%D0%B0&hl=ru&gl=RU&ceid=RU:ru",
            "news",
            "P1",
        ),
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


SOURCES: Dict[str, CitySources] = {
    "Коломна": KOLOMNA_SOURCES,
}


def get_sources_for_city(city_name: str) -> CitySources:
    """Return the source bundle for the given city, raising if missing."""
    try:
        return SOURCES[city_name]
    except KeyError as exc:
        raise KeyError(
            f"No sources registered for city {city_name!r}. "
            f"Known cities: {list(SOURCES)}"
        ) from exc


def iter_all_sources(city_name: str) -> List[Source]:
    """Flatten all source types into a single priority-ordered list."""
    bundle = get_sources_for_city(city_name)
    flat = [*bundle.telegram, *bundle.vk, *bundle.news_rss, *bundle.gosuslugi]
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    return sorted(flat, key=lambda s: priority_order.get(s.priority, 99))
