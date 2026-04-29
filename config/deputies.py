"""Deputy registry — городской округ Коломна.

Совет депутатов: 25 человек, 5 пятимандатных избирательных округов, срок
полномочий 5 лет (текущий созыв с января 2021).

Источник имён — официальный сайт администрации г.о. Коломна
(kolomnagrad.ru/board-deputies.html). Распределение по округам — по
итогам выборов 24.01.2021. Партийная принадлежность, телеграм/VK
каналы и состав постоянных комиссий пока не вписаны (заполнятся
отдельной правкой / CSV-импортом).

Сектора (`sectors`) — то, по каким темам соц-политики депутата стоит
маршрутизировать в auto-распределении тем (DeputyAgendaManager). Это
оценочная классификация, не официальное членство в комиссиях. Базовый
набор — broad social coverage; председатель и замы получают
максимальный охват.

Если состав поменяется (переизбрание, отзыв) — правится только этот
файл, сидер при следующем редеплое сделает upsert.
"""

from __future__ import annotations

from typing import Dict, List, TypedDict

# Канонические сектора для маршрутизации соц-повестки.
# Названия совпадают с теми, что использует DeputyAgendaManager.
SECTOR_SOCIAL_PROTECTION = "соцзащита"
SECTOR_HEALTHCARE = "здравоохранение"
SECTOR_EDUCATION = "образование"
SECTOR_YOUTH = "молодёжь"
SECTOR_CULTURE = "культура"
SECTOR_SPORT = "спорт"
SECTOR_HOUSING = "ЖКХ"
SECTOR_LANDSCAPING = "благоустройство"
SECTOR_TRANSPORT = "транспорт"
SECTOR_ECONOMY = "экономика"
SECTOR_GENERAL = "общая_повестка"

# Базовый набор соц-секторов для рядовых депутатов от округа.
_DISTRICT_REP_SECTORS: List[str] = [
    SECTOR_SOCIAL_PROTECTION,
    SECTOR_LANDSCAPING,
    SECTOR_HOUSING,
    SECTOR_GENERAL,
]

# Расширенный набор для руководства Совета (председатель + замы).
_LEADERSHIP_SECTORS: List[str] = [
    SECTOR_SOCIAL_PROTECTION,
    SECTOR_HEALTHCARE,
    SECTOR_EDUCATION,
    SECTOR_HOUSING,
    SECTOR_LANDSCAPING,
    SECTOR_TRANSPORT,
    SECTOR_CULTURE,
    SECTOR_GENERAL,
]


class DeputyConfig(TypedDict, total=False):
    external_id: str    # стабильный slug, ключ для UPSERT
    name: str
    role: str           # speaker | sector_lead | district_rep | support
    district: str       # "Округ №1" .. "Округ №5"
    party: str          # партия (когда уточним)
    sectors: List[str]
    followers: int
    influence_score: float
    telegram: str       # username без @
    vk: str             # screen_name
    enabled: bool
    note: str           # внутренняя пометка (TODO/комментарий)


def _district_rep(
    *, external_id: str, name: str, district: str, sectors: List[str] | None = None,
) -> DeputyConfig:
    return {
        "external_id": external_id,
        "name": name,
        "role": "district_rep",
        "district": district,
        "sectors": sectors or list(_DISTRICT_REP_SECTORS),
        "influence_score": 0.5,
        "enabled": True,
    }


def _leader(
    *, external_id: str, name: str, district: str, role_label: str,
) -> DeputyConfig:
    """Руководители Совета: председатель + 2 заместителя."""
    return {
        "external_id": external_id,
        "name": name,
        "role": "speaker",  # выводят широкую повестку
        "district": district,
        "sectors": list(_LEADERSHIP_SECTORS),
        "influence_score": 0.85,
        "enabled": True,
        "note": role_label,
    }


# ---------------------------------------------------------------------------
# Город Коломна — Совет депутатов г.о. Коломна (25 человек)
# ---------------------------------------------------------------------------

_DISTRICT_1 = "Округ №1"
_DISTRICT_2 = "Округ №2"
_DISTRICT_3 = "Округ №3"
_DISTRICT_4 = "Округ №4"
_DISTRICT_5 = "Округ №5"


