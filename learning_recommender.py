#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 16: ОБУЧЕНИЕ И РЕКОМЕНДАЦИИ (Learning Recommender)
Система машинного обучения для выявления успешных паттернов и персонализированных рекомендаций

Основан на методах:
- Анализ исторических данных успешных и провальных решений
- Выявление паттернов "что сработало"
- Персонализированные рекомендации для мэра
- A/B тестирование гипотез
- Непрерывное обучение на новых данных
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
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score
import pickle

logger = logging.getLogger(__name__)


# ==================== МОДЕЛИ ДАННЫХ ====================

class OutcomeType(Enum):
    """Тип исхода решения"""
    SUCCESS = "success"      # Успешное решение
    FAILURE = "failure"      # Провальное решение
    PARTIAL = "partial"      # Частично успешное
    NEUTRAL = "neutral"      # Нейтральное


@dataclass
class DecisionOutcome:
    """Исход принятого решения"""
    id: str
    decision_name: str
    decision_type: str
    context_before: Dict[str, float]   # метрики до решения
    context_after: Dict[str, float]    # метрики после решения
    outcome: OutcomeType
    success_score: float                # 0-1, степень успеха
    time_to_result_days: int
    cost_million_rub: float
    lessons_learned: List[str]
    implemented_at: datetime
    evaluated_at: datetime


@dataclass
class Pattern:
    """Выявленный паттерн"""
    id: str
    name: str
    description: str
    conditions: Dict[str, Any]          # условия, при которых паттерн работает
    actions: List[str]                  # рекомендуемые действия
    expected_outcome: OutcomeType
    success_probability: float          # 0-1
    confidence: float                   # 0-1, уверенность в паттерне
    examples: List[Dict]                # примеры использования
    first_discovered: datetime
    last_confirmed: datetime
    times_used: int = 0
    times_successful: int = 0


@dataclass
class Recommendation:
    """Персонализированная рекомендация"""
    id: str
    title: str
    description: str
    pattern_id: str
    priority: str                       # critical/high/medium/low
    expected_impact: Dict[str, float]   # ожидаемое влияние на метрики
    confidence: float
    actions: List[Dict]                 # конкретные шаги
    alternatives: List[str]             # альтернативные варианты
    risks: List[str]
    created_at: datetime
    expires_at: datetime
    is_implemented: bool = False
    feedback: Optional[str] = None


# ==================== КОНФИГУРАЦИЯ ====================

