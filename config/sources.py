"""Source registry — юго-восток Московской области.

Коломна — пилот с полным набором TG / VK / RSS источников. Остальные
пять городов стартуют только с Google News RSS; администратор
подключает локальные TG-каналы и VK-паблики при онбординге
(ТЗ §4.4).
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
        Source("telegram", "Коломна-Инфо", "kolomna_info", "news", "P1"),
        Source("telegram", "Коломна Авто", "kolomna_auto", "transport", "P1"),
        Source("telegram", "Коломна ДТП", "kolomna_dtp", "incidents", "P0"),
        Source("telegram", "Коломенский кремль", "kolomna_kreml", "culture", "P2"),
    ],
    vk=[
        Source("vk", "Типичная Коломна", "typical_kolomna", "complaints", "P0"),
        Source("vk", "Коломна Сегодня", "kolomna_today", "news", "P0"),
        Source("vk", "Администрация Коломны", "kolomna_adm", "official", "P0"),
        Source("vk", "Коломна 360", "kolomna360", "city", "P1"),
        Source("vk", "Коломна Онлайн", "kolomna_online", "news", "P1"),
        # --- автомобильная повестка ---
        Source("vk", "Автомобилисты Коломны", "auto_kolomna", "transport", "P0"),
        Source("vk", "Дороги Коломны", "kolomna_roads", "transport", "P1"),
        Source("vk", "Коломенские пробки", "kolomna_probki", "transport", "P1"),
        # --- общественный транспорт ---
        Source("vk", "Коломенский троллейбус", "kolomna_trolley", "transport", "P2"),
        # --- ЖКХ и благоустройство ---
        Source("vk", "ЖКХ Коломна", "kolomna_zhkh_vk", "utilities", "P1"),
        Source("vk", "Коломна благоустройство", "kolomna_blag", "quality", "P2"),
        # --- тематические ---
        Source("vk", "МФЦ Коломны", "kolomna_mfc", "official", "P2"),
        Source("vk", "Коломна Бизнес", "kolomna_business_vk", "business", "P2"),
        Source("vk", "Мамы Коломны", "kolomna_mamas", "social", "P1"),
        Source("vk", "Коломна Спорт", "kolomna_sport_vk", "sport", "P2"),
    ],
    news_rss=[
        # Генерический поиск по слову «Коломна»
        _google_news_rss("Коломна", "%D0%9A%D0%BE%D0%BB%D0%BE%D0%BC%D0%BD%D0%B0"),
        # Тематические срезы для более точной категоризации
        _google_news_rss(
            "Коломна ДТП",
            "%D0%9A%D0%BE%D0%BB%D0%BE%D0%BC%D0%BD%D0%B0+%D0%94%D0%A2%D0%9F",
        ),
        _google_news_rss(
            "Коломна ЖКХ",
            "%D0%9A%D0%BE%D0%BB%D0%BE%D0%BC%D0%BD%D0%B0+%D0%96%D0%9A%D0%A5",
        ),
        _google_news_rss(
            "Коломна транспорт",
            "%D0%9A%D0%BE%D0%BB%D0%BE%D0%BC%D0%BD%D0%B0+%D1%82%D1%80%D0%B0%D0%BD%D1%81%D0%BF%D0%BE%D1%80%D1%82",
        ),
        _google_news_rss(
            "Коломна культура",
            "%D0%9A%D0%BE%D0%BB%D0%BE%D0%BC%D0%BD%D0%B0+%D0%BA%D1%83%D0%BB%D1%8C%D1%82%D1%83%D1%80%D0%B0",
        ),
        # Прямой RSS городского издания — подтверждён живым.
        Source(
            kind="news_rss",
            name="in-kolomna.ru (RSS)",
            handle="https://in-kolomna.ru/rss.xml",
            category="news", priority="P0",
            notes="Главное городское новостное издание.",
        ),
        # --- RSS-ленты ниже регистрировались, но возвращают 404/timeout.
        # --- Оставлены закомментированными как лог для ручного онбординга
        # --- после того как найдём рабочий endpoint (например, через
        # --- кастомный скрейпер или другой формат).
        # Source(kind="news_rss", name="kolomnagrad.ru (RSS)",
        #        handle="https://kolomnagrad.ru/rss",
        #        category="news", priority="P1"),
        # Source(kind="news_rss", name="360tv.ru — Коломна",
        #        handle="https://360tv.ru/kolomna/rss/",
        #        category="news", priority="P1"),
        # Source(kind="news_rss", name="Подмосковье сегодня — Коломна",
        #        handle="https://mosregtoday.ru/rss/tag/kolomna/",
        #        category="news", priority="P2"),
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
        Source(
            "gosuslugi",
            "ПОС — Платформа обратной связи",
            "kolomna_pos",
            "appeals",
            "P1",
            notes="Портал pos.gosuslugi.ru; требует OAuth интеграции.",
        ),
    ],
)

LUKHOVITSY_SOURCES = CitySources(
    news_rss=[
        _google_news_rss(
            "Луховицы",
            "%D0%9B%D1%83%D1%85%D0%BE%D0%B2%D0%B8%D1%86%D1%8B",
        ),
    ],
)

VOSKRESENSK_SOURCES = CitySources(
    news_rss=[
        _google_news_rss(
            "Воскресенск",
            "%D0%92%D0%BE%D1%81%D0%BA%D1%80%D0%B5%D1%81%D0%B5%D0%BD%D1%81%D0%BA",
        ),
    ],
)

EGORYEVSK_SOURCES = CitySources(
    news_rss=[
        _google_news_rss(
            "Егорьевск",
            "%D0%95%D0%B3%D0%BE%D1%80%D1%8C%D0%B5%D0%B2%D1%81%D0%BA",
        ),
    ],
)

STUPINO_SOURCES = CitySources(
    news_rss=[
        _google_news_rss(
            "Ступино",
            "%D0%A1%D1%82%D1%83%D0%BF%D0%B8%D0%BD%D0%BE",
        ),
    ],
)

OZYORY_SOURCES = CitySources(
    news_rss=[
        _google_news_rss(
            "Озёры",
            "%D0%9E%D0%B7%D1%91%D1%80%D1%8B",
        ),
    ],
)


SOURCES: Dict[str, CitySources] = {
    "Коломна": KOLOMNA_SOURCES,
    "Луховицы": LUKHOVITSY_SOURCES,
    "Воскресенск": VOSKRESENSK_SOURCES,
    "Егорьевск": EGORYEVSK_SOURCES,
    "Ступино": STUPINO_SOURCES,
    "Озёры": OZYORY_SOURCES,
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
