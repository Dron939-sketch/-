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


from urllib.parse import quote_plus


def _google_news_rss(city_ru: str, query_encoded: str) -> Source:
    """Google News RSS feed for an arbitrary Russian-language query."""
    url = (
        f"https://news.google.com/rss/search?q={query_encoded}"
        "&hl=ru&gl=RU&ceid=RU:ru"
    )
    return Source("news_rss", f"Google News — {city_ru}", url, "news", "P1")


def _google_news_query(city_ru: str, query: str, *, category: str = "news",
                       priority: str = "P1") -> Source:
    """Helper: quote_plus the query + build a Source entry in one line.

    `query` is a free-form Russian phrase; it's URL-encoded at registration
    time. Name prefixed with the query so multi-query cities читаются в
    логах без расшифровки.
    """
    url = (
        f"https://news.google.com/rss/search?q={quote_plus(query)}"
        "&hl=ru&gl=RU&ceid=RU:ru"
    )
    return Source("news_rss", f"Google News — {query}", url, category, priority)


# Тематические запросы для любого города — просто подставляем название.
# 11 тем × N городов → N×11 запросов. Overlap терпимый — коллектор
# дедуплицирует по URL на уровне upsert_news_batch.
def _city_news_bundle(city_ru: str, *, priority_bump: bool = False) -> List[Source]:
    """Return a bundle of ~11 Google News queries covering all 4 Меistеr-vectors.

    Used for every pilot to guarantee minimum news volume. priority_bump
    nudges them to P0 for pilot city (Коломна), leaves P1 for остальных.
    """
    pri = "P0" if priority_bump else "P1"
    return [
        _google_news_query(city_ru, city_ru, category="news", priority=pri),
        _google_news_query(city_ru, f"{city_ru} ДТП", category="incidents", priority=pri),
        _google_news_query(city_ru, f"{city_ru} происшествие", category="incidents", priority=pri),
        _google_news_query(city_ru, f"{city_ru} ЖКХ", category="utilities", priority=pri),
        _google_news_query(city_ru, f"{city_ru} транспорт", category="transport", priority=pri),
        _google_news_query(city_ru, f"{city_ru} дороги", category="transport", priority="P1"),
        _google_news_query(city_ru, f"{city_ru} культура", category="culture", priority="P2"),
        _google_news_query(city_ru, f"{city_ru} школа", category="news", priority="P1"),
        _google_news_query(city_ru, f"{city_ru} бизнес", category="business", priority="P1"),
        _google_news_query(city_ru, f"{city_ru} администрация", category="official", priority=pri),
        _google_news_query(city_ru, f"{city_ru} благоустройство", category="news", priority="P2"),
    ]


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
        # Подтверждённые VK-handles. Остальные удалены — не существовали
        # (error_code=100) либо имеют закрытую стену (error_code=15).
        # При онбординге новых VK-источников: проверить
        # https://vk.com/<handle> и убедиться что страница доступна
        # без авторизации, перед добавлением сюда.
        Source("vk", "Типичная Коломна", "typical_kolomna", "complaints", "P0"),
        Source("vk", "Коломна Сегодня", "kolomna_today", "news", "P0"),
        Source("vk", "Администрация Коломны", "kolomna_adm", "official", "P0"),
        Source("vk", "Коломна Онлайн", "kolomna_online", "news", "P1"),
        # Автомобилисты Коломны — handle подтвердить вручную, оставлен по
        # запросу пользователя; коллектор тихо помут'ит его при ошибке.
        Source("vk", "Автомобилисты Коломны", "auto_kolomna", "transport", "P1"),
    ],
    news_rss=[
        # --- 11 тематических Google News запросов под пилотом (P0) ---
        *_city_news_bundle("Коломна", priority_bump=True),
        # --- Прямой RSS городского издания — подтверждён живым. ---
        Source(
            kind="news_rss",
            name="in-kolomna.ru (RSS)",
            handle="https://in-kolomna.ru/rss.xml",
            category="news", priority="P0",
            notes="Главное городское новостное издание.",
        ),
        # --- RSS-ленты ниже регистрировались, но возвращают 404/timeout.
        # --- Оставлены закомментированными как лог для ручного онбординга
        # --- после того как найдём рабочий endpoint.
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
    news_rss=_city_news_bundle("Луховицы"),
)

VOSKRESENSK_SOURCES = CitySources(
    news_rss=_city_news_bundle("Воскресенск"),
)

EGORYEVSK_SOURCES = CitySources(
    news_rss=_city_news_bundle("Егорьевск"),
)

STUPINO_SOURCES = CitySources(
    news_rss=_city_news_bundle("Ступино"),
)

OZYORY_SOURCES = CitySources(
    news_rss=_city_news_bundle("Озёры"),
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