class LearningRecommenderConfig:
    """Конфигурация системы обучения"""
    
    # Исторические данные решений (в реальности — из БД)
    HISTORICAL_DECISIONS = [
        {
            "id": "dec_001",
            "decision_name": "Усиление патрулирования",
            "decision_type": "safety",
            "context_before": {"СБ": 3.2, "ТФ": 3.5, "УБ": 4.0, "ЧВ": 3.5},
            "context_after": {"СБ": 4.0, "ТФ": 3.6, "УБ": 4.1, "ЧВ": 3.6},
            "outcome": "success",
            "success_score": 0.85,
            "time_to_result_days": 30,
            "cost_million_rub": 15,
            "lessons_learned": ["Быстрый эффект", "Поддержка жителей", "Нужно закрепление"],
            "implemented_at": datetime(2025, 6, 1),
            "evaluated_at": datetime(2025, 7, 1)
        },
        {
            "id": "dec_002",
            "decision_name": "Повышение налогов для бизнеса",
            "decision_type": "economy",
            "context_before": {"СБ": 3.8, "ТФ": 3.5, "УБ": 4.2, "ЧВ": 3.2},
            "context_after": {"СБ": 3.7, "ТФ": 3.1, "УБ": 4.0, "ЧВ": 2.9},
            "outcome": "failure",
            "success_score": 0.25,
            "time_to_result_days": 90,
            "cost_million_rub": -8,
            "lessons_learned": ["Отток бизнеса", "Падение доверия", "Нужны налоговые льготы, а не повышение"],
            "implemented_at": datetime(2025, 3, 1),
            "evaluated_at": datetime(2025, 6, 1)
        },
        {
            "id": "dec_003",
            "decision_name": "Благоустройство набережной",
            "decision_type": "infrastructure",
            "context_before": {"СБ": 3.5, "ТФ": 3.4, "УБ": 3.8, "ЧВ": 3.3},
            "context_after": {"СБ": 3.7, "ТФ": 3.6, "УБ": 4.5, "ЧВ": 3.8},
            "outcome": "success",
            "success_score": 0.9,
            "time_to_result_days": 180,
            "cost_million_rub": 50,
            "lessons_learned": ["Долгосрочные проекты окупаются", "Повышает качество жизни", "Привлекает туристов"],
            "implemented_at": datetime(2024, 9, 1),
            "evaluated_at": datetime(2025, 3, 1)
        },
        {
            "id": "dec_004",
            "decision_name": "Игнорирование жалоб на дороги",
            "decision_type": "infrastructure",
            "context_before": {"СБ": 3.8, "ТФ": 3.6, "УБ": 3.9, "ЧВ": 3.5},
            "context_after": {"СБ": 3.6, "ТФ": 3.5, "УБ": 3.5, "ЧВ": 2.8},
            "outcome": "failure",
            "success_score": 0.15,
            "time_to_result_days": 60,
            "cost_million_rub": 0,
            "lessons_learned": ["Игнорирование проблем ухудшает всё", "Падение доверия", "Проблемы накапливаются"],
            "implemented_at": datetime(2025, 1, 1),
            "evaluated_at": datetime(2025, 3, 1)
        },
        {
            "id": "dec_005",
            "decision_name": "Открытые встречи с жителями",
            "decision_type": "social",
            "context_before": {"СБ": 3.6, "ТФ": 3.5, "УБ": 4.0, "ЧВ": 3.2},
            "context_after": {"СБ": 3.7, "ТФ": 3.5, "УБ": 4.1, "ЧВ": 3.8},
            "outcome": "success",
            "success_score": 0.75,
            "time_to_result_days": 45,
            "cost_million_rub": 0.5,
            "lessons_learned": ["Диалог повышает доверие", "Жители ценят внимание", "Быстрый эффект"],
            "implemented_at": datetime(2025, 5, 1),
            "evaluated_at": datetime(2025, 6, 15)
        }
    ]


# ==================== ОСНОВНОЙ КЛАСС ====================

