#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 13: ПЛАНИРОВЩИК РЕСУРСОВ (Resource Planner)
Система оптимального распределения бюджетных, человеческих и временных ресурсов

Основан на методах:
- Многокритериальная оптимизация
- Линейное и целочисленное программирование
- ROI-анализ и приоритизация проектов
- Trade-off анализ и балансировка ресурсов
- Сценарное планирование бюджета
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

class ResourceType(Enum):
    """Типы ресурсов"""
    BUDGET = "budget"           # Финансовые ресурсы (млн ₽)
    PERSONNEL = "personnel"     # Человеческие ресурсы (человеко-часы)
    TIME = "time"               # Временные ресурсы (дни)
    EQUIPMENT = "equipment"     # Материально-технические
    ADMIN = "admin"             # Административный ресурс


class Priority(Enum):
    """Приоритет задач"""
    CRITICAL = "critical"   # Критический (срочно и важно)
    HIGH = "high"           # Высокий
    MEDIUM = "medium"       # Средний
    LOW = "low"             # Низкий
    BACKLOG = "backlog"     # Бэклог


@dataclass
class Task:
    """Задача/проект для планирования"""
    id: str
    name: str
    description: str
    priority: Priority
    resources_needed: Dict[ResourceType, float]  # необходимые ресурсы
    duration_days: int                           # длительность
    dependencies: List[str]                      # ID зависимых задач
    expected_roi: float                          # ожидаемая ROI (0-1)
    affected_vectors: List[str]                  # векторы Мейстера
    deadline: Optional[datetime] = None
    assigned_to: Optional[str] = None
    status: str = "planned"                      # planned/in_progress/completed


@dataclass
class ResourcePool:
    """Пул доступных ресурсов"""
    timestamp: datetime
    budget_million_rub: float           # бюджет в млн ₽
    personnel_hours: int                # человеко-часы в месяц
    time_days: int                      # временной горизонт
    equipment_units: Dict[str, int]     # единицы техники
    admin_capacity: float               # административная ёмкость (0-1)
    
    # Распределение по департаментам
    department_budgets: Dict[str, float]
    department_personnel: Dict[str, int]


@dataclass
class AllocationPlan:
    """План распределения ресурсов"""
    id: str
    timestamp: datetime
    horizon_days: int
    total_budget: float
    allocated_tasks: List[Dict]
    unallocated_tasks: List[Dict]
    resource_utilization: Dict[str, float]  # использование ресурсов
    expected_impact: Dict[str, float]       # ожидаемое влияние на метрики
    total_roi: float
    risks: List[Dict]
    recommendations: List[str]


# ==================== КОНФИГУРАЦИЯ ====================

class ResourcePlannerConfig:
    """Конфигурация планировщика ресурсов"""
    
    # Веса для оптимизации
    OPTIMIZATION_WEIGHTS = {
        'roi': 0.35,
        'strategic_importance': 0.25,
        'urgency': 0.20,
        'resource_efficiency': 0.20
    }
    
    # Минимальные и максимальные значения
    MIN_BUDGET_PER_TASK = 0.5  # млн ₽
    MAX_BUDGET_PER_TASK = 500   # млн ₽
    
    # Коэффициенты конвертации
    PERSONNEL_COST_PER_HOUR = 0.002  # млн ₽ за человеко-час
    EQUIPMENT_COST_PER_UNIT = 0.5    # млн ₽ за единицу
    
    # Департаменты
    DEPARTMENTS = [
        "Безопасность", "Экономика", "Инфраструктура",
        "Социальная сфера", "Экология", "Транспорт",
        "ЖКХ", "Культура", "Образование", "Здравоохранение"
    ]


# ==================== ОСНОВНОЙ КЛАСС ====================

