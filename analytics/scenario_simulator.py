"""What-If Scenario Simulator.

Simulates the impact of budget decisions and interventions on city vector indices.
Uses a rule-based causal model approximating the Meister algorithm dynamics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import math

VECTOR_NAMES = {
    "safety": "Безопасность",
    "economy": "Экономика",
    "quality": "Качество жизни",
    "social": "Социальный капитал",
}

# Cross-vector influence matrix (source -> target coefficients)
# Positive = reinforcing, Negative = dampening
CROSS_INFLUENCE: Dict[str, Dict[str, float]] = {
    "safety": {"economy": 0.15, "quality": 0.25, "social": 0.10},
    "economy": {"safety": 0.10, "quality": 0.20, "social": 0.15},
    "quality": {"safety": 0.15, "economy": 0.10, "social": 0.20},
    "social": {"safety": 0.05, "economy": 0.10, "quality": 0.15},
}

# Intervention effectiveness by vector (base multiplier per 1M RUB)
INTERVENTION_EFFECTIVENESS: Dict[str, Dict[str, float]] = {
    "patrol": {"vector": "safety", "base_effect": 0.08, "duration_months": 6},
    "cctv": {"vector": "safety", "base_effect": 0.06, "duration_months": 12},
    "lighting": {"vector": "safety", "base_effect": 0.05, "duration_months": 9},
    "youth_programs": {"vector": "safety", "base_effect": 0.07, "duration_months": 8},
    
    "tax_holidays": {"vector": "economy", "base_effect": 0.09, "duration_months": 6},
    "biz_forum": {"vector": "economy", "base_effect": 0.05, "duration_months": 4},
    "subsidies": {"vector": "economy", "base_effect": 0.07, "duration_months": 8},
    "industrial_zone": {"vector": "economy", "base_effect": 0.12, "duration_months": 18},
    
    "roads": {"vector": "quality", "base_effect": 0.08, "duration_months": 12},
    "transport": {"vector": "quality", "base_effect": 0.06, "duration_months": 10},
    "parks": {"vector": "quality", "base_effect": 0.05, "duration_months": 8},
    "clinics": {"vector": "quality", "base_effect": 0.07, "duration_months": 10},
    
    "ngo_grants": {"vector": "social", "base_effect": 0.06, "duration_months": 6},
    "festivals": {"vector": "social", "base_effect": 0.05, "duration_months": 3},
    "volunteering": {"vector": "social", "base_effect": 0.04, "duration_months": 8},
    "school_councils": {"vector": "social", "base_effect": 0.05, "duration_months": 10},
}

# Alias for backward compatibility
INTERVENTION_EFFECTIVENESS = INTERVENTION_EFFECTIVENESS

INTERVENTION_COSTS: Dict[str, int] = {
    "patrol": 2_000_000,
    "cctv": 5_000_000,
    "lighting": 3_000_000,
    "youth_programs": 1_500_000,
    
    "tax_holidays": 4_000_000,
    "biz_forum": 2_500_000,
    "subsidies": 6_000_000,
    "industrial_zone": 15_000_000,
    
    "roads": 8_000_000,
    "transport": 5_000_000,
    "parks": 3_500_000,
    "clinics": 7_000_000,
    
    "ngo_grants": 1_500_000,
    "festivals": 2_000_000,
    "volunteering": 1_000_000,
    "school_councils": 800_000,
}


@dataclass
class Intervention:
    """Single intervention in a scenario."""
    code: str
    budget_rub: int
    start_month: int = 0  # months from now
    duration_months: int = 6
    
    @property
    def name(self) -> str:
        names = {
            "patrol": "Усиление патрулирования ДНД",
            "cctv": "Расширение системы видеонаблюдения",
            "lighting": "Ремонт уличного освещения",
            "youth_programs": "Программы профилактики для подростков",
            
            "tax_holidays": "Налоговые каникулы для малого бизнеса",
            "biz_forum": "Инвестиционный форум",
            "subsidies": "Льготные кредиты производителям",
            "industrial_zone": "Реконструкция промышленной зоны",
            
            "roads": "Реконструкция дорожной сети",
            "transport": "Развитие общественного транспорта",
            "parks": "Благоустройство парков и скверов",
            "clinics": "Открытие новых ФАП и поликлиник",
            
            "ngo_grants": "Гранты для местных НКО",
            "festivals": "Городские фестивали и ярмарки",
            "volunteering": "Программы добровольчества",
            "school_councils": "Поддержка школьного самоуправления",
        }
        return names.get(self.code, self.code.replace("_", " ").title())


@dataclass
class ScenarioResult:
    """Result of running a what-if scenario."""
    scenario_name: str
    baseline_vectors: Dict[str, float]
    projected_vectors: Dict[str, float]
    delta_vectors: Dict[str, float]
    total_cost_rub: int
    interventions: List[Intervention] = field(default_factory=list)
    timeline: List[Dict] = field(default_factory=list)
    confidence: str = "medium"  # low, medium, high
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "scenario_name": self.scenario_name,
            "baseline_vectors": self.baseline_vectors,
            "projected_vectors": self.projected_vectors,
            "delta_vectors": self.delta_vectors,
            "total_cost_rub": self.total_cost_rub,
            "interventions": [
                {
                    "code": i.code,
                    "name": i.name,
                    "budget_rub": i.budget_rub,
                    "start_month": i.start_month,
                    "duration_months": i.duration_months,
                }
                for i in self.interventions
            ],
            "timeline": self.timeline,
            "confidence": self.confidence,
            "notes": self.notes,
        }


class ScenarioSimulator:
    """Run what-if simulations on city vectors."""
    
    def __init__(self, city_name: str):
        self.city_name = city_name
    
    def simulate(
        self,
        *,
        baseline_vectors: Dict[str, float],
        interventions: List[Intervention],
        horizon_months: int = 12,
        scenario_name: str = "Custom Scenario",
    ) -> ScenarioResult:
        """Simulate the impact of interventions over time."""
        
        # Initialize state
        current = dict(baseline_vectors)
        timeline: List[Dict] = []
        
        # Group interventions by start month
        by_month: Dict[int, List[Intervention]] = {}
        for interv in interventions:
            by_month.setdefault(interv.start_month, []).append(interv)
        
        # Simulate month by month
        for month in range(horizon_months + 1):
            # Apply interventions starting this month
            active_interventions = by_month.get(month, [])
            
            month_effects: Dict[str, float] = {v: 0.0 for v in baseline_vectors}
            
            for interv in active_interventions:
                if interv.code not in INTERVENTION_EFFECTIVENESS:
                    continue
                
                eff_data = INTERVENTION_EFFECTIVENESS[interv.code]
                target_vector = eff_data["vector"]
                base_effect = eff_data["base_effect"]
                duration = eff_data["duration_months"]
                
                # Calculate effect magnitude based on budget
                base_cost = INTERVENTION_COSTS.get(interv.code, 1_000_000)
                budget_multiplier = min(interv.budget_rub / base_cost, 3.0)  # cap at 3x
                
                # Effect decays over duration
                remaining_months = max(0, duration - (month - interv.start_month))
                if remaining_months > 0:
                    decay_factor = remaining_months / duration
                    effect = base_effect * budget_multiplier * decay_factor
                    month_effects[target_vector] += effect
            
            # Apply direct effects
            for vector, effect in month_effects.items():
                if effect > 0:
                    # Diminishing returns near ceiling (6.0 scale -> 1.0 normalized)
                    ceiling = 1.0
                    distance_to_ceiling = ceiling - current[vector]
                    actual_effect = min(effect, distance_to_ceiling * 0.5)
                    current[vector] = round(current[vector] + actual_effect, 4)
            
            # Apply cross-vector influences
            new_current = dict(current)
            for source, targets in CROSS_INFLUENCE.items():
                for target, coeff in targets.items():
                    influence = (current[source] - 0.5) * coeff * 0.1
                    new_current[target] = round(
                        max(0.0, min(1.0, new_current[target] + influence)), 
                        4
                    )
            current = new_current
            
            # Record snapshot
            timeline.append({
                "month": month,
                "vectors": dict(current),
                "active_interventions": [i.name for i in active_interventions],
            })
        
        # Calculate deltas
        delta_vectors = {
            v: round(current[v] - baseline_vectors[v], 4)
            for v in baseline_vectors
        }
        
        # Determine confidence
        total_spent = sum(i.budget_rub for i in interventions)
        if total_spent < 5_000_000:
            confidence = "low"
            notes = ["Низкий бюджет — высокая неопределённость результатов"]
        elif total_spent > 50_000_000:
            confidence = "high"
            notes = ["Значительный бюджет — прогноз более надёжен"]
        else:
            confidence = "medium"
            notes = ["Средний бюджет — умеренная уверенность в прогнозе"]
        
        # Add contextual notes
        max_delta_vector = max(delta_vectors, key=lambda v: abs(delta_vectors[v]))
        if delta_vectors[max_delta_vector] > 0:
            notes.append(
                f"Наибольший рост ожидается по вектору «{VECTOR_NAMES[max_delta_vector]}» "
                f"(+{delta_vectors[max_delta_vector]:.2%})"
            )
        elif delta_vectors[max_delta_vector] < 0:
            notes.append("Внимание: некоторые показатели могут снизиться из-за перераспределения ресурсов")
        
        total_cost = sum(i.budget_rub for i in interventions)
        
        return ScenarioResult(
            scenario_name=scenario_name,
            baseline_vectors=baseline_vectors,
            projected_vectors=current,
            delta_vectors=delta_vectors,
            interventions=interventions,
            timeline=timeline,
            total_cost_rub=total_cost,
            confidence=confidence,
            notes=notes,
        )
    
    def suggest_interventions(
        self,
        *,
        target_vector: str,
        budget_limit_rub: int,
        priority: str = "balanced",  # immediate, sustainable, balanced
    ) -> List[Intervention]:
        """Suggest optimal interventions for a given budget and target."""
        
        candidates = [
            (code, data) 
            for code, data in INTERVENTION_EFFECTIVENCESS.items()
            if data["vector"] == target_vector
        ]
        
        if priority == "immediate":
            # Sort by shortest duration (quick wins)
            candidates.sort(key=lambda x: x[1]["duration_months"])
        elif priority == "sustainable":
            # Sort by longest duration
            candidates.sort(key=lambda x: -x[1]["duration_months"])
        else:
            # Balanced: sort by effectiveness per ruble
            candidates.sort(
                key=lambda x: x[1]["base_effect"] / INTERVENTION_COSTS.get(x[0], 1),
                reverse=True
            )
        
        selected: List[Intervention] = []
        remaining_budget = budget_limit_rub
        
        for code, data in candidates:
            cost = INTERVENTION_COSTS.get(code, 1_000_000)
            if cost <= remaining_budget:
                selected.append(Intervention(
                    code=code,
                    budget_rub=cost,
                    duration_months=data["duration_months"],
                ))
                remaining_budget -= cost
        
        return selected