class LearningRecommender:
    """
    Система обучения и персонализированных рекомендаций
    
    Позволяет мэру:
    - Учиться на успешных и провальных решениях
    - Получать персонализированные рекомендации
    - Видеть, что сработало в похожих ситуациях
    - Проводить A/B тестирование гипотез
    """
    
    def __init__(self, city_name: str, config: LearningRecommenderConfig = None):
        self.city_name = city_name
        self.config = config or LearningRecommenderConfig()
        
        # Данные
        self.decisions_history: List[DecisionOutcome] = []
        self.patterns: Dict[str, Pattern] = {}
        self.recommendations: List[Recommendation] = []
        
        # Модели ML
        self.success_predictor = None
        self.pattern_classifier = None
        self.is_trained = False
        
        # Инициализация
        self._load_historical_data()
        
        logger.info(f"LearningRecommender инициализирован для города {city_name}")
    
    def _load_historical_data(self):
        """Загрузка исторических данных"""
        for data in self.config.HISTORICAL_DECISIONS:
            outcome = DecisionOutcome(
                id=data['id'],
                decision_name=data['decision_name'],
                decision_type=data['decision_type'],
                context_before=data['context_before'],
                context_after=data['context_after'],
                outcome=OutcomeType(data['outcome']),
                success_score=data['success_score'],
                time_to_result_days=data['time_to_result_days'],
                cost_million_rub=data['cost_million_rub'],
                lessons_learned=data['lessons_learned'],
                implemented_at=data['implemented_at'],
                evaluated_at=data['evaluated_at']
            )
            self.decisions_history.append(outcome)
        
        logger.info(f"Загружено {len(self.decisions_history)} исторических решений")
    
    # ==================== 1. АНАЛИЗ УСПЕШНЫХ ПАТТЕРНОВ ====================
    
    async def analyze_patterns(self) -> List[Pattern]:
        """
        Анализ исторических данных для выявления успешных паттернов
        """
        logger.info("Начинаю анализ паттернов успешных решений...")
        
        patterns = []
        
        # Группируем по типу решений
        by_type = defaultdict(list)
        for decision in self.decisions_history:
            by_type[decision.decision_type].append(decision)
        
        # Анализ каждого типа
        for decision_type, decisions in by_type.items():
            # Успешные и провальные решения
            successful = [d for d in decisions if d.outcome == OutcomeType.SUCCESS]
            failed = [d for d in decisions if d.outcome == OutcomeType.FAILURE]
            
            if not successful:
                continue
            
            # Вычисляем общие черты успешных решений
            common_factors = await self._extract_common_factors(successful, failed)
            
            # Создаём паттерн
            pattern_id = f"pattern_{decision_type}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Определяем условия, при которых паттерн работает
            conditions = self._build_conditions(common_factors)
            
            # Рекомендуемые действия
            actions = self._build_actions(decision_type, successful)
            
            # Вероятность успеха
            success_rate = len(successful) / len(decisions) if decisions else 0
            confidence = min(0.95, success_rate + 0.1)  # небольшой бонус за уверенность
            
            pattern = Pattern(
                id=pattern_id,
                name=self._generate_pattern_name(decision_type, common_factors),
                description=self._generate_pattern_description(decision_type, common_factors),
                conditions=conditions,
                actions=actions,
                expected_outcome=OutcomeType.SUCCESS,
                success_probability=success_rate,
                confidence=confidence,
                examples=[
                    {
                        'decision_name': d.decision_name,
                        'success_score': d.success_score,
                        'time_to_result': d.time_to_result_days
                    }
                    for d in successful[:3]
                ],
                first_discovered=datetime.now(),
                last_confirmed=datetime.now(),
                times_used=len(successful),
                times_successful=len(successful)
            )
            
            patterns.append(pattern)
            self.patterns[pattern_id] = pattern
        
        logger.info(f"Выявлено {len(patterns)} паттернов успешных решений")
        return patterns
    
    async def _extract_common_factors(self, successful: List[DecisionOutcome], 
                                       failed: List[DecisionOutcome]) -> Dict[str, Any]:
        """Извлечение общих факторов успешных решений"""
        common = {}
        
        if not successful:
            return common
        
        # Анализ метрик до решения
        before_metrics = {
            'СБ': [],
            'ТФ': [],
            'УБ': [],
            'ЧВ': []
        }
        
        for decision in successful:
            for vector in before_metrics:
                before_metrics[vector].append(decision.context_before.get(vector, 3.0))
        
        # Средние значения
        for vector in before_metrics:
            if before_metrics[vector]:
                common[f'avg_{vector}_before'] = sum(before_metrics[vector]) / len(before_metrics[vector])
        
        # Анализ времени до результата
        avg_time = sum(d.time_to_result_days for d in successful) / len(successful)
        common['avg_time_to_result_days'] = avg_time
        
        # Анализ стоимости
        avg_cost = sum(d.cost_million_rub for d in successful) / len(successful)
        common['avg_cost_million_rub'] = avg_cost
        
        # Анализ улучшений
        improvements = {}
        for vector in ['СБ', 'ТФ', 'УБ', 'ЧВ']:
            improvements[vector] = sum(
                d.context_after.get(vector, 3.0) - d.context_before.get(vector, 3.0)
                for d in successful
            ) / len(successful)
        common['avg_improvements'] = improvements
        
        return common
    
    def _build_conditions(self, common_factors: Dict) -> Dict[str, Any]:
        """Построение условий применения паттерна"""
        conditions = {}
        
        if 'avg_СБ_before' in common_factors:
            conditions['safety_below'] = common_factors['avg_СБ_before'] < 3.5
        
        if 'avg_ТФ_before' in common_factors:
            conditions['economy_below'] = common_factors['avg_ТФ_before'] < 3.5
        
        if 'avg_time_to_result_days' in common_factors:
            conditions['quick_win_possible'] = common_factors['avg_time_to_result_days'] < 60
        
        return conditions
    
    def _build_actions(self, decision_type: str, successful: List[DecisionOutcome]) -> List[str]:
        """Построение рекомендуемых действий"""
        actions = []
        
        # Собираем уроки из успешных решений
        all_lessons = []
        for decision in successful:
            all_lessons.extend(decision.lessons_learned)
        
        # Берём самые частые
        from collections import Counter
        lesson_counts = Counter(all_lessons)
        top_lessons = lesson_counts.most_common(3)
        
        for lesson, count in top_lessons:
            actions.append(lesson)
        
        # Добавляем типовые действия по типу
        type_actions = {
            'safety': [
                "Усилить патрулирование в проблемных районах",
                "Установить камеры видеонаблюдения",
                "Вовлечь жителей в программы безопасности"
            ],
            'economy': [
                "Предоставить налоговые льготы для МСП",
                "Создать инвестиционный портал",
                "Провести встречи с предпринимателями"
            ],
            'infrastructure': [
                "Провести аудит инфраструктуры",
                "Составить план благоустройства",
                "Внедрить инициативное бюджетирование"
            ],
            'social': [
                "Организовать открытые встречи с жителями",
                "Запустить программу поддержки НКО",
                "Создать общественный совет"
            ]
        }
        
        actions.extend(type_actions.get(decision_type, [])[:2])
        
        return list(set(actions))[:5]
    
    def _generate_pattern_name(self, decision_type: str, common_factors: Dict) -> str:
        """Генерация названия паттерна"""
        type_names = {
            'safety': 'Безопасность',
            'economy': 'Экономика',
            'infrastructure': 'Инфраструктура',
            'social': 'Социальная сфера'
        }
        
        type_name = type_names.get(decision_type, decision_type)
        
        if common_factors.get('avg_time_to_result_days', 60) < 45:
            return f"Быстрая победа в сфере {type_name}"
        else:
            return f"Стратегический успех в сфере {type_name}"
    
    def _generate_pattern_description(self, decision_type: str, common_factors: Dict) -> str:
        """Генерация описания паттерна"""
        avg_time = common_factors.get('avg_time_to_result_days', 60)
        avg_cost = common_factors.get('avg_cost_million_rub', 10)
        improvements = common_factors.get('avg_improvements', {})
        
        best_improvement = max(improvements.items(), key=lambda x: x[1]) if improvements else ('УБ', 0.3)
        
        return (f"Паттерн показывает, что при текущем состоянии города инвестиции в развитие "
                f"приносят результат через {avg_time:.0f} дней. "
                f"Наибольший эффект ожидается в сфере {best_improvement[0]} "
                f"(улучшение на {best_improvement[1]:.1f} балла). "
                f"Типичный бюджет: {avg_cost:.0f} млн ₽.")
    
    # ==================== 2. ОБУЧЕНИЕ МОДЕЛЕЙ ====================
    
    async def train_models(self):
        """
        Обучение моделей машинного обучения для предсказания успеха решений
        """
        logger.info("Начинаю обучение моделей прогнозирования...")
        
        # Подготовка данных
        X = []
        y = []
        
        for decision in self.decisions_history:
            # Признаки: метрики до решения, тип решения, стоимость
            features = [
                decision.context_before.get('СБ', 3.0),
                decision.context_before.get('ТФ', 3.0),
                decision.context_before.get('УБ', 3.0),
                decision.context_before.get('ЧВ', 3.0),
                1 if decision.decision_type == 'safety' else 0,
                1 if decision.decision_type == 'economy' else 0,
                1 if decision.decision_type == 'infrastructure' else 0,
                1 if decision.decision_type == 'social' else 0,
                decision.cost_million_rub / 100,  # нормализация
                decision.time_to_result_days / 365
            ]
            X.append(features)
            y.append(1 if decision.outcome == OutcomeType.SUCCESS else 0)
        
        if len(X) < 10:
            logger.warning("Недостаточно данных для обучения моделей")
            return
        
        # Разделение на train/test
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Random Forest
        self.success_predictor = RandomForestClassifier(
            n_estimators=100,
            max_depth=5,
            random_state=42
        )
        self.success_predictor.fit(X_train, y_train)
        
        # Оценка
        y_pred = self.success_predictor.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, zero_division=0)
        recall = recall_score(y_test, y_pred, zero_division=0)
        
        self.is_trained = True
        
        logger.info(f"Модель обучена. Accuracy: {accuracy:.0%}, Precision: {precision:.0%}, Recall: {recall:.0%}")
    
    async def predict_success_probability(self, 
                                           decision_type: str,
                                           current_metrics: Dict[str, float],
                                           cost_million_rub: float,
                                           time_days: int) -> float:
        """
        Предсказание вероятности успеха решения
        """
        if not self.is_trained or not self.success_predictor:
            # Если модель не обучена, используем эвристику
            return self._heuristic_success_probability(decision_type, current_metrics, cost_million_rub, time_days)
        
        features = [
            current_metrics.get('СБ', 3.0),
            current_metrics.get('ТФ', 3.0),
            current_metrics.get('УБ', 3.0),
            current_metrics.get('ЧВ', 3.0),
            1 if decision_type == 'safety' else 0,
            1 if decision_type == 'economy' else 0,
            1 if decision_type == 'infrastructure' else 0,
            1 if decision_type == 'social' else 0,
            cost_million_rub / 100,
            time_days / 365
        ]
        
        proba = self.success_predictor.predict_proba([features])[0]
        return proba[1]  # вероятность успеха
    
    def _heuristic_success_probability(self, decision_type: str,
                                        current_metrics: Dict[str, float],
                                        cost_million_rub: float,
                                        time_days: int) -> float:
        """Эвристическая оценка вероятности успеха"""
        base_prob = 0.5
        
        # Корректировка по типу решения
        type_bonus = {
            'safety': 0.1,
            'infrastructure': 0.05,
            'social': 0.1,
            'economy': -0.05
        }
        base_prob += type_bonus.get(decision_type, 0)
        
        # Корректировка по стоимости (дешёвые решения чаще успешны)
        if cost_million_rub < 10:
            base_prob += 0.1
        elif cost_million_rub > 100:
            base_prob -= 0.1
        
        # Корректировка по времени (быстрые решения чаще успешны)
        if time_days < 30:
            base_prob += 0.1
        elif time_days > 180:
            base_prob -= 0.1
        
        # Корректировка по текущим метрикам
        avg_metric = sum(current_metrics.values()) / 4
        if avg_metric < 3.0:
            base_prob += 0.1  # есть куда расти
        elif avg_metric > 4.5:
            base_prob -= 0.1  # сложно улучшать
        
        return max(0.1, min(0.95, base_prob))
    
    # ==================== 3. ГЕНЕРАЦИЯ РЕКОМЕНДАЦИЙ ====================
    
    async def generate_recommendations(self, 
                                        current_metrics: Dict[str, float],
                                        urgent_issues: List[str] = None) -> List[Recommendation]:
        """
        Генерация персонализированных рекомендаций на основе текущей ситуации
        """
        logger.info("Генерация персонализированных рекомендаций...")
        
        recommendations = []
        
        # 1. Анализ паттернов
        patterns = await self.analyze_patterns()
        
        # 2. Для каждого паттерна проверяем, подходит ли он под текущую ситуацию
        for pattern in patterns:
            is_applicable = await self._is_pattern_applicable(pattern, current_metrics)
            
            if is_applicable:
                # Ожидаемый эффект
                expected_impact = self._estimate_impact(pattern, current_metrics)
                
                # Приоритет
                priority = self._determine_priority(pattern, current_metrics, urgent_issues)
                
                # Конкретные шаги
                actions = self._detail_actions(pattern.actions, current_metrics)
                
                recommendation = Recommendation(
                    id=f"rec_{datetime.now().strftime('%Y%m%d%H%M%S')}_{pattern.id[-6:]}",
                    title=f"💡 {pattern.name}",
                    description=pattern.description,
                    pattern_id=pattern.id,
                    priority=priority,
                    expected_impact=expected_impact,
                    confidence=pattern.confidence,
                    actions=actions,
                    alternatives=self._generate_alternatives(pattern),
                    risks=self._identify_risks(pattern),
                    created_at=datetime.now(),
                    expires_at=datetime.now() + timedelta(days=30)
                )
                recommendations.append(recommendation)
        
        # 3. Сортируем по приоритету и уверенности
        priority_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        recommendations.sort(key=lambda x: (priority_order.get(x.priority, 0), x.confidence), reverse=True)
        
        self.recommendations = recommendations
        
        logger.info(f"Сгенерировано {len(recommendations)} рекомендаций")
        return recommendations
    
    async def _is_pattern_applicable(self, pattern: Pattern, current_metrics: Dict[str, float]) -> bool:
        """Проверка применимости паттерна к текущей ситуации"""
        conditions = pattern.conditions
        
        # Проверка условий
        if conditions.get('safety_below', False):
            if current_metrics.get('СБ', 4.0) >= 3.5:
                return False
        
        if conditions.get('economy_below', False):
            if current_metrics.get('ТФ', 4.0) >= 3.5:
                return False
        
        # Если все условия выполнены или условий нет
        return True
    
    def _estimate_impact(self, pattern: Pattern, current_metrics: Dict[str, float]) -> Dict[str, float]:
        """Оценка ожидаемого влияния на метрики"""
        impact = {'СБ': 0, 'ТФ': 0, 'УБ': 0, 'ЧВ': 0}
        
        # На основе исторических улучшений
        if pattern.id.startswith('pattern_safety'):
            impact['СБ'] = 0.4
            impact['ЧВ'] = 0.2
        elif pattern.id.startswith('pattern_economy'):
            impact['ТФ'] = 0.3
            impact['УБ'] = 0.1
        elif pattern.id.startswith('pattern_infrastructure'):
            impact['УБ'] = 0.5
            impact['СБ'] = 0.1
        elif pattern.id.startswith('pattern_social'):
            impact['ЧВ'] = 0.4
            impact['УБ'] = 0.2
        
        # Корректировка с учётом текущего состояния
        for vector in impact:
            if current_metrics.get(vector, 3.0) > 5.0:
                impact[vector] *= 0.5  # меньше потенциала для улучшения
        
        return impact
    
    def _determine_priority(self, pattern: Pattern, 
                             current_metrics: Dict[str, float],
                             urgent_issues: List[str]) -> str:
        """Определение приоритета рекомендации"""
        # Проверяем, соответствует ли паттерн срочным проблемам
        if urgent_issues:
            pattern_keywords = {
                'safety': ['безопасность', 'преступность', 'страх'],
                'economy': ['экономика', 'бизнес', 'работа'],
                'infrastructure': ['дороги', 'жкх', 'транспорт'],
                'social': ['доверие', 'соцсети', 'жалобы']
            }
            
            for issue in urgent_issues:
                for key, keywords in pattern_keywords.items():
                    if key in pattern.id and any(kw in issue.lower() for kw in keywords):
                        return 'critical'
        
        # Приоритет по текущим метрикам
        if pattern.id.startswith('pattern_safety') and current_metrics.get('СБ', 4.0) < 3.0:
            return 'critical'
        elif pattern.id.startswith('pattern_economy') and current_metrics.get('ТФ', 4.0) < 3.0:
            return 'high'
        elif pattern.id.startswith('pattern_infrastructure') and current_metrics.get('УБ', 4.0) < 3.5:
            return 'high'
        elif pattern.confidence > 0.8:
            return 'medium'
        else:
            return 'low'
    
    def _detail_actions(self, actions: List[str], current_metrics: Dict[str, float]) -> List[Dict]:
        """Детализация действий с конкретными параметрами"""
        detailed = []
        
        for action in actions:
            detailed.append({
                'step': action,
                'responsible': self._suggest_responsible(action),
                'timeline': self._suggest_timeline(action),
                'estimated_cost': self._estimate_cost(action),
                'metrics_to_track': self._suggest_metrics(action)
            })
        
        return detailed
    
    def _suggest_responsible(self, action: str) -> str:
        """Предложение ответственного за действие"""
        if 'безопасн' in action.lower() or 'патрул' in action.lower():
            return 'Департамент безопасности'
        elif 'налог' in action.lower() or 'бизнес' in action.lower():
            return 'Департамент экономики'
        elif 'благоустр' in action.lower() or 'дорог' in action.lower():
            return 'Департамент инфраструктуры'
        elif 'встреч' in action.lower() or 'жител' in action.lower():
            return 'Департамент социальной политики'
        else:
            return 'Профильный департамент'
    
    def _suggest_timeline(self, action: str) -> str:
        """Предложение сроков выполнения"""
        if 'быстр' in action.lower() or 'срочн' in action.lower():
            return '1-2 недели'
        elif 'налог' in action.lower():
            return '1-2 месяца'
        elif 'благоустр' in action.lower():
            return '3-6 месяцев'
        else:
            return '1-3 месяца'
    
    def _estimate_cost(self, action: str) -> str:
        """Оценка стоимости действия"""
        if 'патрул' in action.lower() or 'встреч' in action.lower():
            return 'Низкий (0.5-2 млн ₽)'
        elif 'камер' in action.lower() or 'налог' in action.lower():
            return 'Средний (5-15 млн ₽)'
        elif 'благоустр' in action.lower():
            return 'Высокий (20-50 млн ₽)'
        else:
            return 'Средний (5-15 млн ₽)'
    
    def _suggest_metrics(self, action: str) -> List[str]:
        """Предложение метрик для отслеживания"""
        if 'безопасн' in action.lower():
            return ['Уровень преступности', 'Доверие к полиции', 'Индекс страха']
        elif 'экономик' in action.lower():
            return ['Количество МСП', 'Налоговые поступления', 'Уровень безработицы']
        elif 'благоустр' in action.lower():
            return ['Качество дорог', 'Количество жалоб', 'Индекс комфорта']
        else:
            return ['Удовлетворённость жителей', 'Охват мероприятий']
    
    def _generate_alternatives(self, pattern: Pattern) -> List[str]:
        """Генерация альтернативных вариантов"""
        return [
            "Начать с пилотного проекта в одном районе",
            "Привлечь внешних экспертов для оценки",
            "Провести общественные слушания перед реализацией"
        ]
    
    def _identify_risks(self, pattern: Pattern) -> List[str]:
        """Идентификация рисков"""
        risks = [
            "Недостаточное финансирование",
            "Сопротивление со стороны заинтересованных лиц",
            "Затягивание сроков реализации"
        ]
        
        if 'safety' in pattern.id:
            risks.append("Рост недоверия при неудачной реализации")
        elif 'economy' in pattern.id:
            risks.append("Временное снижение налоговых поступлений")
        
        return risks
    
    # ==================== 4. A/B ТЕСТИРОВАНИЕ ====================
    
    async def create_ab_test(self, 
                              recommendation_id: str,
                              test_duration_days: int = 30) -> Dict[str, Any]:
        """
        Создание A/B теста для проверки гипотезы
        """
        recommendation = next((r for r in self.recommendations if r.id == recommendation_id), None)
        if not recommendation:
            return {'error': 'Recommendation not found'}
        
        ab_test = {
            'id': f"abtest_{recommendation_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'recommendation_id': recommendation_id,
            'title': recommendation.title,
            'start_date': datetime.now(),
            'end_date': datetime.now() + timedelta(days=test_duration_days),
            'status': 'active',
            'metrics_before': {},  # будет заполнено
            'metrics_after': {},
            'control_group': [],   # районы/проекты без вмешательства
            'test_group': [],      # районы/проекты с вмешательством
            'results': None
        }
        
        logger.info(f"Создан A/B тест для рекомендации '{recommendation.title}'")
        return ab_test
    
    # ==================== 5. СБОР ОБРАТНОЙ СВЯЗИ ====================
    
    async def collect_feedback(self, recommendation_id: str, feedback: str, success_rating: int) -> bool:
        """
        Сбор обратной связи о реализованной рекомендации
        """
        recommendation = next((r for r in self.recommendations if r.id == recommendation_id), None)
        if not recommendation:
            return False
        
        recommendation.is_implemented = True
        recommendation.feedback = feedback
        
        # Обновляем паттерн
        pattern = self.patterns.get(recommendation.pattern_id)
        if pattern:
            pattern.times_used += 1
            if success_rating >= 4:  # 4-5 звёзд = успех
                pattern.times_successful += 1
            pattern.last_confirmed = datetime.now()
        
        logger.info(f"Получена обратная связь для рекомендации '{recommendation.title}': {success_rating}/5")
        return True
    
    # ==================== 6. ДАШБОРД ====================
    
    async def get_learning_dashboard(self) -> Dict[str, Any]:
        """
        Получение дашборда системы обучения
        """
        # Статистика по решениям
        total_decisions = len(self.decisions_history)
        successful = sum(1 for d in self.decisions_history if d.outcome == OutcomeType.SUCCESS)
        failed = sum(1 for d in self.decisions_history if d.outcome == OutcomeType.FAILURE)
        
        # Статистика по паттернам
        total_patterns = len(self.patterns)
        high_confidence_patterns = sum(1 for p in self.patterns.values() if p.confidence > 0.7)
        
        # Активные рекомендации
        active_recommendations = [r for r in self.recommendations if not r.is_implemented and r.expires_at > datetime.now()]
        
        # Успешность паттернов
        pattern_success_rates = []
        for pattern in self.patterns.values():
            if pattern.times_used > 0:
                rate = pattern.times_successful / pattern.times_used
                pattern_success_rates.append(rate)
        
        avg_pattern_success = sum(pattern_success_rates) / len(pattern_success_rates) if pattern_success_rates else 0
        
        return {
            'timestamp': datetime.now().isoformat(),
            'city': self.city_name,
            'statistics': {
                'total_decisions_analyzed': total_decisions,
                'successful_decisions': successful,
                'failed_decisions': failed,
                'success_rate': successful / total_decisions if total_decisions > 0 else 0,
                'total_patterns_discovered': total_patterns,
                'high_confidence_patterns': high_confidence_patterns,
                'active_recommendations': len(active_recommendations),
                'avg_pattern_success_rate': avg_pattern_success
            },
            'top_patterns': [
                {
                    'name': p.name,
                    'success_probability': p.success_probability,
                    'confidence': p.confidence,
                    'times_used': p.times_used,
                    'successful': p.times_successful
                }
                for p in sorted(self.patterns.values(), key=lambda x: x.confidence, reverse=True)[:5]
            ],
            'active_recommendations': [
                {
                    'id': r.id,
                    'title': r.title,
                    'priority': r.priority,
                    'confidence': r.confidence,
                    'expires_at': r.expires_at.isoformat()
                }
                for r in active_recommendations[:5]
            ],
            'lessons_learned': self._extract_key_lessons()
        }
    
    def _extract_key_lessons(self) -> List[str]:
        """Извлечение ключевых уроков из истории решений"""
        all_lessons = []
        for decision in self.decisions_history:
            all_lessons.extend(decision.lessons_learned)
        
        # Берём самые частые
        from collections import Counter
        lesson_counts = Counter(all_lessons)
        
        return [lesson for lesson, _ in lesson_counts.most_common(5)]