class ResourcePlanner:
    """
    Планировщик ресурсов — оптимальное распределение бюджетных средств
    
    Позволяет мэру:
    - Оптимально распределить бюджет между проектами
    - Увидеть ROI каждого вложения
    - Сбалансировать ресурсы между департаментами
    - Сравнить сценарии распределения
    """
    
    def __init__(self, city_name: str, config: ResourcePlannerConfig = None):
        self.city_name = city_name
        self.config = config or ResourcePlannerConfig()
        
        # Хранилище
        self.tasks: Dict[str, Task] = {}
        self.allocation_plans: List[AllocationPlan] = []
        self.current_resources: Optional[ResourcePool] = None
        
        # Кэш для расчётов
        self.roi_cache = {}
        
        # История
        self.history = []
        
        logger.info(f"ResourcePlanner инициализирован для города {city_name}")
    
    # ==================== 1. УПРАВЛЕНИЕ ЗАДАЧАМИ ====================
    
    async def add_task(self,
                        name: str,
                        description: str,
                        priority: Priority,
                        budget_needed: float,
                        personnel_needed: int,
                        duration_days: int,
                        expected_roi: float,
                        affected_vectors: List[str],
                        dependencies: List[str] = None,
                        deadline: datetime = None) -> Task:
        """
        Добавление задачи в план
        """
        task_id = f"task_{hashlib.md5(f'{name}_{datetime.now().isoformat()}'.encode()).hexdigest()[:8]}"
        
        task = Task(
            id=task_id,
            name=name,
            description=description,
            priority=priority,
            resources_needed={
                ResourceType.BUDGET: budget_needed,
                ResourceType.PERSONNEL: personnel_needed,
                ResourceType.TIME: duration_days
            },
            duration_days=duration_days,
            dependencies=dependencies or [],
            expected_roi=expected_roi,
            affected_vectors=affected_vectors,
            deadline=deadline
        )
        
        self.tasks[task_id] = task
        
        logger.info(f"Добавлена задача '{name}' с бюджетом {budget_needed} млн ₽")
        return task
    
    async def remove_task(self, task_id: str) -> bool:
        """Удаление задачи"""
        if task_id in self.tasks:
            del self.tasks[task_id]
            logger.info(f"Удалена задача {task_id}")
            return True
        return False
    
    async def update_task_priority(self, task_id: str, new_priority: Priority) -> bool:
        """Обновление приоритета задачи"""
        if task_id in self.tasks:
            self.tasks[task_id].priority = new_priority
            logger.info(f"Обновлён приоритет задачи {task_id} -> {new_priority.value}")
            return True
        return False
    
    # ==================== 2. УПРАВЛЕНИЕ РЕСУРСАМИ ====================
    
    async def set_resources(self,
                             budget_million_rub: float,
                             personnel_hours: int,
                             time_horizon_days: int,
                             department_budgets: Dict[str, float] = None) -> ResourcePool:
        """
        Установка доступных ресурсов
        """
        if department_budgets is None:
            # Равномерное распределение по департаментам
            per_department = budget_million_rub / len(self.config.DEPARTMENTS)
            department_budgets = {dept: per_department for dept in self.config.DEPARTMENTS}
        
        self.current_resources = ResourcePool(
            timestamp=datetime.now(),
            budget_million_rub=budget_million_rub,
            personnel_hours=personnel_hours,
            time_days=time_horizon_days,
            equipment_units={},
            admin_capacity=1.0,
            department_budgets=department_budgets,
            department_personnel={dept: personnel_hours // len(self.config.DEPARTMENTS) 
                                  for dept in self.config.DEPARTMENTS}
        )
        
        logger.info(f"Установлены ресурсы: бюджет {budget_million_rub} млн ₽, "
                   f"персонал {personnel_hours} чел-ч, горизонт {time_horizon_days} дней")
        
        return self.current_resources
    
    # ==================== 3. ОПТИМИЗАЦИЯ РАСПРЕДЕЛЕНИЯ ====================
    
    async def optimize_allocation(self, 
                                    resources: ResourcePool = None,
                                    priority_weights: Dict[str, float] = None) -> AllocationPlan:
        """
        Оптимальное распределение ресурсов с учётом приоритетов и ROI
        """
        if resources is None:
            resources = self.current_resources
        
        if not resources:
            raise ValueError("Ресурсы не установлены")
        
        if not self.tasks:
            return AllocationPlan(
                id=f"plan_empty_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                timestamp=datetime.now(),
                horizon_days=resources.time_days,
                total_budget=resources.budget_million_rub,
                allocated_tasks=[],
                unallocated_tasks=[],
                resource_utilization={},
                expected_impact={},
                total_roi=0,
                risks=[],
                recommendations=["Нет задач для планирования"]
            )
        
        weights = priority_weights or self.config.OPTIMIZATION_WEIGHTS
        
        # 1. Оценка каждой задачи
        task_scores = await self._score_tasks(resources, weights)
        
        # 2. Сортировка по приоритету и эффективности
        sorted_tasks = sorted(task_scores, key=lambda x: x['score'], reverse=True)
        
        # 3. Жадное распределение ресурсов
        allocated_tasks = []
        unallocated_tasks = []
        remaining_budget = resources.budget_million_rub
        remaining_personnel = resources.personnel_hours
        
        for task_score in sorted_tasks:
            task = task_score['task']
            budget_needed = task.resources_needed.get(ResourceType.BUDGET, 0)
            personnel_needed = task.resources_needed.get(ResourceType.PERSONNEL, 0)
            
            # Проверяем зависимости
            deps_met = await self._check_dependencies(task, [t['task'] for t in allocated_tasks])
            
            if (budget_needed <= remaining_budget and 
                personnel_needed <= remaining_personnel and
                deps_met):
                
                allocated_tasks.append({
                    'task_id': task.id,
                    'name': task.name,
                    'budget': budget_needed,
                    'personnel': personnel_needed,
                    'duration_days': task.duration_days,
                    'roi': task.expected_roi,
                    'score': task_score['score']
                })
                
                remaining_budget -= budget_needed
                remaining_personnel -= personnel_needed
            else:
                unallocated_tasks.append({
                    'task_id': task.id,
                    'name': task.name,
                    'budget': budget_needed,
                    'personnel': personnel_needed,
                    'reason': self._get_rejection_reason(task, budget_needed, personnel_needed, 
                                                         remaining_budget, remaining_personnel, deps_met)
                })
        
        # 4. Расчёт utilisation
        utilization = {
            'budget': 1 - (remaining_budget / resources.budget_million_rub) if resources.budget_million_rub > 0 else 0,
            'personnel': 1 - (remaining_personnel / resources.personnel_hours) if resources.personnel_hours > 0 else 0
        }
        
        # 5. Ожидаемое влияние на метрики
        expected_impact = await self._calculate_expected_impact(allocated_tasks)
        
        # 6. Идентификация рисков
        risks = await self._identify_risks(allocated_tasks, resources)
        
        # 7. Рекомендации
        recommendations = await self._generate_recommendations(allocated_tasks, unallocated_tasks, utilization)
        
        plan = AllocationPlan(
            id=f"plan_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.now(),
            horizon_days=resources.time_days,
            total_budget=resources.budget_million_rub,
            allocated_tasks=allocated_tasks,
            unallocated_tasks=unallocated_tasks,
            resource_utilization=utilization,
            expected_impact=expected_impact,
            total_roi=sum(t['roi'] for t in allocated_tasks) / len(allocated_tasks) if allocated_tasks else 0,
            risks=risks,
            recommendations=recommendations
        )
        
        self.allocation_plans.append(plan)
        
        logger.info(f"Создан план распределения: выделено {len(allocated_tasks)} задач, "
                   f"бюджет использован на {utilization['budget']:.0%}")
        
        return plan
    
    async def _score_tasks(self, resources: ResourcePool, weights: Dict[str, float]) -> List[Dict]:
        """
        Оценка задач по нескольким критериям
        """
        scored_tasks = []
        
        for task in self.tasks.values():
            # 1. ROI скор
            roi_score = task.expected_roi
            
            # 2. Стратегическая важность (на основе векторов)
            strategic_score = self._calculate_strategic_importance(task, resources)
            
            # 3. Срочность
            urgency_score = self._calculate_urgency(task, resources)
            
            # 4. Ресурсоэффективность
            efficiency_score = self._calculate_efficiency(task)
            
            # Взвешенная сумма
            total_score = (
                roi_score * weights.get('roi', 0.35) +
                strategic_score * weights.get('strategic_importance', 0.25) +
                urgency_score * weights.get('urgency', 0.20) +
                efficiency_score * weights.get('resource_efficiency', 0.20)
            )
            
            scored_tasks.append({
                'task': task,
                'score': total_score,
                'components': {
                    'roi': roi_score,
                    'strategic': strategic_score,
                    'urgency': urgency_score,
                    'efficiency': efficiency_score
                }
            })
        
        return scored_tasks
    
    def _calculate_strategic_importance(self, task: Task, resources: ResourcePool) -> float:
        """
        Расчёт стратегической важности задачи
        """
        # Приоритет задачи
        priority_scores = {
            Priority.CRITICAL: 1.0,
            Priority.HIGH: 0.8,
            Priority.MEDIUM: 0.5,
            Priority.LOW: 0.3,
            Priority.BACKLOG: 0.1
        }
        priority_score = priority_scores.get(task.priority, 0.5)
        
        # Влияние на векторы (чем больше векторов, тем важнее)
        vector_score = min(1.0, len(task.affected_vectors) / 4)
        
        # Наличие дедлайна
        deadline_score = 0.2 if task.deadline else 0
        
        return priority_score * 0.6 + vector_score * 0.3 + deadline_score
    
    def _calculate_urgency(self, task: Task, resources: ResourcePool) -> float:
        """
        Расчёт срочности задачи
        """
        if not task.deadline:
            return 0.3
        
        days_until_deadline = (task.deadline - datetime.now()).days
        
        if days_until_deadline < 0:
            return 1.0  # Просрочена
        elif days_until_deadline < 7:
            return 0.9
        elif days_until_deadline < 30:
            return 0.7
        elif days_until_deadline < 90:
            return 0.5
        else:
            return 0.3
    
    def _calculate_efficiency(self, task: Task) -> float:
        """
        Расчёт ресурсоэффективности (ROI на единицу ресурса)
        """
        total_cost = task.resources_needed.get(ResourceType.BUDGET, 0)
        total_cost += task.resources_needed.get(ResourceType.PERSONNEL, 0) * self.config.PERSONNEL_COST_PER_HOUR
        
        if total_cost <= 0:
            return 0.5
        
        roi_per_cost = task.expected_roi / total_cost
        return min(1.0, roi_per_cost * 10)  # нормализация
    
    async def _check_dependencies(self, task: Task, allocated_tasks: List[Task]) -> bool:
        """
        Проверка выполнения зависимостей
        """
        if not task.dependencies:
            return True
        
        allocated_ids = [t.id for t in allocated_tasks]
        
        for dep_id in task.dependencies:
            if dep_id not in allocated_ids and dep_id in self.tasks:
                # Зависимость существует, но не выделена
                return False
        
        return True
    
    def _get_rejection_reason(self, task: Task, budget_needed: float, personnel_needed: int,
                               remaining_budget: float, remaining_personnel: int, deps_met: bool) -> str:
        """Причина отклонения задачи"""
        if not deps_met:
            return f"Не выполнены зависимости: {', '.join(task.dependencies)}"
        elif budget_needed > remaining_budget:
            return f"Недостаточно бюджета (нужно {budget_needed} млн ₽, осталось {remaining_budget:.1f} млн ₽)"
        elif personnel_needed > remaining_personnel:
            return f"Недостаточно персонала (нужно {personnel_needed} чел-ч, осталось {remaining_personnel})"
        else:
            return "Неизвестная причина"
    
    async def _calculate_expected_impact(self, allocated_tasks: List[Dict]) -> Dict[str, float]:
        """
        Расчёт ожидаемого влияния на метрики города
        """
        impact = {'СБ': 0, 'ТФ': 0, 'УБ': 0, 'ЧВ': 0}
        
        for task_info in allocated_tasks:
            task = self.tasks.get(task_info['task_id'])
            if not task:
                continue
            
            # Влияние пропорционально ROI и бюджету
            weight = task.expected_roi * (task.resources_needed.get(ResourceType.BUDGET, 0) / 100)
            
            for vector in task.affected_vectors:
                if vector in impact:
                    impact[vector] += weight
        
        # Нормализация
        for vector in impact:
            impact[vector] = min(0.5, impact[vector])
        
        return impact
    
    async def _identify_risks(self, allocated_tasks: List[Dict], resources: ResourcePool) -> List[Dict]:
        """
        Идентификация рисков при распределении
        """
        risks = []
        
        # 1. Перегрузка бюджета
        total_budget = sum(t['budget'] for t in allocated_tasks)
        if total_budget > resources.budget_million_rub * 0.9:
            risks.append({
                'type': 'budget_exhaustion',
                'severity': 'high',
                'description': 'Бюджет почти полностью исчерпан, нет резерва на непредвиденные расходы',
                'mitigation': 'Создать резервный фонд или сократить менее важные задачи'
            })
        
        # 2. Перегрузка персонала
        total_personnel = sum(t['personnel'] for t in allocated_tasks)
        if total_personnel > resources.personnel_hours * 0.9:
            risks.append({
                'type': 'personnel_overload',
                'severity': 'medium',
                'description': 'Высокая загрузка персонала, риск выгорания и срывов сроков',
                'mitigation': 'Привлечь внешних подрядчиков или пересмотреть сроки'
            })
        
        # 3. Зависимости
        tasks_with_deps = [t for t in allocated_tasks 
                          if self.tasks.get(t['task_id']) and self.tasks[t['task_id']].dependencies]
        if len(tasks_with_deps) > len(allocated_tasks) * 0.5:
            risks.append({
                'type': 'dependency_chain',
                'severity': 'medium',
                'description': 'Много задач с зависимостями, риск каскадных задержек',
                'mitigation': 'Усилить контроль критического пути'
            })
        
        # 4. Несбалансированность по департаментам
        dept_budgets = defaultdict(float)
        for task_info in allocated_tasks:
            task = self.tasks.get(task_info['task_id'])
            if task:
                # Определяем департамент по векторам
                dept = self._vector_to_department(task.affected_vectors)
                dept_budgets[dept] += task_info['budget']
        
        for dept, allocated in dept_budgets.items():
            if dept in resources.department_budgets:
                if allocated > resources.department_budgets[dept] * 1.2:
                    risks.append({
                        'type': 'department_imbalance',
                        'severity': 'low',
                        'description': f'Департамент {dept} получил на 20% больше бюджета, чем запланировано',
                        'mitigation': 'Пересмотреть распределение или увеличить бюджет департамента'
                    })
        
        return risks
    
    def _vector_to_department(self, vectors: List[str]) -> str:
        """Маппинг векторов на департаменты"""
        mapping = {
            'СБ': 'Безопасность',
            'ТФ': 'Экономика',
            'УБ': 'Инфраструктура',
            'ЧВ': 'Социальная сфера'
        }
        return mapping.get(vectors[0] if vectors else 'УБ', 'Инфраструктура')
    
    async def _generate_recommendations(self, allocated: List[Dict], unallocated: List[Dict], 
                                         utilization: Dict) -> List[str]:
        """
        Генерация рекомендаций
        """
        recommendations = []
        
        # Рекомендации по бюджету
        if utilization['budget'] < 0.5:
            recommendations.append(f"💡 Использовано только {utilization['budget']:.0%} бюджета. "
                                  f"Можно добавить ещё задач из бэклога.")
        elif utilization['budget'] > 0.95:
            recommendations.append(f"⚠️ Бюджет почти исчерпан ({utilization['budget']:.0%}). "
                                  f"Рекомендуется оставить резерв на непредвиденные расходы.")
        
        # Рекомендации по персоналу
        if utilization['personnel'] > 0.9:
            recommendations.append(f"👥 Высокая загрузка персонала ({utilization['personnel']:.0%}). "
                                  f"Рассмотрите возможность найма или аутсорсинга.")
        
        # Нераспределённые задачи
        if unallocated:
            high_priority_unallocated = [u for u in unallocated 
                                        if self.tasks.get(u['task_id']) and 
                                        self.tasks[u['task_id']].priority in [Priority.CRITICAL, Priority.HIGH]]
            
            if high_priority_unallocated:
                recommendations.append(f"⚠️ {len(high_priority_unallocated)} высокоприоритетных задач не вошли в план. "
                                      f"Требуется пересмотр бюджета или перенос сроков.")
        
        # Лучшая задача по ROI
        if allocated:
            best_roi = max(allocated, key=lambda x: x['roi'])
            recommendations.append(f"🎯 Наилучшая ROI у задачи '{best_roi['name']}' — {best_roi['roi']:.0%}.")
        
        return recommendations
    
    # ==================== 4. СЦЕНАРНОЕ ПЛАНИРОВАНИЕ ====================
    
    async def scenario_planning(self, 
                                  base_resources: ResourcePool,
                                  scenarios: List[Dict[str, Any]]) -> List[AllocationPlan]:
        """
        Сценарное планирование — сравнение разных вариантов распределения
        """
        plans = []
        
        for i, scenario in enumerate(scenarios):
            logger.info(f"Расчёт сценария {i+1}: {scenario.get('name', 'Unnamed')}")
            
            # Создаём копию ресурсов с изменениями
            scenario_resources = ResourcePool(
                timestamp=base_resources.timestamp,
                budget_million_rub=scenario.get('budget', base_resources.budget_million_rub),
                personnel_hours=scenario.get('personnel', base_resources.personnel_hours),
                time_days=scenario.get('time_horizon', base_resources.time_days),
                equipment_units=base_resources.equipment_units,
                admin_capacity=scenario.get('admin_capacity', base_resources.admin_capacity),
                department_budgets=scenario.get('department_budgets', base_resources.department_budgets),
                department_personnel=scenario.get('department_personnel', base_resources.department_personnel)
            )
            
            # Временно устанавливаем ресурсы
            old_resources = self.current_resources
            self.current_resources = scenario_resources
            
            # Оптимизируем
            plan = await self.optimize_allocation(scenario_resources)
            plan.id = f"scenario_{i+1}_{plan.id}"
            plans.append(plan)
            
            # Восстанавливаем
            self.current_resources = old_resources
        
        return plans
    
    # ==================== 5. БЮДЖЕТИРОВАНИЕ ПО ДЕПАРТАМЕНТАМ ====================
    
    async def department_budgeting(self, 
                                     total_budget: float,
                                     strategic_priorities: Dict[str, float]) -> Dict[str, float]:
        """
        Распределение бюджета по департаментам на основе стратегических приоритетов
        """
        if abs(sum(strategic_priorities.values()) - 1.0) > 0.01:
            logger.warning("Сумма весов стратегических приоритетов не равна 1, нормализую")
            total_weight = sum(strategic_priorities.values())
            strategic_priorities = {k: v/total_weight for k, v in strategic_priorities.items()}
        
        department_budgets = {}
        
        for dept in self.config.DEPARTMENTS:
            # Вес департамента (по умолчанию равномерный)
            weight = strategic_priorities.get(dept, 1.0 / len(self.config.DEPARTMENTS))
            department_budgets[dept] = total_budget * weight
        
        return department_budgets
    
    # ==================== 6. АНАЛИЗ ЭФФЕКТИВНОСТИ ====================
    
    async def analyze_efficiency(self, plan: AllocationPlan) -> Dict[str, Any]:
        """
        Анализ эффективности плана распределения
        """
        if not plan.allocated_tasks:
            return {'error': 'Нет выделенных задач'}
        
        # 1. ROI анализ
        rois = [t['roi'] for t in plan.allocated_tasks]
        avg_roi = np.mean(rois)
        max_roi = max(rois)
        min_roi = min(rois)
        
        # 2. Распределение по приоритетам
        priority_distribution = defaultdict(int)
        for task_info in plan.allocated_tasks:
            task = self.tasks.get(task_info['task_id'])
            if task:
                priority_distribution[task.priority.value] += 1
        
        # 3. Эффективность по векторам
        vector_efficiency = defaultdict(float)
        vector_counts = defaultdict(int)
        
        for task_info in plan.allocated_tasks:
            task = self.tasks.get(task_info['task_id'])
            if task:
                for vector in task.affected_vectors:
                    vector_efficiency[vector] += task.expected_roi
                    vector_counts[vector] += 1
        
        for vector in vector_efficiency:
            if vector_counts[vector] > 0:
                vector_efficiency[vector] /= vector_counts[vector]
        
        # 4. Рекомендации по улучшению
        recommendations = []
        
        if avg_roi < 0.3:
            recommendations.append("⚠️ Средняя ROI ниже 30%. Пересмотрите портфель задач.")
        
        if plan.resource_utilization.get('budget', 0) < 0.7:
            recommendations.append("💡 Бюджет использован менее чем на 70%. Добавьте задачи с высоким ROI.")
        
        if len(plan.unallocated_tasks) > len(plan.allocated_tasks) * 0.3:
            recommendations.append("📋 Много нераспределённых задач. Рассмотрите увеличение бюджета.")
        
        return {
            'roi_analysis': {
                'average': avg_roi,
                'maximum': max_roi,
                'minimum': min_roi,
                'total': sum(rois)
            },
            'priority_distribution': dict(priority_distribution),
            'vector_efficiency': dict(vector_efficiency),
            'recommendations': recommendations
        }
    
    # ==================== 7. ДАШБОРД И ОТЧЁТНОСТЬ ====================
    
    async def get_planner_dashboard(self) -> Dict[str, Any]:
        """
        Получение дашборда планировщика
        """
        latest_plan = self.allocation_plans[-1] if self.allocation_plans else None
        
        # Статистика задач
        tasks_by_priority = defaultdict(int)
        for task in self.tasks.values():
            tasks_by_priority[task.priority.value] += 1
        
        # Бюджетная статистика
        total_budget_needed = sum(t.resources_needed.get(ResourceType.BUDGET, 0) for t in self.tasks.values())
        
        return {
            'timestamp': datetime.now().isoformat(),
            'city': self.city_name,
            'statistics': {
                'total_tasks': len(self.tasks),
                'critical_tasks': tasks_by_priority.get('critical', 0),
                'high_tasks': tasks_by_priority.get('high', 0),
                'total_budget_needed': total_budget_needed,
                'plans_created': len(self.allocation_plans)
            },
            'current_resources': {
                'budget_million_rub': self.current_resources.budget_million_rub if self.current_resources else 0,
                'personnel_hours': self.current_resources.personnel_hours if self.current_resources else 0,
                'time_horizon_days': self.current_resources.time_days if self.current_resources else 0
            } if self.current_resources else None,
            'latest_plan': {
                'allocated_tasks': len(latest_plan.allocated_tasks) if latest_plan else 0,
                'unallocated_tasks': len(latest_plan.unallocated_tasks) if latest_plan else 0,
                'budget_utilization': latest_plan.resource_utilization.get('budget', 0) if latest_plan else 0,
                'total_roi': latest_plan.total_roi if latest_plan else 0
            } if latest_plan else None,
            'recommendations': latest_plan.recommendations if latest_plan else [
                "Добавьте задачи для планирования",
                "Установите бюджет и ресурсы"
            ]
        }
    
    async def export_plan_report(self, plan_id: str) -> Dict[str, Any]:
        """
        Экспорт отчёта по плану распределения
        """
        plan = next((p for p in self.allocation_plans if p.id == plan_id), None)
        
        if not plan:
            return {'error': 'Plan not found'}
        
        efficiency = await self.analyze_efficiency(plan)
        
        return {
            'report_id': f"plan_report_{plan_id}",
            'generated_at': datetime.now().isoformat(),
            'city': self.city_name,
            'plan': {
                'id': plan.id,
                'timestamp': plan.timestamp.isoformat(),
                'horizon_days': plan.horizon_days,
                'total_budget': plan.total_budget
            },
            'allocated_tasks': plan.allocated_tasks,
            'unallocated_tasks': plan.unallocated_tasks[:10],  # топ-10
            'resource_utilization': plan.resource_utilization,
            'expected_impact': plan.expected_impact,
            'efficiency_analysis': efficiency,
            'risks': plan.risks,
            'recommendations': plan.recommendations
        }