KOLOMNA_DEPUTIES: List[DeputyConfig] = [
    # --- Округ №1 ---
    {
        "external_id": "vaulin-av",
        "name":        "Ваулин Андрей Валерьевич",
        "role":        "district_rep",
        "district":    _DISTRICT_1,
        "sectors":     list(_DISTRICT_REP_SECTORS),
        "vk":          "avvaulin",
        "influence_score": 0.5,
        "enabled":     True,
    },
    _district_rep(external_id="orlov-sv",      name="Орлов Сергей Владимирович",      district=_DISTRICT_1),
    _district_rep(external_id="kostyunin-aa",  name="Костюнин Анатолий Александрович", district=_DISTRICT_1),
    {
        "external_id": "pavlova-na",
        "name":        "Павлова Наталья Александровна",
        "role":        "district_rep",
        "district":    _DISTRICT_1,
        "sectors":     list(_DISTRICT_REP_SECTORS),
        "vk":          "id342610269",
        "influence_score": 0.5,
        "enabled":     True,
    },
    _district_rep(external_id="rvachev-vm",    name="Рвачев Виктор Михайлович",       district=_DISTRICT_1),

    # --- Округ №2 ---
    _district_rep(external_id="bychkova-ev",   name="Бычкова Екатерина Владимировна", district=_DISTRICT_2),
    _district_rep(external_id="vasilev-sa",    name="Васильев Сергей Александрович",  district=_DISTRICT_2),
    _district_rep(external_id="kirichenko-sv", name="Кириченко Сергей Васильевич",    district=_DISTRICT_2),
    _district_rep(external_id="taranets-aa",   name="Таранец Андрей Александрович",   district=_DISTRICT_2),
    _district_rep(external_id="fedorov-dv",    name="Федоров Дмитрий Владимирович",   district=_DISTRICT_2),

    # --- Округ №3 ---
    _district_rep(external_id="khazov-iv",     name="Хазов Игорь Владиславович",      district=_DISTRICT_3),
    _district_rep(external_id="gerlinskiy-nb", name="Герлинский Николай Борисович",   district=_DISTRICT_3),
    _district_rep(external_id="leonova-zhk",   name="Леонова Жанна Константиновна",   district=_DISTRICT_3),
    _district_rep(external_id="koptyubenko-sa", name="Коптюбенко Сергей Александрович", district=_DISTRICT_3),
    _district_rep(external_id="zelenkov-rv",   name="Зеленков Роман Владимирович",    district=_DISTRICT_3),

    # --- Округ №4 ---
    _district_rep(external_id="shirkalin-ma",  name="Ширкалин Михаил Александрович",  district=_DISTRICT_4),
    _district_rep(external_id="kharitonov-aa", name="Харитонов Алексей Александрович", district=_DISTRICT_4),
    _district_rep(external_id="shumov-sv",     name="Шумов Сергей Вячеславович",      district=_DISTRICT_4),
    _district_rep(external_id="ivanov-av",     name="Иванов Алексей Вячеславович",    district=_DISTRICT_4),
    _district_rep(external_id="murzak-na",     name="Мурзак Наталия Александровна",   district=_DISTRICT_4),

    # --- Округ №5 (руководство Совета + двое рядовых) ---
    {
        "external_id": "bratushkov-nv",
        "name":        "Братушков Николай Владимирович",
        "role":        "speaker",
        "district":    _DISTRICT_5,
        "sectors":     list(_LEADERSHIP_SECTORS),
        "vk":          "bratushkov",
        "influence_score": 0.85,
        "enabled":     True,
        "note":        "Председатель Совета депутатов",
    },
    _leader(
        external_id="androsov-rv",
        name="Андросов Роман Викторович",
        district=_DISTRICT_5,
        role_label="Заместитель председателя Совета депутатов",
    ),
    _leader(
        external_id="kossov-vs",
        name="Коссов Валерий Семенович",
        district=_DISTRICT_5,
        role_label="Заместитель председателя Совета депутатов (на постоянной основе)",
    ),
    _district_rep(external_id="abdulaev-au",   name="Абдулаев Абдула Умахмадович",    district=_DISTRICT_5),
    _district_rep(external_id="zhukova-ni",    name="Жукова Нина Ивановна",           district=_DISTRICT_5),
]


# Карта: city_name → список депутатов. Сидер итерирует именно по ней,
# чтобы добавить второй город было два движения: новый ключ + список.
DEPUTIES_BY_CITY: Dict[str, List[DeputyConfig]] = {
    "Коломна": KOLOMNA_DEPUTIES,
}


def deputies_for_city(city_name: str) -> List[DeputyConfig]:
    """Безопасно вернуть список депутатов или [] если город не сконфигурирован."""
    return DEPUTIES_BY_CITY.get(city_name, [])
