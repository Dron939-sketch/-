"""Decision simulator (ТЗ §11, MVP adapter).

Library of 10 типичных управленческих решений городской администрации —
каждое с ориентировочной стоимостью, сроком, и ожидаемым воздействием
на 4 Меейстер-вектора в трёх сценариях (оптимистичный / реалистичный /
пессимистичный). Список рисков + теги для UI.

Решения — шаблоны, а не конкретные проекты; цифры — ориентиры на основе
публичных методических материалов по регионам РФ (не обязательство по
конкретному городу).

Легаси `decision_simulator.py` ships agent-based modeling + system
dynamics engine. Пропущен сознательно — симуляция агентов требует
калибровочных данных, которых у нас нет. Адаптер отдаёт мэру честный
каталог «что можно сделать и чего ждать».

`filter_for(vector=None)` выбирает решения, где primary_vector совпадает
или этот вектор присутствует в значимом воздействии любого сценария.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class DecisionScenario:
    label: str
    safety: float
    economy: float
    quality: float
    social: float
    note: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "safety":  round(self.safety, 2),
            "economy": round(self.economy, 2),
            "quality": round(self.quality, 2),
            "social":  round(self.social, 2),
            "note": self.note,
        }


@dataclass(frozen=True)
class Decision:
    id: str
    name: str
    description: str
    primary_vector: str
    cost_rub: int
    duration_months: int
    tags: tuple
    risks: tuple
    scenarios: Dict[str, DecisionScenario]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "primary_vector": self.primary_vector,
            "cost_rub": int(self.cost_rub),
            "duration_months": int(self.duration_months),
            "tags": list(self.tags),
            "risks": list(self.risks),
            "scenarios": {k: v.to_dict() for k, v in self.scenarios.items()},
        }


def _s(label, sb=0.0, tf=0.0, ub=0.0, chv=0.0, note="") -> DecisionScenario:
    return DecisionScenario(
        label=label, safety=sb, economy=tf, quality=ub, social=chv, note=note,
    )


_DECISIONS: List[Decision] = [
    Decision(
        id="cam_network",
        name="Расширение «Безопасного города»",
        description="Установка 200+ камер с интеграцией в региональный мониторинг.",
        primary_vector="safety",
        cost_rub=60_000_000, duration_months=6,
        tags=("безопасность", "цифровизация", "регион"),
        risks=("Рост опасений по персданным", "Зависимость от областной сети"),
        scenarios={
            "optimistic":  _s("Оптимистичный",  sb=+0.8, tf=+0.1, ub=+0.1,
                              note="Раскрываемость +15%, ощущение безопасности +20%."),
            "realistic":   _s("Реалистичный",   sb=+0.4, tf=+0.0, ub=+0.1,
                              note="Умеренный рост раскрываемости, точечная профилактика."),
            "pessimistic": _s("Пессимистичный", sb=+0.1, chv=-0.1,
                              note="Камеры не интегрированы, ощущение надзора."),
        },
    ),
    Decision(
        id="yard_program",
        name="Программа «Мой двор»",
        description="Благоустройство 20 дворов по голосованию жителей за сезон.",
        primary_vector="quality",
        cost_rub=90_000_000, duration_months=9,
        tags=("благоустройство", "участие", "дворы"),
        risks=("Срыв сроков подрядчиками", "Недовольство из-за «не того» двора"),
        scenarios={
            "optimistic":  _s("Оптимистичный",  ub=+0.7, chv=+0.4, tf=+0.1,
                              note="Рост удовлетворённости, эффект мультипликации."),
            "realistic":   _s("Реалистичный",   ub=+0.4, chv=+0.2,
                              note="Заметное улучшение, ROI через год."),
            "pessimistic": _s("Пессимистичный", ub=+0.1, chv=-0.1,
                              note="Скандалы вокруг выбора дворов и подрядчиков."),
        },
    ),
    Decision(
        id="sme_subsidy",
        name="Субсидирование аренды для МСП",
        description="Субсидия 50% аренды для новых МСП в 1-й год в центре.",
        primary_vector="economy",
        cost_rub=40_000_000, duration_months=12,
        tags=("бизнес", "мсп", "субсидии"),
        risks=("Злоупотребления номинальными регистрациями", "Низкая активность"),
        scenarios={
            "optimistic":  _s("Оптимистичный",  tf=+0.6, ub=+0.2,
                              note="20+ новых точек, рост налоговой базы через год."),
            "realistic":   _s("Реалистичный",   tf=+0.3, ub=+0.1,
                              note="10 новых МСП, часть закрывается после субсидии."),
            "pessimistic": _s("Пессимистичный", tf=+0.1,
                              note="Субсидии без роста — захват рынка теми же игроками."),
        },
    ),
    Decision(
        id="transport_optimize",
        name="Оптимизация маршрутной сети",
        description="Перераспределение автобусов по GPS-аналитике + выделенка.",
        primary_vector="quality",
        cost_rub=25_000_000, duration_months=4,
        tags=("транспорт", "маршруты", "данные"),
        risks=("Переходный период — жалобы", "Сопротивление перевозчиков"),
        scenarios={
            "optimistic":  _s("Оптимистичный",  ub=+0.5, tf=+0.2, chv=+0.1,
                              note="Время в пути -15%, переполненность -30%."),
            "realistic":   _s("Реалистичный",   ub=+0.3, tf=+0.1,
                              note="Улучшение на ключевых маршрутах."),
            "pessimistic": _s("Пессимистичный", ub=-0.1, chv=-0.2,
                              note="Плохая коммуникация — всплеск жалоб."),
        },
    ),
    Decision(
        id="kindergarten_build",
        name="Строительство частного детсада с городом",
        description="ЧГП — администрация даёт землю, инвестор строит сад на 150 мест.",
        primary_vector="social",
        cost_rub=120_000_000, duration_months=18,
        tags=("образование", "дети", "чгп"),
        risks=("Задержки строительства", "Кадровый дефицит воспитателей"),
        scenarios={
            "optimistic":  _s("Оптимистичный",  chv=+0.6, ub=+0.4, tf=+0.2,
                              note="Закрытие очереди в сад, приток молодых семей."),
            "realistic":   _s("Реалистичный",   chv=+0.4, ub=+0.2,
                              note="Частичное снижение очереди."),
            "pessimistic": _s("Пессимистичный", chv=+0.1, ub=+0.1,
                              note="Затянутая стройка, нехватка воспитателей."),
        },
    ),
    Decision(
        id="ekogorod_waste",
        name="Раздельный сбор мусора",
        description="3-корзинная система с просветительской кампанией.",
        primary_vector="quality",
        cost_rub=35_000_000, duration_months=6,
        tags=("экология", "мусор", "образование"),
        risks=("Смешанный вывоз обнулит усилия", "Низкая вовлечённость"),
        scenarios={
            "optimistic":  _s("Оптимистичный",  ub=+0.4, chv=+0.3,
                              note="Рост сознательности, снижение жалоб на запах."),
            "realistic":   _s("Реалистичный",   ub=+0.2, chv=+0.1,
                              note="Частичное внедрение в центре."),
            "pessimistic": _s("Пессимистичный", ub=-0.1,
                              note="Разоблачение «одной мусоровозкой» — скандал."),
        },
    ),
    Decision(
        id="volunteer_hub",
        name="Штаб городских волонтёров",
        description="Физический хаб + бонусная программа для активистов.",
        primary_vector="social",
        cost_rub=8_000_000, duration_months=3,
        tags=("волонтёры", "молодёжь", "сообщество"),
        risks=("Выгорание без системной поддержки",),
        scenarios={
            "optimistic":  _s("Оптимистичный",  chv=+0.5, ub=+0.2, sb=+0.1,
                              note="Активная молодёжь остаётся, растёт соц. капитал."),
            "realistic":   _s("Реалистичный",   chv=+0.3, ub=+0.1,
                              note="Рабочий хаб, 50-100 регулярных волонтёров."),
            "pessimistic": _s("Пессимистичный", chv=+0.1,
                              note="Низкая явка, формальные отчёты."),
        },
    ),
    Decision(
        id="tourism_festival",
        name="Флагманский городской фестиваль",
        description="3-дневный фестиваль в центре (музыка / гастрономия / история).",
        primary_vector="economy",
        cost_rub=30_000_000, duration_months=4,
        tags=("туризм", "культура", "мсп"),
        risks=("Погода", "Инциденты с безопасностью"),
        scenarios={
            "optimistic":  _s("Оптимистичный",  tf=+0.4, ub=+0.3, chv=+0.3,
                              note="30-50k гостей, загрузка гостиниц +40%."),
            "realistic":   _s("Реалистичный",   tf=+0.2, ub=+0.2, chv=+0.2,
                              note="Устойчивое расширение туристической базы."),
            "pessimistic": _s("Пессимистичный", tf=+0.0,
                              note="Погода / слабая реклама — эффект ниже ожиданий."),
        },
    ),
    Decision(
        id="senior_care",
        name="Патронажная служба пожилых",
        description="Расширение муниципального патроната — +30 получателей.",
        primary_vector="social",
        cost_rub=20_000_000, duration_months=12,
        tags=("пожилые", "соцзащита"),
        risks=("Кадровый дефицит патронажных работников",),
        scenarios={
            "optimistic":  _s("Оптимистичный",  chv=+0.5, ub=+0.2,
                              note="Снижение соц. изоляции, благодарная обратная связь."),
            "realistic":   _s("Реалистичный",   chv=+0.3, ub=+0.1,
                              note="30 новых подопечных, стабильный сервис."),
            "pessimistic": _s("Пессимистичный", chv=+0.1,
                              note="Текучесть кадров съедает эффект."),
        },
    ),
    Decision(
        id="digital_services",
        name="Цифровизация муниципальных услуг",
        description="Перевод 30+ типовых процедур в онлайн-формат.",
        primary_vector="quality",
        cost_rub=50_000_000, duration_months=9,
        tags=("цифровизация", "госуслуги"),
        risks=("Сбои на старте", "Цифровое неравенство пожилых"),
        scenarios={
            "optimistic":  _s("Оптимистичный",  ub=+0.5, tf=+0.3, sb=+0.2,
                              note="Время обработки x5, рост удовлетворённости МСП."),
            "realistic":   _s("Реалистичный",   ub=+0.3, tf=+0.2,
                              note="Типовые услуги онлайн, МФЦ разгружается."),
            "pessimistic": _s("Пессимистичный", ub=+0.0,
                              note="Скан портал не работает стабильно, возврат в МФЦ."),
        },
    ),
]


def list_decisions() -> List[Decision]:
    return list(_DECISIONS)


def filter_for(vector: Optional[str] = None) -> List[Decision]:
    """Return decisions whose primary_vector matches, or (if vector is None) all.

    When `vector` is set, also include decisions that produce a non-trivial
    effect (|Δ| ≥ 0.15 in the realistic scenario) on that vector — so a mayor
    asking for "экономика" sees fundraising ideas even if their primary tag
    is social.
    """
    if not vector:
        return list(_DECISIONS)
    v = vector.strip().lower()
    picks: List[Decision] = []
    for d in _DECISIONS:
        if d.primary_vector == v:
            picks.append(d)
            continue
        realistic = d.scenarios.get("realistic")
        if realistic is None:
            continue
        effect = abs(getattr(realistic, v, 0.0) or 0.0)
        if effect >= 0.15:
            picks.append(d)
    return picks


def get_decision(decision_id: str) -> Optional[Decision]:
    for d in _DECISIONS:
        if d.id == decision_id:
            return d
    return None