# ==================== ИНТЕГРАЦИЯ С ОСНОВНЫМ ПРИЛОЖЕНИЕМ ====================

async def create_resource_planner(city_name: str) -> ResourcePlanner:
    """Фабричная функция для создания планировщика ресурсов"""
    return ResourcePlanner(city_name)


# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("🧪 Тестирование ResourcePlanner...")
        
        # Создаём планировщик
        planner = ResourcePlanner("Коломна")
        
        # 1. Добавляем задачи
        print("\n📋 ДОБАВЛЕНИЕ ЗАДАЧ:")
        
        task1 = await planner.add_task(
            name="Установка камер видеонаблюдения",
            description="Установка 50 камер в проблемных районах",
            priority=Priority.HIGH,
            budget_needed=15.0,
            personnel_needed=500,
            duration_days=60,
            expected_roi=0.75,
            affected_vectors=['СБ']
        )
        print(f"  + {task1.name} (бюджет: {task1.resources_needed[ResourceType.BUDGET]} млн ₽)")
        
        task2 = await planner.add_task(
            name="Ремонт дорог в центре",
            description="Капитальный ремонт 5 км дорог",
            priority=Priority.CRITICAL,
            budget_needed=50.0,
            personnel_needed=2000,
            duration_days=120,
            expected_roi=0.6,
            affected_vectors=['УБ', 'ТФ']
        )
        print(f"  + {task2.name} (бюджет: {task2.resources_needed[ResourceType.BUDGET]} млн ₽)")
        
        task3 = await planner.add_task(
            name="Социальная программа для молодёжи",
            description="Гранты и мероприятия",
            priority=Priority.MEDIUM,
            budget_needed=8.0,
            personnel_needed=300,
            duration_days=90,
            expected_roi=0.5,
            affected_vectors=['ЧВ']
        )
        print(f"  + {task3.name} (бюджет: {task3.resources_needed[ResourceType.BUDGET]} млн ₽)")
        
        # 2. Устанавливаем ресурсы
        print("\n💰 УСТАНОВКА РЕСУРСОВ:")
        
        resources = await planner.set_resources(
            budget_million_rub=60.0,
            personnel_hours=2500,
            time_horizon_days=180
        )
        print(f"  Бюджет: {resources.budget_million_rub} млн ₽")
        print(f"  Персонал: {resources.personnel_hours} чел-ч")
        
        # 3. Оптимизация распределения
        print("\n⚡ ОПТИМИЗАЦИЯ РАСПРЕДЕЛЕНИЯ:")
        
        plan = await planner.optimize_allocation()
        
        print(f"  Выделено задач: {len(plan.allocated_tasks)}")
        print(f"  Не выделено: {len(plan.unallocated_tasks)}")
        print(f"  Использование бюджета: {plan.resource_utilization['budget']:.0%}")
        print(f"  Общая ROI: {plan.total_roi:.0%}")
        
        print(f"\n  Выделенные задачи:")
        for task in plan.allocated_tasks:
            print(f"    • {task['name']} — {task['budget']} млн ₽, ROI {task['roi']:.0%}")
        
        if plan.unallocated_tasks:
            print(f"\n  Не выделенные задачи:")
            for task in plan.unallocated_tasks[:3]:
                print(f"    • {task['name']} — причина: {task['reason']}")
        
        # 4. Сценарное планирование
        print("\n🎯 СЦЕНАРНОЕ ПЛАНИРОВАНИЕ:")
        
        scenarios = [
            {'name': 'Оптимистичный', 'budget': 80.0, 'personnel': 3000},
            {'name': 'Базовый', 'budget': 60.0, 'personnel': 2500},
            {'name': 'Пессимистичный', 'budget': 40.0, 'personnel': 2000}
        ]
        
        scenario_plans = await planner.scenario_planning(resources, scenarios)
        
        for i, sp in enumerate(scenario_plans):
            print(f"  Сценарий {scenarios[i]['name']}: {len(sp.allocated_tasks)} задач, "
                  f"ROI {sp.total_roi:.0%}, бюджет {sp.resource_utilization['budget']:.0%}")
        
        # 5. Анализ эффективности
        print("\n📊 АНАЛИЗ ЭФФЕКТИВНОСТИ:")
        
        efficiency = await planner.analyze_efficiency(plan)
        print(f"  Средняя ROI: {efficiency['roi_analysis']['average']:.0%}")
        print(f"  Максимальная ROI: {efficiency['roi_analysis']['maximum']:.0%}")
        
        if efficiency['recommendations']:
            for rec in efficiency['recommendations']:
                print(f"  {rec}")
        
        # 6. Дашборд
        print("\n📋 ДАШБОРД ПЛАНИРОВЩИКА:")
        
        dashboard = await planner.get_planner_dashboard()
        print(f"  Всего задач: {dashboard['statistics']['total_tasks']}")
        print(f"  Критических задач: {dashboard['statistics']['critical_tasks']}")
        print(f"  Требуется бюджета: {dashboard['statistics']['total_budget_needed']:.0f} млн ₽")
        
        print("\n✅ Тест завершен")
    
    asyncio.run(demo())