# ==================== ИНТЕГРАЦИЯ С ОСНОВНЫМ ПРИЛОЖЕНИЕМ ====================

async def create_learning_recommender(city_name: str) -> LearningRecommender:
    """Фабричная функция для создания системы обучения"""
    return LearningRecommender(city_name)


# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("🧪 Тестирование LearningRecommender...")
        
        # Создаём систему обучения
        recommender = LearningRecommender("Коломна")
        
        # 1. Анализ паттернов
        print("\n📊 АНАЛИЗ ПАТТЕРНОВ:")
        patterns = await recommender.analyze_patterns()
        for p in patterns[:3]:
            print(f"  • {p.name} (уверенность {p.confidence:.0%})")
            print(f"    {p.description[:80]}...")
        
        # 2. Обучение модели
        print("\n🤖 ОБУЧЕНИЕ МОДЕЛИ:")
        await recommender.train_models()
        print(f"  Модель обучена: {recommender.is_trained}")
        
        # 3. Генерация рекомендаций
        print("\n💡 ГЕНЕРАЦИЯ РЕКОМЕНДАЦИЙ:")
        current_metrics = {'СБ': 3.2, 'ТФ': 3.5, 'УБ': 4.0, 'ЧВ': 3.3}
        urgent_issues = ["жалобы на безопасность", "негатив в соцсетях"]
        
        recommendations = await recommender.generate_recommendations(current_metrics, urgent_issues)
        
        for rec in recommendations[:3]:
            print(f"\n  [{rec.priority.upper()}] {rec.title}")
            print(f"    {rec.description[:100]}...")
            print(f"    Уверенность: {rec.confidence:.0%}")
            print(f"    Ожидаемый эффект: {rec.expected_impact}")
            if rec.actions:
                print(f"    Первый шаг: {rec.actions[0]['step']}")
        
        # 4. Предсказание успеха
        print("\n🔮 ПРЕДСКАЗАНИЕ УСПЕХА:")
        prob = await recommender.predict_success_probability(
            decision_type="safety",
            current_metrics=current_metrics,
            cost_million_rub=15,
            time_days=30
        )
        print(f"  Вероятность успеха решения по безопасности: {prob:.0%}")
        
        # 5. Дашборд
        print("\n📋 ДАШБОРД ОБУЧЕНИЯ:")
        dashboard = await recommender.get_learning_dashboard()
        print(f"  Всего решений проанализировано: {dashboard['statistics']['total_decisions_analyzed']}")
        print(f"  Успешность решений: {dashboard['statistics']['success_rate']:.0%}")
        print(f"  Выявлено паттернов: {dashboard['statistics']['total_patterns_discovered']}")
        print(f"  Активных рекомендаций: {dashboard['statistics']['active_recommendations']}")
        
        if dashboard['lessons_learned']:
            print(f"  Ключевые уроки: {', '.join(dashboard['lessons_learned'][:3])}")
        
        print("\n✅ Тест завершен")
    
    asyncio.run(demo())
