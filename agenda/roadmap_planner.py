"""Roadmap planner.

Given a current metric level and a target, splits the gap into quarterly
milestones. This is a rule-based approximation that feeds the mayor's
"goal → plan" UI; the heavier reasoning (budgets, risk analysis, resource
modelling) lives in `intervention_library.py` and can be layered on top.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from math import ceil
from typing import Dict, List, Optional


VECTOR_NAMES = {
    "СБ": "Безопасность",
    "ТФ": "Экономика",
    "УБ": "Качество жизни",
    "ЧВ": "Социальный капитал",
}

# Rough per-level budget heuristics in RUB. Used only as an order-of-magnitude
# estimate until the real intervention library is plugged in.
_BASE_COST_PER_LEVEL = {
    "СБ": 18_000_000,
    "ТФ": 25_000_000,
    "УБ": 12_000_000,
    "ЧВ": 6_000_000,
}


@dataclass
class RoadmapMilestone:
    quarter_start: date
    quarter_end: date
    target_level: float
    interventions: List[str] = field(default_factory=list)
    estimated_cost_rub: int = 0
    risks: List[str] = field(default_factory=list)


@dataclass
class Roadmap:
    city: str
    vector: str
    start_level: float
    target_level: float
    deadline: date
    scenario: str  # "optimistic" | "baseline" | "pessimistic"
    milestones: List[RoadmapMilestone] = field(default_factory=list)
    total_cost_rub: int = 0
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "city": self.city,
            "vector": self.vector,
            "vector_name": VECTOR_NAMES.get(self.vector, self.vector),
            "start_level": self.start_level,
            "target_level": self.target_level,
            "deadline": self.deadline.isoformat(),
            "scenario": self.scenario,
            "total_cost_rub": self.total_cost_rub,
            "notes": self.notes,
            "milestones": [
                {
                    "quarter_start": m.quarter_start.isoformat(),
                    "quarter_end": m.quarter_end.isoformat(),
                    "target_level": m.target_level,
                    "interventions": m.interventions,
                    "estimated_cost_rub": m.estimated_cost_rub,
                    "risks": m.risks,
                }
                for m in self.milestones
            ],
        }


class RoadmapPlanner:
    """Split a vector gap into quarterly milestones.

    Three scenarios shift the pace of progress:
    - optimistic:  progress front-loaded (70% by mid-timeline)
    - baseline:    linear progress per quarter
    - pessimistic: progress back-loaded (ramp up late)
    """

    def __init__(self, city_name: str):
        self.city_name = city_name

    def plan(
        self,
        *,
        vector: str,
        start_level: float,
        target_level: float,
        deadline: date,
        scenario: str = "baseline",
        today: Optional[date] = None,
        intervention_catalog: Optional[Dict[str, List[str]]] = None,
    ) -> Roadmap:
        if vector not in VECTOR_NAMES:
            raise ValueError(f"Unknown vector: {vector!r}")
        if target_level <= start_level:
            raise ValueError("target_level must be greater than start_level")
        today = today or date.today()
        if deadline <= today:
            raise ValueError("deadline must be in the future")

        quarters = self._split_quarters(today, deadline)
        milestones = self._build_milestones(
            quarters=quarters,
            start_level=start_level,
            target_level=target_level,
            vector=vector,
            scenario=scenario,
            catalog=intervention_catalog or {},
        )
        total_cost = sum(m.estimated_cost_rub for m in milestones)
        notes = self._scenario_notes(scenario, vector)

        return Roadmap(
            city=self.city_name,
            vector=vector,
            start_level=start_level,
            target_level=target_level,
            deadline=deadline,
            scenario=scenario,
            milestones=milestones,
            total_cost_rub=total_cost,
            notes=notes,
        )

    @staticmethod
    def _split_quarters(start: date, end: date) -> List[tuple[date, date]]:
        quarters: List[tuple[date, date]] = []
        current = start
        while current < end:
            next_q = min(current + timedelta(days=90), end)
            quarters.append((current, next_q))
            current = next_q + timedelta(days=1)
        return quarters

    def _build_milestones(
        self,
        *,
        quarters: List[tuple[date, date]],
        start_level: float,
        target_level: float,
        vector: str,
        scenario: str,
        catalog: Dict[str, List[str]],
    ) -> List[RoadmapMilestone]:
        n = len(quarters)
        if n == 0:
            return []
        progress_curve = self._progress_curve(scenario, n)
        total_gap = target_level - start_level
        base_cost_per_level = _BASE_COST_PER_LEVEL.get(vector, 10_000_000)
        interventions = catalog.get(vector) or self._default_interventions(vector)

        milestones: List[RoadmapMilestone] = []
        previous_level = start_level
        for i, (q_start, q_end) in enumerate(quarters):
            this_level = start_level + total_gap * progress_curve[i]
            delta = this_level - previous_level
            cost = ceil(abs(delta) * base_cost_per_level)
            picked = interventions[i % len(interventions) : i % len(interventions) + 2]
            milestones.append(
                RoadmapMilestone(
                    quarter_start=q_start,
                    quarter_end=q_end,
                    target_level=round(this_level, 2),
                    interventions=picked or interventions[:2],
                    estimated_cost_rub=cost,
                    risks=self._default_risks(vector),
                )
            )
            previous_level = this_level
        return milestones

    @staticmethod
    def _progress_curve(scenario: str, n: int) -> List[float]:
        """Return cumulative progress ∈ [0,1] per quarter."""
        if n == 1:
            return [1.0]
        indices = [i / (n - 1) for i in range(n)]  # 0..1
        if scenario == "optimistic":
            return [round(x**0.5, 4) for x in indices]
        if scenario == "pessimistic":
            return [round(x**2.0, 4) for x in indices]
        return [round(x, 4) for x in indices]

    @staticmethod
    def _default_interventions(vector: str) -> List[str]:
        return {
            "СБ": [
                "Усиление патрулирования ДНД в проблемных районах",
                "Расширение системы видеонаблюдения",
                "Программы профилактики для подростков",
                "Ремонт уличного освещения",
            ],
            "ТФ": [
                "Налоговые каникулы для малого бизнеса",
                "Инвестиционный форум в Коломне",
                "Льготные кредиты производителям",
                "Реконструкция промышленной зоны",
            ],
            "УБ": [
                "Благоустройство исторического центра",
                "Реконструкция дорожной сети",
                "Развитие общественного транспорта",
                "Открытие новых ФАП и поликлиник",
            ],
            "ЧВ": [
                "Гранты для местных НКО",
                "Городские фестивали и ярмарки",
                "Добровольческие программы",
                "Поддержка школьного самоуправления",
            ],
        }.get(vector, ["Целевая программа развития"])

    @staticmethod
    def _default_risks(vector: str) -> List[str]:
        return {
            "СБ": ["Недостаток кадров в полиции", "Рост ЧП в праздничные периоды"],
            "ТФ": ["Сокращение федеральных трансфертов", "Отток кадров в Москву"],
            "УБ": ["Срыв сроков подрядчиками", "Рост цен на стройматериалы"],
            "ЧВ": ["Низкая вовлечённость жителей", "Политизация повестки"],
        }.get(vector, ["Недостаток ресурсов"])

    @staticmethod
    def _scenario_notes(scenario: str, vector: str) -> List[str]:
        if scenario == "optimistic":
            return ["Сценарий предполагает полное финансирование и кооперацию региона"]
        if scenario == "pessimistic":
            return ["Основной прогресс откладывается на последние кварталы срока"]
        return [f"Базовый сценарий: равномерный прирост по вектору {vector}"]
