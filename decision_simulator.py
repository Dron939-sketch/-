#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 11: СИМУЛЯТОР РЕШЕНИЙ (Decision Simulator)
Система прогнозирования последствий управленческих решений

Основан на методах:
- Агентное моделирование (Agent-Based Modeling)
- Системная динамика
- Анализ сценариев "что если"
- Оценка побочных эффектов
- Мультифакторное прогнозирование
"""

import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


# ==================== МОДЕЛИ ДАННЫХ ====================

class DecisionType(Enum):
    """Типы управленческих решений"""
    BUDGET = "budget"                   # Бюджетные решения
    POLICY = "policy"                   # Политические/нормативные
    INFRASTRUCTURE = "infrastructure"   # Инфраструктурные проекты
    SOCIAL = "social"                   # Социальные программы
    SAFETY = "safety"                   # Меры безопасности
    ECONOMIC = "economic"               # Экономические стимулы
    COMMUNICATION = "communication"     # Коммуникационные кампании
    PERSONNEL = "personnel"             # Кадровые решения


class ScenarioType(Enum):
    """Типы сценариев"""
    OPTIMISTIC = "optimistic"     # Оптимистичный (максимальный эффект)
    REALISTIC = "realistic"       # Реалистичный (средний эффект)
    PESSIMISTIC = "pessimistic"   # Пессимистичный (минимальный эффект)
    CATASTROPHIC = "catastrophic" # Катастрофический (негативные последствия)


@dataclass
class Decision:
    """Управленческое решение"""
    id: str
    name: str
    description: str
    type: DecisionType
    parameters: Dict[str, Any]          # параметры решения
    cost_million_rub: float
    implementation_time_days: int
    affected_vectors: List[str]         # какие векторы Мейстера затрагивает
    expected_impact: Dict[str, float]   # ожидаемое влияние на метрики


@dataclass
class SimulationResult:
    """Результат симуляции"""
    id: str
    decision_id: str
    scenario: ScenarioType
    probability: float                   # вероятность сценария
    time_horizon_days: int              # горизонт прогноза
    direct_effects: Dict[str, float]    # прямые эффекты на метрики
    indirect_effects: Dict[str, List[Dict]]  # цепочки косвенных эффектов
    side_effects: List[Dict]            # побочные эффекты
    final_metrics: Dict[str, float]     # итоговые метрики
    confidence: float                   # уверенность в прогнозе
    recommendations: List[str]
    created_at: datetime


@dataclass
class DecisionComparison:
    """Сравнение альтернативных решений"""
    id: str
    baseline_metrics: Dict[str, float]   # текущие метрики
    alternatives: List[Dict]             # сравнение вариантов
    best_by_criteria: Dict[str, str]     # лучшее по каждому критерию
    trade_offs: List[Dict]               # компромиссы
    recommended: str                     # рекомендованное решение


# ==================== КОНФИГУРАЦИЯ ====================

class DecisionSimulatorConfig:
    """Конфигурация симулятора решений"""
    
    # Коэффициенты влияния между векторами
    INFLUENCE_MATRIX = {
        'СБ': {'СБ': 1.0, 'ТФ': 0.6, 'УБ': 0.5, 'ЧВ': 0.7},
        'ТФ': {'СБ': 0.5, 'ТФ': 1.0, 'УБ': 0.7, 'ЧВ': 0.4},
        'УБ': {'СБ': 0.4, 'ТФ': 0.6, 'УБ': 1.0, 'ЧВ': 0.8},
        'ЧВ': {'СБ': 0.6, 'ТФ': 0.4, 'УБ': 0.7, 'ЧВ': 1.0}
    }
    
    # Коэффициенты затухания эффектов по времени
    TIME_DECAY = 0.95  # 5% затухание в день
    
    # Пороги значимости для побочных эффектов
    SIDE_EFFECT_THRESHOLD = 0.05
    
    # Горизонты прогнозирования (дни)
    FORECAST_HORIZONS = [30, 90, 180, 365]


# ==================== ОСНОВНОЙ КЛАСС ====================

class DecisionSimulator:
    """
    Симулятор решений — прогнозирование последствий управленческих решений
    
    Позволяет мэру:
    - Протестировать решение до его принятия
    - Сравнить альтернативы
    - Увидеть цепочки косвенных эффектов
    - Оценить побочные последствия
    """
    
    def __init__(self, city_name: str, model=None, config: DecisionSimulatorConfig = None):
        self.city_name = city_name
        self.model = model  # ConfinementModel9 для учёта системных связей
        self.config = config or DecisionSimulatorConfig()
        
        # Хранилище
        self.decisions: Dict[str, Decision] = {}
        self.simulation_results: Dict[str, SimulationResult] = {}
        self.decision_history: List[Dict] = []
        
        # База знаний эффектов
        self.effects_knowledge_base = self._init_effects_knowledge_base()
        
        # Кэш
        self.cache = {}
        
        logger.info(f"DecisionSimulator инициализирован для города {city_name}")
    
    def _init_effects_knowledge_base(self) -> Dict[str, Dict]:
        """
        База знаний типовых эффектов управленческих решений
        """
        return {
            'budget_increase_safety': {
                'name': 'Увеличение бюджета на безопасность',
                'direct_effects': {'СБ': 0.15, 'ТФ': -0.05, 'ЧВ': 0.05},
                'time_lag_days': 30,
                'side_effects': [
                    {'description': 'Возможное недовольство других ведомств', 'probability': 0.4, 'severity': 0.2}
                ]
            },
            'budget_cut_maintenance': {
                'name': 'Сокращение бюджета на содержание',
                'direct_effects': {'УБ': -0.1, 'СБ': -0.05},
                'time_lag_days': 60,
                'side_effects': [
                    {'description': 'Рост жалоб на состояние инфраструктуры', 'probability': 0.7, 'severity': 0.3}
                ]
            },
            'tax_incentive_business': {
                'name': 'Налоговые льготы для бизнеса',
                'direct_effects': {'ТФ': 0.2, 'УБ': 0.05, 'СБ': -0.02},
                'time_lag_days': 90,
                'side_effects': [
                    {'description': 'Временное снижение налоговых поступлений', 'probability': 1.0, 'severity': 0.25}
                ]
            },
            'infrastructure_project': {
                'name': 'Крупный инфраструктурный проект',
                'direct_effects': {'УБ': 0.25, 'ТФ': 0.1, 'СБ': 0.05},
                'time_lag_days': 180,
                'side_effects': [
                    {'description': 'Временные неудобства для жителей', 'probability': 0.9, 'severity': 0.2},
                    {'description': 'Перерасход бюджета', 'probability': 0.5, 'severity': 0.3}
                ]
            },
            'social_program': {
                'name': 'Социальная программа поддержки',
                'direct_effects': {'ЧВ': 0.15, 'УБ': 0.1},
                'time_lag_days': 60,
                'side_effects': [
                    {'description': 'Дополнительная нагрузка на бюджет', 'probability': 0.8, 'severity': 0.15}
                ]
            },
            'safety_patrol_increase': {
                'name': 'Усиление патрулирования',
                'direct_effects': {'СБ': 0.2, 'ЧВ': 0.1},
                'time_lag_days': 14,
                'side_effects': [
                    {'description': 'Ощущение полицейского государства', 'probability': 0.3, 'severity': 0.1}
                ]
            },
            'communication_campaign': {
                'name': 'Информационная кампания',
                'direct_effects': {'ЧВ': 0.15},
                'time_lag_days': 30,
                'side_effects': [
                    {'description': 'Риск негативной реакции', 'probability': 0.2, 'severity': 0.2}
                ]
            },
            'staff_training': {
                'name': 'Обучение персонала администрации',
                'direct_effects': {'ЧВ': 0.1, 'УБ': 0.05},
                'time_lag_days': 90,
                'side_effects': []
            }
        }
    
    # ==================== 1. СОЗДАНИЕ РЕШЕНИЙ ====================
    
    async def create_decision(self,
                               name: str,
                               description: str,
                               decision_type: DecisionType,
                               parameters: Dict[str, Any],
                               cost: float,
                               implementation_time: int,
                               affected_vectors: List[str]) -> Decision:
        """
        Создание нового управленческого решения для симуляции
        """
        decision_id = f"dec_{hashlib.md5(f'{name}_{datetime.now().isoformat()}'.encode()).hexdigest()[:8]}"
        
        # Оценка ожидаемого воздействия
        expected_impact = await self._estimate_expected_impact(
            decision_type, parameters, affected_vectors
        )
        
        decision = Decision(
            id=decision_id,
            name=name,
            description=description,
            type=decision_type,
            parameters=parameters,
            cost_million_rub=cost,
            implementation_time_days=implementation_time,
            affected_vectors=affected_vectors,
            expected_impact=expected_impact
        )
        
        self.decisions[decision_id] = decision
        
        logger.info(f"Создано решение '{name}' с ID {decision_id}")
        return decision
    
    async def _estimate_expected_impact(self,
                                         decision_type: DecisionType,
                                         parameters: Dict,
                                         affected_vectors: List[str]) -> Dict[str, float]:
        """Оценка ожидаемого воздействия решения"""
        
        # Базовые эффекты из базы знаний
        base_key = f"{decision_type.value}_{parameters.get('subtype', 'default')}"
        
        # Поиск в базе знаний
        for key, effect in self.effects_knowledge_base.items():
            if key.startswith(decision_type.value):
                base_effects = effect.get('direct_effects', {})
                break
        else:
            base_effects = {v: 0.1 for v in affected_vectors}
        
        # Корректировка по параметрам
        adjusted_effects = base_effects.copy()
        
        # Учёт масштаба (бюджета)
        if 'budget' in parameters:
            scale_factor = min(2.0, parameters['budget'] / 10)  # 10 млн = базовый
            for v in adjusted_effects:
                adjusted_effects[v] *= scale_factor
        
        # Учёт срочности
        if parameters.get('urgency', 'normal') == 'high':
            for v in adjusted_effects:
                adjusted_effects[v] *= 0.8  # быстрые решения менее эффективны
        
        return adjusted_effects
    
    # ==================== 2. СИМУЛЯЦИЯ РЕШЕНИЯ ====================
    
    async def simulate_decision(self,
                                 decision_id: str,
                                 current_metrics: Dict[str, float],
                                 time_horizon_days: int = 180,
                                 include_indirect: bool = True) -> List[SimulationResult]:
        """
        Симуляция последствий принятия решения
        
        Args:
            decision_id: ID решения
            current_metrics: текущие метрики города
            time_horizon_days: горизонт прогноза в днях
            include_indirect: учитывать ли косвенные эффекты
            
        Returns:
            список результатов по сценариям
        """
        decision = self.decisions.get(decision_id)
        if not decision:
            raise ValueError(f"Решение {decision_id} не найдено")
        
        logger.info(f"Запуск симуляции для решения '{decision.name}'")
        
        results = []
        
        # Симуляция по трём основным сценариям
        scenarios = [
            (ScenarioType.OPTIMISTIC, 0.25),   # 25% вероятность
            (ScenarioType.REALISTIC, 0.50),    # 50% вероятность
            (ScenarioType.PESSIMISTIC, 0.20),  # 20% вероятность
            (ScenarioType.CATASTROPHIC, 0.05)  # 5% вероятность
        ]
        
        for scenario, probability in scenarios:
            result = await self._simulate_scenario(
                decision=decision,
                scenario=scenario,
                probability=probability,
                current_metrics=current_metrics,
                time_horizon_days=time_horizon_days,
                include_indirect=include_indirect
            )
            results.append(result)
            self.simulation_results[result.id] = result
        
        # Сохраняем в историю
        self.decision_history.append({
            'decision_id': decision_id,
            'decision_name': decision.name,
            'timestamp': datetime.now(),
            'results': [{
                'scenario': r.scenario.value,
                'probability': r.probability,
                'final_metrics': r.final_metrics
            } for r in results]
        })
        
        return results
    
    async def _simulate_scenario(self,
                                   decision: Decision,
                                   scenario: ScenarioType,
                                   probability: float,
                                   current_metrics: Dict[str, float],
                                   time_horizon_days: int,
                                   include_indirect: bool) -> SimulationResult:
        """
        Симуляция конкретного сценария
        """
        # Базовые метрики
        final_metrics = current_metrics.copy()
        
        # 1. Прямые эффекты
        direct_effects = await self._calculate_direct_effects(
            decision, scenario, time_horizon_days
        )
        
        for vector, change in direct_effects.items():
            if vector in final_metrics:
                final_metrics[vector] += change
                final_metrics[vector] = max(1.0, min(6.0, final_metrics[vector]))
        
        # 2. Косвенные эффекты (через связи Мейстера)
        indirect_effects = []
        if include_indirect and self.model:
            indirect_effects = await self._calculate_indirect_effects(
                decision, direct_effects, scenario, time_horizon_days
            )
            
            for effect in indirect_effects:
                vector = effect['target_vector']
                change = effect['total_change']
                if vector in final_metrics:
                    final_metrics[vector] += change
                    final_metrics[vector] = max(1.0, min(6.0, final_metrics[vector]))
        
        # 3. Побочные эффекты
        side_effects = await self._calculate_side_effects(
            decision, scenario, final_metrics
        )
        
        # 4. Учёт времени реализации
        if time_horizon_days > decision.implementation_time_days:
            # Эффект проявляется не сразу
            implementation_factor = min(1.0, time_horizon_days / decision.implementation_time_days)
            for vector in final_metrics:
                original_change = final_metrics[vector] - current_metrics.get(vector, 3.0)
                final_metrics[vector] = current_metrics.get(vector, 3.0) + original_change * implementation_factor
        
        # 5. Затухание эффектов со временем
        decay_factor = self.config.TIME_DECAY ** (time_horizon_days / 30)
        for vector in final_metrics:
            original_change = final_metrics[vector] - current_metrics.get(vector, 3.0)
            final_metrics[vector] = current_metrics.get(vector, 3.0) + original_change * decay_factor
        
        # Формируем рекомендации
        recommendations = await self._generate_recommendations(
            decision, scenario, direct_effects, side_effects, final_metrics
        )
        
        simulation_id = f"sim_{decision.id}_{scenario.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        return SimulationResult(
            id=simulation_id,
            decision_id=decision.id,
            scenario=scenario,
            probability=probability,
            time_horizon_days=time_horizon_days,
            direct_effects=direct_effects,
            indirect_effects=indirect_effects,
            side_effects=side_effects,
            final_metrics=final_metrics,
            confidence=self._calculate_confidence(scenario, decision, time_horizon_days),
            recommendations=recommendations,
            created_at=datetime.now()
        )
    
    async def _calculate_direct_effects(self,
                                         decision: Decision,
                                         scenario: ScenarioType,
                                         horizon: int) -> Dict[str, float]:
        """
        Расчёт прямых эффектов решения на метрики
        """
        effects = {}
        
        # Базовые эффекты из базы знаний
        base_key = f"{decision.type.value}_{decision.parameters.get('subtype', 'default')}"
        
        for key, effect_data in self.effects_knowledge_base.items():
            if key.startswith(decision.type.value):
                base_effects = effect_data.get('direct_effects', {})
                time_lag = effect_data.get('time_lag_days', 30)
                break
        else:
            base_effects = {v: 0.1 for v in decision.affected_vectors}
            time_lag = 30
        
        # Корректировка в зависимости от сценария
        scenario_multipliers = {
            ScenarioType.OPTIMISTIC: 1.3,
            ScenarioType.REALISTIC: 1.0,
            ScenarioType.PESSIMISTIC: 0.7,
            ScenarioType.CATASTROPHIC: 0.3
        }
        
        multiplier = scenario_multipliers.get(scenario, 1.0)
        
        # Учёт временного лага
        if horizon < time_lag:
            # Эффект ещё не проявился полностью
            progress = horizon / time_lag
            multiplier *= progress
        
        for vector, base_change in base_effects.items():
            effects[vector] = base_change * multiplier
        
        # Учёт параметров решения
        if 'intensity' in decision.parameters:
            intensity = decision.parameters['intensity']
            for v in effects:
                effects[v] *= intensity
        
        return effects
    
    async def _calculate_indirect_effects(self,
                                            decision: Decision,
                                            direct_effects: Dict[str, float],
                                            scenario: ScenarioType,
                                            horizon: int) -> List[Dict]:
        """
        Расчёт косвенных эффектов через системные связи (Мейстер)
        """
        indirect_effects = []
        
        if not self.model or not self.model.elements:
            return indirect_effects
        
        # Карта векторов к элементам модели
        vector_to_element = {'СБ': 2, 'ТФ': 3, 'УБ': 4, 'ЧВ': 5}
        
        # Для каждого прямого эффекта
        for vector, change in direct_effects.items():
            if vector not in vector_to_element:
                continue
            
            element_id = vector_to_element[vector]
            element = self.model.elements.get(element_id)
            
            if not element:
                continue
            
            # Находим элементы, на которые влияет данный
            for target_id in element.causes:
                target_element = self.model.elements.get(target_id)
                if not target_element:
                    continue
                
                # Определяем вектор цели
                target_vector = self._get_vector_from_element(target_element)
                if not target_vector:
                    continue
                
                # Сила связи
                link_strength = self._get_link_strength(element_id, target_id)
                
                # Затухание по цепочке
                decay = self.config.TIME_DECAY ** (horizon / 30)
                
                # Косвенный эффект
                indirect_change = change * link_strength * decay
                
                # Коррекция по сценарию
                scenario_multipliers = {
                    ScenarioType.OPTIMISTIC: 1.2,
                    ScenarioType.REALISTIC: 1.0,
                    ScenarioType.PESSIMISTIC: 0.8,
                    ScenarioType.CATASTROPHIC: 0.5
                }
                indirect_change *= scenario_multipliers.get(scenario, 1.0)
                
                indirect_effects.append({
                    'source_vector': vector,
                    'source_change': change,
                    'target_vector': target_vector,
                    'via_element': f"{element_id}→{target_id}",
                    'strength': link_strength,
                    'change': indirect_change,
                    'total_change': indirect_change
                })
        
        # Агрегируем по целевым векторам
        aggregated = {}
        for effect in indirect_effects:
            target = effect['target_vector']
            if target not in aggregated:
                aggregated[target] = 0
            aggregated[target] += effect['change']
        
        # Формируем результат с цепочками
        result = []
        for target, total in aggregated.items():
            chain = [e for e in indirect_effects if e['target_vector'] == target]
            result.append({
                'target_vector': target,
                'total_change': total,
                'chain': chain[:3]  # первые 3 звена
            })
        
        return result
    
    def _get_vector_from_element(self, element) -> Optional[str]:
        """Определение вектора по элементу модели"""
        element_id = getattr(element, 'id', 0)
        vector_map = {2: 'СБ', 3: 'ТФ', 4: 'УБ', 5: 'ЧВ'}
        return vector_map.get(element_id)
    
    def _get_link_strength(self, from_id: int, to_id: int) -> float:
        """Получение силы связи между элементами"""
        if not self.model or not hasattr(self.model, 'links'):
            return 0.5
        
        for link in self.model.links:
            if link.get('from') == from_id and link.get('to') == to_id:
                return link.get('strength', 0.5)
        
        return 0.3  # связь по умолчанию
    
    async def _calculate_side_effects(self,
                                        decision: Decision,
                                        scenario: ScenarioType,
                                        final_metrics: Dict[str, float]) -> List[Dict]:
        """
        Выявление побочных эффектов решения
        """
        side_effects = []
        
        # Проверка на резкое падение метрик
        for vector, value in final_metrics.items():
            if value < 2.0:  # критически низкий уровень
                side_effects.append({
                    'type': 'metric_collapse',
                    'vector': vector,
                    'value': value,
                    'description': f"Критическое падение {vector} до {value:.1f}/6",
                    'severity': 'high',
                    'probability': 0.7 if scenario == ScenarioType.CATASTROPHIC else 0.3
                })
        
        # Проверка на негативные реакции в соцсетях (по опыту)
        if decision.type in [DecisionType.POLICY, DecisionType.BUDGET]:
            if decision.parameters.get('unpopular', False):
                side_effects.append({
                    'type': 'social_backlash',
                    'description': 'Вероятна негативная реакция в соцсетях',
                    'severity': 'medium',
                    'probability': 0.6
                })
        
        # Проверка на бюджетные риски
        if decision.cost_million_rub > 100:
            side_effects.append({
                'type': 'budget_risk',
                'description': f'Высокий бюджетный риск ({decision.cost_million_rub} млн ₽)',
                'severity': 'high',
                'probability': 0.5
            })
        
        # Специфические побочные эффекты из базы знаний
        for key, effect_data in self.effects_knowledge_base.items():
            if key.startswith(decision.type.value):
                for se in effect_data.get('side_effects', []):
                    # Корректировка вероятности по сценарию
                    prob = se.get('probability', 0.5)
                    if scenario == ScenarioType.OPTIMISTIC:
                        prob *= 0.5
                    elif scenario == ScenarioType.PESSIMISTIC:
                        prob *= 1.5
                    elif scenario == ScenarioType.CATASTROPHIC:
                        prob *= 2.0
                    
                    side_effects.append({
                        'type': 'knowledge_base',
                        'description': se['description'],
                        'severity': 'medium' if se.get('severity', 0.2) > 0.3 else 'low',
                        'probability': min(1.0, prob)
                    })
                break
        
        return side_effects
    
    async def _generate_recommendations(self,
                                          decision: Decision,
                                          scenario: ScenarioType,
                                          direct_effects: Dict,
                                          side_effects: List,
                                          final_metrics: Dict) -> List[str]:
        """
        Генерация рекомендаций на основе результатов симуляции
        """
        recommendations = []
        
        # Оценка эффективности
        total_improvement = sum(max(0, v) for v in direct_effects.values())
        total_degradation = sum(min(0, v) for v in direct_effects.values())
        
        if total_improvement > abs(total_degradation) * 1.5:
            recommendations.append(f"✅ Решение эффективно: ожидается улучшение в {len([v for v in direct_effects.values() if v > 0])} сферах")
        elif total_degradation < 0:
            recommendations.append(f"⚠️ Решение имеет риски: возможны негативные последствия в {len([v for v in direct_effects.values() if v < 0])} сферах")
        
        # Учёт побочных эффектов
        high_risk_side = [s for s in side_effects if s.get('severity') == 'high' and s.get('probability', 0) > 0.5]
        if high_risk_side:
            recommendations.append(f"🚨 ВЫСОКИЕ РИСКИ: {', '.join([s['description'] for s in high_risk_side[:2]])}")
            recommendations.append("💡 Рекомендуется разработать план смягчения последствий")
        
        # Сравнение с альтернативами (если есть)
        if len(self.decisions) > 1:
            recommendations.append("📊 Для выбора оптимального решения сравните несколько альтернатив")
        
        # Горизонт планирования
        if scenario == ScenarioType.OPTIMISTIC:
            recommendations.append("🎯 При оптимистичном сценарии — можно реализовывать в полном объёме")
        elif scenario == ScenarioType.PESSIMISTIC:
            recommendations.append("🛡️ При пессимистичном сценарии — рекомендуется пилотный запуск")
        elif scenario == ScenarioType.CATASTROPHIC:
            recommendations.append("🔴 КАТАСТРОФИЧЕСКИЙ СЦЕНАРИЙ: отложить решение или полностью пересмотреть")
        
        return recommendations
    
    def _calculate_confidence(self, scenario: ScenarioType, decision: Decision, horizon: int) -> float:
        """Расчёт уверенности в прогнозе"""
        base_confidence = {
            ScenarioType.OPTIMISTIC: 0.6,
            ScenarioType.REALISTIC: 0.75,
            ScenarioType.PESSIMISTIC: 0.65,
            ScenarioType.CATASTROPHIC: 0.5
        }.get(scenario, 0.6)
        
        # Чем дальше горизонт, тем ниже уверенность
        horizon_factor = max(0.5, 1.0 - horizon / 365)
        
        # Чем сложнее решение, тем ниже уверенность
        complexity_factor = 1.0 - min(0.3, len(decision.affected_vectors) / 20)
        
        return base_confidence * horizon_factor * complexity_factor
    
    # ==================== 3. СРАВНЕНИЕ АЛЬТЕРНАТИВ ====================
    
    async def compare_decisions(self,
                                  decision_ids: List[str],
                                  current_metrics: Dict[str, float],
                                  criteria: List[str] = None) -> DecisionComparison:
        """
        Сравнение нескольких альтернативных решений
        """
        if not criteria:
            criteria = ['effectiveness', 'speed', 'cost', 'safety', 'confidence']
        
        logger.info(f"Сравнение {len(decision_ids)} альтернативных решений")
        
        alternatives = []
        
        for decision_id in decision_ids:
            # Симуляция по реалистичному сценарию
            results = await self.simulate_decision(
                decision_id=decision_id,
                current_metrics=current_metrics,
                time_horizon_days=180
            )
            
            realistic_result = next((r for r in results if r.scenario == ScenarioType.REALISTIC), results[0] if results else None)
            
            if realistic_result:
                # Оценка по критериям
                evaluation = self._evaluate_by_criteria(
                    realistic_result, decision_id, criteria
                )
                alternatives.append(evaluation)
        
        # Определение лучшего по каждому критерию
        best_by_criteria = {}
        for criterion in criteria:
            best = max(alternatives, key=lambda x: x['scores'].get(criterion, 0))
            best_by_criteria[criterion] = best['decision_name']
        
        # Выявление компромиссов
        trade_offs = self._identify_trade_offs(alternatives, criteria)
        
        # Рекомендация
        recommended = await self._recommend_best_alternative(alternatives, criteria)
        
        return DecisionComparison(
            id=f"comp_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            baseline_metrics=current_metrics,
            alternatives=alternatives,
            best_by_criteria=best_by_criteria,
            trade_offs=trade_offs,
            recommended=recommended
        )
    
    def _evaluate_by_criteria(self,
                                result: SimulationResult,
                                decision_id: str,
                                criteria: List[str]) -> Dict:
        """
        Оценка решения по критериям
        """
        decision = self.decisions.get(decision_id)
        
        scores = {}
        
        for criterion in criteria:
            if criterion == 'effectiveness':
                # Суммарное улучшение метрик
                total_improvement = sum(max(0, v) for v in result.direct_effects.values())
                scores['effectiveness'] = min(1.0, total_improvement / 0.5)
            
            elif criterion == 'speed':
                # Скорость реализации
                if decision:
                    speed_score = 1.0 - min(1.0, decision.implementation_time_days / 180)
                    scores['speed'] = speed_score
            
            elif criterion == 'cost':
                # Экономическая эффективность
                if decision:
                    cost_score = 1.0 - min(1.0, decision.cost_million_rub / 500)
                    scores['cost'] = cost_score
            
            elif criterion == 'safety':
                # Безопасность (отсутствие негативных эффектов)
                negative_effects = sum(1 for v in result.direct_effects.values() if v < 0)
                safety_score = 1.0 - min(1.0, negative_effects / 5)
                scores['safety'] = safety_score
            
            elif criterion == 'confidence':
                # Уверенность в прогнозе
                scores['confidence'] = result.confidence
            
            elif criterion == 'side_effect_risk':
                # Риск побочных эффектов
                high_risk = sum(1 for s in result.side_effects if s.get('severity') == 'high')
                risk_score = 1.0 - min(1.0, high_risk / 3)
                scores['side_effect_risk'] = risk_score
            
            else:
                scores[criterion] = 0.5
        
        return {
            'decision_id': decision_id,
            'decision_name': decision.name if decision else 'Unknown',
            'scores': scores,
            'total_score': sum(scores.values()) / len(scores) if scores else 0,
            'final_metrics': result.final_metrics,
            'side_effects_count': len(result.side_effects)
        }
    
    def _identify_trade_offs(self, alternatives: List[Dict], criteria: List[str]) -> List[Dict]:
        """Выявление компромиссов между решениями"""
        trade_offs = []
        
        for i, alt1 in enumerate(alternatives):
            for alt2 in alternatives[i+1:]:
                trade = []
                
                for criterion in criteria:
                    score1 = alt1['scores'].get(criterion, 0)
                    score2 = alt2['scores'].get(criterion, 0)
                    
                    if abs(score1 - score2) > 0.2:
                        if score1 > score2:
                            trade.append(f"{alt1['decision_name']} лучше по {criterion}")
                        else:
                            trade.append(f"{alt2['decision_name']} лучше по {criterion}")
                
                if trade:
                    trade_offs.append({
                        'between': [alt1['decision_name'], alt2['decision_name']],
                        'trade_offs': trade
                    })
        
        return trade_offs
    
    async def _recommend_best_alternative(self, alternatives: List[Dict], criteria: List[str]) -> str:
        """Рекомендация лучшей альтернативы"""
        if not alternatives:
            return "Нет альтернатив для сравнения"
        
        # Взвешенная оценка (приоритет effectiveness и safety)
        weights = {'effectiveness': 0.35, 'safety': 0.25, 'cost': 0.2, 'speed': 0.1, 'confidence': 0.1}
        
        best_alternative = None
        best_score = -1
        
        for alt in alternatives:
            weighted_score = 0
            for criterion, weight in weights.items():
                weighted_score += alt['scores'].get(criterion, 0) * weight
            
            if weighted_score > best_score:
                best_score = weighted_score
                best_alternative = alt['decision_name']
        
        return best_alternative
    
    # ==================== 4. АНАЛИЗ "ЧТО ЕСЛИ" ====================
    
    async def what_if_analysis(self,
                                 base_metrics: Dict[str, float],
                                 variables: Dict[str, Any],
                                 time_horizon_days: int = 180) -> Dict[str, Any]:
        """
        Анализ "Что если" — изменение параметров без конкретного решения
        """
        logger.info(f"Запуск what-if анализа с переменными: {list(variables.keys())}")
        
        results = {
            'baseline': base_metrics.copy(),
            'scenarios': [],
            'sensitivity': {}
        }
        
        # Базовый прогноз без изменений
        baseline_projection = await self._project_metrics(base_metrics, time_horizon_days)
        results['baseline_projection'] = baseline_projection
        
        # Для каждой переменной
        for var_name, var_value in variables.items():
            modified_metrics = base_metrics.copy()
            
            # Применяем изменение
            if var_name in modified_metrics:
                modified_metrics[var_name] = var_value
            
            # Прогноз с изменением
            projection = await self._project_metrics(modified_metrics, time_horizon_days)
            
            # Оценка чувствительности
            delta = projection['final'] - baseline_projection['final']
            
            results['scenarios'].append({
                'variable': var_name,
                'new_value': var_value,
                'projection': projection,
                'impact': delta
            })
            
            results['sensitivity'][var_name] = {
                'elasticity': abs(delta.get(var_name, 0) / (var_value - base_metrics.get(var_name, 3)) if var_value != base_metrics.get(var_name, 3) else 0),
                'impact': delta
            }
        
        return results
    
    async def _project_metrics(self, metrics: Dict[str, float], days: int) -> Dict:
        """
        Проекция метрик на будущее (простая экстраполяция)
        """
        # Простая модель: метрики имеют тенденцию возвращаться к среднему (3.5)
        mean_reversion = 0.02  # 2% в день
        
        final = {}
        for vector, value in metrics.items():
            # Дрейф к среднему
            target = 3.5
            drift = (target - value) * mean_reversion * days
            final[vector] = max(1.0, min(6.0, value + drift))
        
        return {
            'initial': metrics,
            'final': final,
            'days': days
        }
    
    # ==================== 5. ДАШБОРД И ОТЧЁТНОСТЬ ====================
    
    async def get_simulator_dashboard(self) -> Dict[str, Any]:
        """
        Получение дашборда симулятора решений
        """
        return {
            'timestamp': datetime.now().isoformat(),
            'city': self.city_name,
            'statistics': {
                'total_decisions_simulated': len(self.decision_history),
                'active_decisions': len(self.decisions),
                'average_confidence': np.mean([r.confidence for r in self.simulation_results.values()]) if self.simulation_results else 0
            },
            'recent_simulations': [
                {
                    'decision_name': h['decision_name'],
                    'timestamp': h['timestamp'].isoformat(),
                    'scenarios': h['results']
                }
                for h in self.decision_history[-5:]
            ],
            'available_decision_types': [dt.value for dt in DecisionType],
            'recommended_next_actions': await self._get_recommendations()
        }
    
    async def _get_recommendations(self) -> List[str]:
        """Рекомендации по использованию симулятора"""
        recommendations = [
            "💡 Перед принятием важного решения — протестируйте его в симуляторе",
            "📊 Сравнивайте 2-3 альтернативы, чтобы выбрать оптимальную",
            "🎯 Учитывайте не только прямые, но и косвенные эффекты",
            "⚠️ Обращайте внимание на побочные эффекты в сценариях",
            "🔄 Периодически пересматривайте решения при изменении ситуации"
        ]
        return recommendations
    
    # ==================== 6. ЭКСПОРТ ОТЧЁТОВ ====================
    
    async def export_simulation_report(self, simulation_id: str) -> Dict:
        """
        Экспорт отчёта по симуляции для презентации
        """
        result = self.simulation_results.get(simulation_id)
        if not result:
            return {'error': 'Simulation not found'}
        
        decision = self.decisions.get(result.decision_id)
        
        return {
            'report_id': f"rep_{simulation_id}",
            'generated_at': datetime.now().isoformat(),
            'decision': {
                'name': decision.name if decision else 'Unknown',
                'description': decision.description if decision else '',
                'type': decision.type.value if decision else '',
                'cost_million_rub': decision.cost_million_rub if decision else 0,
                'implementation_time_days': decision.implementation_time_days if decision else 0
            },
            'simulation': {
                'scenario': result.scenario.value,
                'probability': result.probability,
                'time_horizon_days': result.time_horizon_days,
                'confidence': result.confidence
            },
            'effects': {
                'direct': result.direct_effects,
                'indirect': [
                    {'target': e['target_vector'], 'change': e['total_change']}
                    for e in result.indirect_effects
                ],
                'side_effects': result.side_effects
            },
            'final_metrics': result.final_metrics,
            'recommendations': result.recommendations,
            'visualization_data': self._prepare_visualization_data(result)
        }
    
    def _prepare_visualization_data(self, result: SimulationResult) -> Dict:
        """Подготовка данных для визуализации"""
        return {
            'metrics_before': {'СБ': 3.5, 'ТФ': 3.5, 'УБ': 3.5, 'ЧВ': 3.5},  # заглушка
            'metrics_after': result.final_metrics,
            'changes': result.direct_effects,
            'timeline': [
                {'day': 0, 'metrics': {'СБ': 3.5, 'ТФ': 3.5, 'УБ': 3.5, 'ЧВ': 3.5}},
                {'day': result.time_horizon_days, 'metrics': result.final_metrics}
            ]
        }


# ==================== ИНТЕГРАЦИЯ С ОСНОВНЫМ ПРИЛОЖЕНИЕМ ====================

async def create_decision_simulator(city_name: str, model=None) -> DecisionSimulator:
    """Фабричная функция для создания симулятора решений"""
    return DecisionSimulator(city_name, model)


# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("🧪 Тестирование DecisionSimulator...")
        
        # Создаём симулятор
        simulator = DecisionSimulator("Коломна")
        
        # 1. Создаём решение
        decision = await simulator.create_decision(
            name="Усиление патрулирования в проблемных районах",
            description="Увеличение количества патрулей в 2 раза, установка 50 камер",
            decision_type=DecisionType.SAFETY,
            parameters={'subtype': 'patrol_increase', 'intensity': 1.2, 'budget': 15},
            cost=15.0,
            implementation_time=30,
            affected_vectors=['СБ', 'ЧВ']
        )
        
        print(f"\n📋 СОЗДАНО РЕШЕНИЕ:")
        print(f"  Название: {decision.name}")
        print(f"  Бюджет: {decision.cost_million_rub} млн ₽")
        print(f"  Срок: {decision.implementation_time_days} дней")
        
        # 2. Симуляция
        current_metrics = {'СБ': 3.2, 'ТФ': 3.8, 'УБ': 4.2, 'ЧВ': 3.5}
        
        results = await simulator.simulate_decision(
            decision_id=decision.id,
            current_metrics=current_metrics,
            time_horizon_days=180
        )
        
        print(f"\n🔮 РЕЗУЛЬТАТЫ СИМУЛЯЦИИ:")
        for r in results:
            print(f"\n  Сценарий: {r.scenario.value} (вероятность {r.probability:.0%})")
            print(f"    Прямые эффекты: {r.direct_effects}")
            print(f"    Итоговые метрики: СБ={r.final_metrics.get('СБ', 0):.1f}, ТФ={r.final_metrics.get('ТФ', 0):.1f}")
            if r.recommendations:
                print(f"    Рекомендации: {r.recommendations[0]}")
        
        # 3. Сравнение альтернатив
        print(f"\n📊 СРАВНЕНИЕ АЛЬТЕРНАТИВ:")
        
        # Создаём второе решение
        decision2 = await simulator.create_decision(
            name="Социальная программа для молодёжи",
            description="Гранты и мероприятия для молодёжи",
            decision_type=DecisionType.SOCIAL,
            parameters={'subtype': 'youth_program', 'budget': 10},
            cost=10.0,
            implementation_time=60,
            affected_vectors=['ЧВ', 'УБ']
        )
        
        comparison = await simulator.compare_decisions(
            decision_ids=[decision.id, decision2.id],
            current_metrics=current_metrics
        )
        
        print(f"  Лучшее по эффективности: {comparison.best_by_criteria.get('effectiveness', 'Н/Д')}")
        print(f"  Лучшее по стоимости: {comparison.best_by_criteria.get('cost', 'Н/Д')}")
        print(f"  Рекомендовано: {comparison.recommended}")
        
        # 4. Анализ "Что если"
        print(f"\n❓ АНАЛИЗ 'ЧТО ЕСЛИ':")
        
        what_if = await simulator.what_if_analysis(
            base_metrics=current_metrics,
            variables={'СБ': 4.5, 'ТФ': 4.0},
            time_horizon_days=180
        )
        
        print(f"  Исходные метрики: СБ={current_metrics['СБ']:.1f}, ТФ={current_metrics['ТФ']:.1f}")
        print(f"  Чувствительность СБ: {what_if['sensitivity'].get('СБ', {}).get('elasticity', 0):.2f}")
        
        # 5. Дашборд
        dashboard = await simulator.get_simulator_dashboard()
        print(f"\n📊 ДАШБОРД СИМУЛЯТОРА:")
        print(f"  Всего симуляций: {dashboard['statistics']['total_decisions_simulated']}")
        print(f"  Средняя уверенность: {dashboard['statistics']['average_confidence']:.0%}")
        
        print("\n✅ Тест завершен")
    
    asyncio.run(demo())
