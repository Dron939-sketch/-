"""Happiness events library (ТЗ §39, MVP adapter).

Курируемая коллекция из 18 событий, адаптированных под юго-восток
Московской области: банные фестивали, гастрономия (луховицкие огурцы,
яблочный спас), фольклорные гуляния, православные праздники, рыбалка
и сельская тематика на Оке. Каждое событие несёт:

  type, audience, season, happiness_impact, trust_impact, cost_rub,
  duration_days, tags, description.

`recommend(season=None, audience=None, limit=6)` фильтрует по сезону
(год-за-год события появляются в любое время), по аудитории, и
сортирует по комбинированному happiness × trust score.

Легаси `happiness_events_library.py` — полный каталог на ~800 строк,
взят как концептуальный ориентир. Адаптер ужат до наиболее
применимых событий для 6 пилотных городов.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple


_SEASONS = ("winter", "spring", "summer", "autumn", "year_round")
_AUDIENCES = ("all", "family", "youth", "adults", "seniors", "tourists")


@dataclass(frozen=True)
class HappinessEvent:
    id: str
    name: str
    description: str
    type: str
    audience: str
    season: str
    happiness_impact: float     # 0..1
    trust_impact: float          # 0..1
    cost_rub: int
    duration_days: int
    tags: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "type": self.type,
            "audience": self.audience,
            "season": self.season,
            "happiness_impact": round(self.happiness_impact, 2),
            "trust_impact": round(self.trust_impact, 2),
            "cost_rub": int(self.cost_rub),
            "duration_days": int(self.duration_days),
            "tags": list(self.tags),
        }


_LIBRARY: List[HappinessEvent] = [
    HappinessEvent(
        id="day_of_city",
        name="День города",
        description="Центральная площадь + набережная, концерт + ярмарка + салют.",
        type="folk", audience="all", season="summer",
        happiness_impact=0.85, trust_impact=0.6,
        cost_rub=8_000_000, duration_days=1,
        tags=("флаг", "фестиваль", "бренд"),
    ),
    HappinessEvent(
        id="pancake_week",
        name="Масленица на набережной",
        description="Блины, сжигание чучела, молодецкие забавы, ярмарка ремёсел.",
        type="folk", audience="family", season="winter",
        happiness_impact=0.75, trust_impact=0.5,
        cost_rub=2_500_000, duration_days=1,
        tags=("традиции", "еда", "православие"),
    ),
    HappinessEvent(
        id="apple_saved",
        name="Яблочный Спас",
        description="Освящение яблок + ярмарка местных фермеров + мастер-классы.",
        type="religious", audience="family", season="summer",
        happiness_impact=0.70, trust_impact=0.55,
        cost_rub=1_500_000, duration_days=1,
        tags=("православие", "фермеры", "сад"),
    ),
    HappinessEvent(
        id="kolomna_kremlin",
        name="Фестиваль у Коломенского кремля",
        description="Историческая реконструкция + концерт + экскурсии.",
        type="cultural", audience="tourists", season="summer",
        happiness_impact=0.72, trust_impact=0.5,
        cost_rub=3_500_000, duration_days=2,
        tags=("туризм", "история"),
    ),
    HappinessEvent(
        id="oka_fishing",
        name="Турнир по рыбалке на Оке",
        description="Соревнования + уха на берегу + призы за самую крупную.",
        type="fishing", audience="adults", season="summer",
        happiness_impact=0.62, trust_impact=0.4,
        cost_rub=800_000, duration_days=1,
        tags=("Ока", "спорт", "отдых"),
    ),
    HappinessEvent(
        id="luhovitsy_cucumber",
        name="Праздник луховицкого огурца",
        description="Гастрономический фестиваль с дегустациями и мастер-классами.",
        type="gastronomy", audience="family", season="summer",
        happiness_impact=0.68, trust_impact=0.5,
        cost_rub=2_000_000, duration_days=1,
        tags=("Луховицы", "гастрономия", "фермеры"),
    ),
    HappinessEvent(
        id="winter_skating",
        name="Открытие катка в центре",
        description="Городской каток + прокат коньков + горячий чай + светомузыка.",
        type="seasonal", audience="all", season="winter",
        happiness_impact=0.65, trust_impact=0.45,
        cost_rub=3_500_000, duration_days=90,
        tags=("зима", "спорт", "семья"),
    ),
    HappinessEvent(
        id="yard_concert",
        name="Дворовые концерты выходного дня",
        description="5 вечерних концертов в разных районах с местными артистами.",
        type="folk", audience="all", season="summer",
        happiness_impact=0.55, trust_impact=0.5,
        cost_rub=1_200_000, duration_days=5,
        tags=("дворы", "музыка", "соседи"),
    ),
    HappinessEvent(
        id="crafts_market",
        name="Ярмарка ремёсел",
        description="Гончары, ткачи, кузнецы; мастер-классы для детей.",
        type="crafts", audience="family", season="year_round",
        happiness_impact=0.58, trust_impact=0.5,
        cost_rub=700_000, duration_days=2,
        tags=("ремёсла", "дети", "традиции"),
    ),
    HappinessEvent(
        id="victory_day",
        name="День Победы",
        description="Парад + бессмертный полк + полевая кухня + вечерний салют.",
        type="cultural", audience="all", season="spring",
        happiness_impact=0.80, trust_impact=0.75,
        cost_rub=5_000_000, duration_days=1,
        tags=("память", "патриотизм", "государство"),
    ),
    HappinessEvent(
        id="knowledge_day",
        name="1 сентября + День молодёжи",
        description="Праздник знаний + молодёжный вечерний концерт.",
        type="educational", audience="youth", season="autumn",
        happiness_impact=0.60, trust_impact=0.5,
        cost_rub=1_500_000, duration_days=1,
        tags=("школа", "молодёжь"),
    ),
    HappinessEvent(
        id="new_year_tree",
        name="Главная ёлка города",
        description="Новогодняя площадь + Дед Мороз + детские утренники.",
        type="seasonal", audience="family", season="winter",
        happiness_impact=0.80, trust_impact=0.55,
        cost_rub=4_000_000, duration_days=14,
        tags=("новый год", "дети", "семья"),
    ),
    HappinessEvent(
        id="banya_festival",
        name="Банный фестиваль",
        description="Парки с русскими банями, парная с венниками, конкурсы.",
        type="banya", audience="adults", season="autumn",
        happiness_impact=0.55, trust_impact=0.4,
        cost_rub=1_000_000, duration_days=2,
        tags=("традиции", "здоровье"),
    ),
    HappinessEvent(
        id="grandpa_day",
        name="День пожилого человека",
        description="Концерт для пенсионеров + вечер памяти + чаепитие.",
        type="charity", audience="seniors", season="autumn",
        happiness_impact=0.60, trust_impact=0.7,
        cost_rub=800_000, duration_days=1,
        tags=("пенсионеры", "забота"),
    ),
    HappinessEvent(
        id="family_sports",
        name="Городская спартакиада «Папа, мама, я»",
        description="Семейные команды в 5 видах спорта с призами.",
        type="sports", audience="family", season="year_round",
        happiness_impact=0.65, trust_impact=0.5,
        cost_rub=1_200_000, duration_days=1,
        tags=("спорт", "семья"),
    ),
    HappinessEvent(
        id="charity_marathon",
        name="Благотворительный марафон",
        description="Забег в поддержку больных детей + ярмарка добра.",
        type="charity", audience="adults", season="spring",
        happiness_impact=0.55, trust_impact=0.75,
        cost_rub=600_000, duration_days=1,
        tags=("благотворительность", "спорт"),
    ),
    HappinessEvent(
        id="harvest_festival",
        name="Праздник урожая",
        description="Дары осени, ярмарка овощей, конкурс самой большой тыквы.",
        type="fermer", audience="family", season="autumn",
        happiness_impact=0.60, trust_impact=0.5,
        cost_rub=900_000, duration_days=2,
        tags=("фермеры", "осень", "еда"),
    ),
    HappinessEvent(
        id="easter_service",
        name="Пасхальные гуляния",
        description="Крёстный ход + освящение куличей + ярмарка.",
        type="religious", audience="all", season="spring",
        happiness_impact=0.70, trust_impact=0.55,
        cost_rub=1_000_000, duration_days=1,
        tags=("православие", "традиции"),
    ),
]


@dataclass
class EventsReport:
    season: str
    audience: Optional[str]
    events: List[HappinessEvent]
    total_library: int
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "season": self.season,
            "audience": self.audience,
            "events": [e.to_dict() for e in self.events],
            "total_library": int(self.total_library),
            "note": self.note,
        }


def library_size() -> int:
    return len(_LIBRARY)


def current_season(today: Optional[datetime] = None) -> str:
    """Return the meteorological season for a given date (defaults to now)."""
    t = today or datetime.now()
    m = t.month
    if m in (12, 1, 2):
        return "winter"
    if m in (3, 4, 5):
        return "spring"
    if m in (6, 7, 8):
        return "summer"
    return "autumn"


def recommend(
    season: Optional[str] = None,
    audience: Optional[str] = None,
    *,
    limit: int = 6,
    today: Optional[datetime] = None,
) -> EventsReport:
    """Score and return the top events for the requested season / audience.

    Missing arguments default to the current season and "all" audience.
    Year-round events are always eligible regardless of season filter.
    """
    season = (season or current_season(today)).strip().lower()
    audience_key = audience.strip().lower() if audience else None

    eligible: List[HappinessEvent] = []
    for event in _LIBRARY:
        if season and event.season not in (season, "year_round"):
            continue
        if audience_key and event.audience not in (audience_key, "all"):
            continue
        eligible.append(event)

    # Combined score: happiness_impact + 0.5 × trust_impact (trust weights less).
    eligible.sort(
        key=lambda e: e.happiness_impact + 0.5 * e.trust_impact,
        reverse=True,
    )
    picked = eligible[: max(1, int(limit))]

    note = None
    if not picked:
        note = "Событий на этот сезон/аудиторию не нашлось."

    return EventsReport(
        season=season,
        audience=audience_key,
        events=picked,
        total_library=len(_LIBRARY),
        note=note,
    )
