#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 20: ФОРСАЙТ И СЦЕНАРНОЕ ПЛАНИРОВАНИЕ (Foresight)
Система долгосрочного прогнозирования развития города на 5-20 лет

Основан на методах:
- Сценарное планирование (Shell метод)
- Анализ мегатрендов и слабых сигналов
- Обратный форсайт (Backcasting)
- Дельфи-метод для экспертных оценок
- Выявление "чёрных лебедей"
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
import json
import hashlib
from math import exp

logger = logging.getLogger(__name__)


# ==================== МОДЕЛИ ДАННЫХ ====================

class ScenarioType(Enum):
    """Типы сценариев"""
    OPTIMISTIC = "optimistic"       # Оптимистичный (прорыв)
    BASELINE = "baseline"           # Базовый (инерционный)
    PESSIMISTIC = "pessimistic"     # Пессимистичный (стагнация)
    SHOCK = "shock"                 # Шоковый (кризисный)
    TRANSFORMATIVE = "transformative"  # Трансформационный


class Megatrend(Enum):
    """Мегатренды, влияющие на города"""
    URBANIZATION = "urbanization"           # Урбанизация
    DIGITALIZATION = "digitalization"       # Цифровизация
    AGING = "aging"                         # Старение населения
    CLIMATE = "climate"                     # Изменение климата
    REMOTE_WORK = "remote_work"             # Удалённая работа
    ECOLOGY = "ecology"                     # Экологическое сознание
    HEALTH = "health"                       # Здравоохранение
    EDUCATION = "education"                 # Образование
    MOBILITY = "mobility"                   # Новая мобильность
    LOCALIZATION = "localization"           # Локализация производства


@dataclass
class MegatrendAnalysis:
    """Анализ мегатренда"""
    trend: Megatrend
    impact_on_city: float          # -1 (негатив) до +1 (позитив)
    probability: float             # 0-1 вероятность реализации
    time_horizon_years: int        # через сколько лет проявится
    local_factors: List[str]       # локальные факторы влияния
    opportunities: List[str]       # возможности
    threats: List[str]             # угрозы


@dataclass
class Scenario:
    """Сценарий развития города"""
    id: str
    name: str
    type: ScenarioType
    description: str
    horizon_years: int
    key_assumptions: List[str]      # ключевые допущения
    population: Dict[int, int]      # год -> население
    economy: Dict[int, float]       # год -> бюджет (млрд ₽)
    metrics: Dict[int, Dict[str, float]]  # год -> {СБ, ТФ, УБ, ЧВ}
    infrastructure: List[str]       # ключевые инфраструктурные проекты
    risks: List[str]                # риски сценария
    triggers: List[str]             # триггеры наступления
    probability: float              # 0-1 вероятность
    created_at: datetime


@dataclass
class BlackSwan:
    """Чёрный лебедь — маловероятное, но разрушительное событие"""
    id: str
    name: str
    description: str
    probability: float              # 0-1 (обычно < 0.05)
    impact: str                     # catastrophic/high/medium
    early_signals: List[str]        # слабые сигналы
    prevention_measures: List[str]  # меры предотвращения
    mitigation_measures: List[str]  # меры смягчения
    examples: List[str]             # аналоги в других городах


@dataclass
class BackcastStep:
    """Шаг обратного форсайта"""
    year: int
    target: str                     # целевой показатель
    required_actions: List[str]
    prerequisites: List[str]
    responsible: List[str]
    budget_estimate: float


# ==================== КОНФИГУРАЦИЯ ====================

class ForesightConfig:
    """Конфигурация системы форсайта"""
    
    # Мегатренды с их влиянием (по умолчанию)
    MEGATRENDS = {
        Megatrend.URBANIZATION: {
            "impact": 0.6,
            "probability": 0.9,
            "horizon": 10,
            "opportunities": ["Рост рынка недвижимости", "Приток инвестиций"],
            "threats": ["Нагрузка на инфраструктуру", "Рост цен на жильё"]
        },
        Megatrend.DIGITALIZATION: {
            "impact": 0.8,
            "probability": 0.95,
            "horizon": 5,
            "opportunities": ["Удалённая работа", "IT-кластер"],
            "threats": ["Цифровое неравенство", "Киберугрозы"]
        },
        Megatrend.AGING: {
            "impact": -0.5,
            "probability": 0.85,
            "horizon": 15,
            "opportunities": ["Развитие медицины", "Социальные услуги"],
            "threats": ["Дефицит кадров", "Нагрузка на бюджет"]
        },
        Megatrend.CLIMATE: {
            "impact": -0.4,
            "probability": 0.9,
            "horizon": 10,
            "opportunities": ["Зелёная энергетика", "Экотуризм"],
            "threats": ["Экстремальные погодные явления", "Затраты на адаптацию"]
        },
        Megatrend.REMOTE_WORK: {
            "impact": 0.5,
            "probability": 0.8,
            "horizon": 5,
            "opportunities": ["Приток мигрантов из мегаполисов", "Коворкинги"],
            "threats": ["Отток из офисов", "Снижение деловой активности в центре"]
        }
    }
    
    # Типовые чёрные лебеди
    BLACK_SWANS = [
        {
            "name": "Техногенная катастрофа",
            "description": "Крупная авария на промышленном объекте",
            "probability": 0.03,
            "impact": "catastrophic",
            "early_signals": ["Нарушения безопасности", "Износ оборудования"]
        },
        {
            "name": "Экономический кризис",
            "description": "Обвал бюджета, закрытие градообразующих предприятий",
            "probability": 0.05,
            "impact": "high",
            "early_signals": ["Падение налогов", "Рост безработицы"]
        },
        {
            "name": "Природный катаклизм",
            "description": "Наводнение, пожар, ураган",
            "probability": 0.04,
            "impact": "high",
            "early_signals": ["Климатические аномалии", "Неготовность инфраструктуры"]
        },
        {
            "name": "Репутационная катастрофа",
            "description": "Крупный скандал с руководством города",
            "probability": 0.06,
            "impact": "high",
            "early_signals": ["Нарастание негатива в соцсетях", "Утечки компромата"]
        }
    ]


# ==================== ОСНОВНОЙ КЛАСС ====================

class ForesightEngine:
    """
    Система форсайта и сценарного планирования
    
    Позволяет:
    - Заглянуть на 5-20 лет вперёд
    - Сравнить разные сценарии развития
    - Подготовиться к чёрным лебедям
    - Спланировать обратный путь от желаемого будущего
    """
    
    def __init__(self, city_name: str, config: ForesightConfig = None):
        self.city_name = city_name
        self.config = config or ForesightConfig()
        
        # Данные города
        self.current_population = 0
        self.current_budget = 0
        self.current_metrics = {'СБ': 3.0, 'ТФ': 3.0, 'УБ': 3.0, 'ЧВ': 3.0}
        
        # Сценарии
        self.scenarios: Dict[str, Scenario] = {}
        self.megatrends: List[MegatrendAnalysis] = []
        self.black_swans: List[BlackSwan] = []
        
        # Экспертные оценки (для Дельфи-метода)
        self.expert_panel: List[Dict] = []
        
        # История
        self.forecast_history = []
        
        logger.info(f"ForesightEngine инициализирован для города {city_name}")
    
    # ==================== 1. АНАЛИЗ МЕГАТРЕНДОВ ====================
    
    async def analyze_megatrends(self, 
                                   custom_factors: Dict[Megatrend, Dict] = None) -> List[MegatrendAnalysis]:
        """
        Анализ мегатрендов и их влияния на город
        """
        logger.info("Анализ мегатрендов...")
        
        analyses = []
        
        for trend, default_data in self.config.MEGATRENDS.items():
            # Учитываем кастомные факторы
            custom = custom_factors.get(trend, {}) if custom_factors else {}
            
            # Локальные факторы (уникальные для города)
            local_factors = await self._get_local_factors(trend)
            
            analysis = MegatrendAnalysis(
                trend=trend,
                impact_on_city=custom.get('impact', default_data['impact']),
                probability=custom.get('probability', default_data['probability']),
                time_horizon_years=custom.get('horizon', default_data['horizon']),
                local_factors=local_factors,
                opportunities=custom.get('opportunities', default_data['opportunities']),
                threats=custom.get('threats', default_data['threats'])
            )
            analyses.append(analysis)
        
        self.megatrends = analyses
        return analyses
    
    async def _get_local_factors(self, trend: Megatrend) -> List[str]:
        """Получение локальных факторов для конкретного города"""
        # В реальной системе — анализ уникальных особенностей города
        # Для демо — общие факторы
        
        local_factors_map = {
            Megatrend.URBANIZATION: [
                f"Близость к {self.city_name} области",
                "Наличие свободных земель",
                "Транспортная доступность"
            ],
            Megatrend.DIGITALIZATION: [
                "Уровень цифровой грамотности населения",
                "Наличие IT-школ",
                "Качество связи и интернета"
            ],
            Megatrend.REMOTE_WORK: [
                "Доля работающих в IT и офисных профессиях",
                "Качество жилья",
                "Скорость интернета"
            ]
        }
        
        return local_factors_map.get(trend, ["Требуется дополнительный анализ"])
    
    # ==================== 2. ПОСТРОЕНИЕ СЦЕНАРИЕВ ====================
    
    async def build_scenarios(self, horizon_years: int = 10) -> List[Scenario]:
        """
        Построение четырёх базовых сценариев развития города
        """
        logger.info(f"Построение сценариев на {horizon_years} лет...")
        
        scenarios = []
        
        # 1. Оптимистичный сценарий
        optimistic = await self._build_optimistic_scenario(horizon_years)
        scenarios.append(optimistic)
        
        # 2. Базовый сценарий
        baseline = await self._build_baseline_scenario(horizon_years)
        scenarios.append(baseline)
        
        # 3. Пессимистичный сценарий
        pessimistic = await self._build_pessimistic_scenario(horizon_years)
        scenarios.append(pessimistic)
        
        # 4. Шоковый сценарий (кризисный)
        shock = await self._build_shock_scenario(horizon_years)
        scenarios.append(shock)
        
        # Сохраняем
        for scenario in scenarios:
            self.scenarios[scenario.id] = scenario
        
        logger.info(f"Построено {len(scenarios)} сценариев")
        return scenarios
    
    async def _build_optimistic_scenario(self, horizon: int) -> Scenario:
        """Оптимистический сценарий — прорывное развитие"""
        
        # Допущения
        assumptions = [
            "Привлечение крупного инвестора (IT-парк)",
            "Развитие транспортной инфраструктуры (МЦД до Коломны)",
            "Рост туристического потока на 300%",
            "Создание 5000 новых рабочих мест",
            "Реализация программы «Цифровой город»"
        ]
        
        # Прогноз населения
        population = {}
        for year in range(0, horizon + 1):
            if year == 0:
                population[year] = self.current_population or 144589
            else:
                # Рост 2% в год
                growth_rate = 1.02
                population[year] = int(population[year-1] * growth_rate)
        
        # Прогноз бюджета
        economy = {}
        for year in range(0, horizon + 1):
            if year == 0:
                economy[year] = self.current_budget or 5.8
            else:
                # Рост 8% в год
                growth_rate = 1.08
                economy[year] = economy[year-1] * growth_rate
        
        # Прогноз метрик
        metrics = {}
        for year in range(0, horizon + 1):
            progress = year / horizon
            metrics[year] = {
                'СБ': min(6.0, 3.5 + progress * 2.5),
                'ТФ': min(6.0, 3.2 + progress * 2.8),
                'УБ': min(6.0, 3.8 + progress * 2.2),
                'ЧВ': min(6.0, 3.0 + progress * 3.0)
            }
        
        # Инфраструктурные проекты
        infrastructure = [
            "IT-парк «Коломенский»",
            "Реконструкция ж/д вокзала",
            "Новая набережная и пешеходные зоны",
            "Строительство 3 школ и 5 детских садов",
            "Реконструкция стадиона"
        ]
        
        # Риски
        risks = [
            "Перегрев экономики",
            "Рост цен на недвижимость",
            "Нехватка кадров"
        ]
        
        return Scenario(
            id=f"scenario_optimistic_{datetime.now().strftime('%Y%m%d')}",
            name="Технологический прорыв",
            type=ScenarioType.OPTIMISTIC,
            description="Коломна становится IT-кластером и туристическим центром Московской области",
            horizon_years=horizon,
            key_assumptions=assumptions,
            population=population,
            economy=economy,
            metrics=metrics,
            infrastructure=infrastructure,
            risks=risks,
            triggers=["Приход крупного инвестора", "Запуск МЦД", "Признание ЮНЕСКО"],
            probability=0.15,
            created_at=datetime.now()
        )
    
    async def _build_baseline_scenario(self, horizon: int) -> Scenario:
        """Базовый сценарий — инерционное развитие"""
        
        assumptions = [
            "Сохранение текущих темпов развития",
            "Реализация плановых проектов",
            "Отсутствие крупных прорывов",
            "Постепенное улучшение качества жизни"
        ]
        
        population = {}
        for year in range(0, horizon + 1):
            if year == 0:
                population[year] = self.current_population or 144589
            else:
                # Стагнация населения
                growth_rate = 1.002
                population[year] = int(population[year-1] * growth_rate)
        
        economy = {}
        for year in range(0, horizon + 1):
            if year == 0:
                economy[year] = self.current_budget or 5.8
            else:
                # Рост 3% в год (инфляция)
                growth_rate = 1.03
                economy[year] = economy[year-1] * growth_rate
        
        metrics = {}
        for year in range(0, horizon + 1):
            progress = year / horizon
            metrics[year] = {
                'СБ': min(6.0, 3.5 + progress * 1.5),
                'ТФ': min(6.0, 3.2 + progress * 1.8),
                'УБ': min(6.0, 3.8 + progress * 1.2),
                'ЧВ': min(6.0, 3.0 + progress * 1.5)
            }
        
        infrastructure = [
            "Плановый ремонт дорог",
            "Благоустройство 10 дворов в год",
            "Ремонт школ по программе"
        ]
        
        risks = [
            "Отставание от соседних городов",
            "Отток молодёжи",
            "Стагнация экономики"
        ]
        
        return Scenario(
            id=f"scenario_baseline_{datetime.now().strftime('%Y%m%d')}",
            name="Инерционное развитие",
            type=ScenarioType.BASELINE,
            description="Сохранение текущих темпов, плановое развитие без прорывов",
            horizon_years=horizon,
            key_assumptions=assumptions,
            population=population,
            economy=economy,
            metrics=metrics,
            infrastructure=infrastructure,
            risks=risks,
            triggers=["Продолжение текущей политики"],
            probability=0.55,
            created_at=datetime.now()
        )
    
    async def _build_pessimistic_scenario(self, horizon: int) -> Scenario:
        """Пессимистический сценарий — стагнация"""
        
        assumptions = [
            "Экономическая рецессия",
            "Сокращение бюджетных доходов",
            "Отток населения",
            "Недофинансирование проектов"
        ]
        
        population = {}
        for year in range(0, horizon + 1):
            if year == 0:
                population[year] = self.current_population or 144589
            else:
                # Убыль 0.5% в год
                growth_rate = 0.995
                population[year] = int(population[year-1] * growth_rate)
        
        economy = {}
        for year in range(0, horizon + 1):
            if year == 0:
                economy[year] = self.current_budget or 5.8
            else:
                # Снижение 1% в год
                growth_rate = 0.99
                economy[year] = economy[year-1] * growth_rate
        
        metrics = {}
        for year in range(0, horizon + 1):
            metrics[year] = {
                'СБ': max(1.5, 3.5 - year * 0.1),
                'ТФ': max(1.5, 3.2 - year * 0.15),
                'УБ': max(1.5, 3.8 - year * 0.08),
                'ЧВ': max(1.5, 3.0 - year * 0.12)
            }
        
        infrastructure = [
            "Только аварийные работы",
            "Сокращение программ благоустройства"
        ]
        
        risks = [
            "Банкротство города",
            "Массовый отток населения",
            "Социальная напряжённость"
        ]
        
        return Scenario(
            id=f"scenario_pessimistic_{datetime.now().strftime('%Y%m%d')}",
            name="Стагнация",
            type=ScenarioType.PESSIMISTIC,
            description="Экономический спад, отток населения, ухудшение качества жизни",
            horizon_years=horizon,
            key_assumptions=assumptions,
            population=population,
            economy=economy,
            metrics=metrics,
            infrastructure=infrastructure,
            risks=risks,
            triggers=["Затяжной экономический кризис", "Потеря крупного инвестора"],
            probability=0.25,
            created_at=datetime.now()
        )
    
    async def _build_shock_scenario(self, horizon: int) -> Scenario:
        """Шоковый сценарий — кризисный"""
        
        assumptions = [
            "Внешний шок (пандемия, техногенная катастрофа)",
            "Экстренные меры, мобилизация ресурсов",
            "Восстановление после кризиса"
        ]
        
        population = {}
        # Кризис на 2-3 году, затем восстановление
        for year in range(0, horizon + 1):
            if year == 0:
                population[year] = self.current_population or 144589
            elif year <= 2:
                # Кризис: резкое падение
                population[year] = int(population[year-1] * 0.95)
            else:
                # Восстановление
                population[year] = int(population[year-1] * 1.02)
        
        economy = {}
        for year in range(0, horizon + 1):
            if year == 0:
                economy[year] = self.current_budget or 5.8
            elif year <= 2:
                economy[year] = economy[year-1] * 0.85
            else:
                economy[year] = economy[year-1] * 1.05
        
        metrics = {}
        for year in range(0, horizon + 1):
            if year <= 2:
                # Падение во время кризиса
                metrics[year] = {
                    'СБ': max(1.0, 3.5 - year * 1.0),
                    'ТФ': max(1.0, 3.2 - year * 1.2),
                    'УБ': max(1.0, 3.8 - year * 0.8),
                    'ЧВ': max(1.0, 3.0 - year * 1.0)
                }
            else:
                # Восстановление
                progress = (year - 2) / (horizon - 2)
                metrics[year] = {
                    'СБ': min(4.5, 1.5 + progress * 3.0),
                    'ТФ': min(4.2, 1.2 + progress * 3.0),
                    'УБ': min(4.8, 2.2 + progress * 2.6),
                    'ЧВ': min(4.0, 1.5 + progress * 2.5)
                }
        
        infrastructure = [
            "Восстановление инфраструктуры после кризиса",
            "Программа антикризисных мер"
        ]
        
        risks = [
            "Затяжной характер кризиса",
            "Невосстановление экономики",
            "Социальные волнения"
        ]
        
        return Scenario(
            id=f"scenario_shock_{datetime.now().strftime('%Y%m%d')}",
            name="Кризис и восстановление",
            type=ScenarioType.SHOCK,
            description="Внешний шок, кризис, затем постепенное восстановление",
            horizon_years=horizon,
            key_assumptions=assumptions,
            population=population,
            economy=economy,
            metrics=metrics,
            infrastructure=infrastructure,
            risks=risks,
            triggers=["Пандемия", "Техногенная катастрофа", "Финансовый кризис"],
            probability=0.05,
            created_at=datetime.now()
        )
    
    # ==================== 3. ЧЁРНЫЕ ЛЕБЕДИ ====================
    
    async def identify_black_swans(self) -> List[BlackSwan]:
        """
        Выявление потенциальных чёрных лебедей
        """
        logger.info("Выявление чёрных лебедей...")
        
        black_swans = []
        
        for data in self.config.BLACK_SWANS:
            # Адаптация под конкретный город
            local_signals = await self._get_local_early_signals(data['name'])
            
            black_swan = BlackSwan(
                id=f"bs_{data['name'].lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}",
                name=data['name'],
                description=data['description'],
                probability=data['probability'],
                impact=data['impact'],
                early_signals=data['early_signals'] + local_signals,
                prevention_measures=await self._get_prevention_measures(data['name']),
                mitigation_measures=await self._get_mitigation_measures(data['name']),
                examples=await self._get_examples(data['name'])
            )
            black_swans.append(black_swan)
        
        self.black_swans = black_swans
        return black_swans
    
    async def _get_local_early_signals(self, black_swan_name: str) -> List[str]:
        """Локальные ранние сигналы для города"""
        signals_map = {
            "Техногенная катастрофа": [
                "Последняя проверка Ростехнадзора выявила нарушения",
                "Износ оборудования на заводе превышает 70%"
            ],
            "Экономический кризис": [
                "Снижение поступлений от НДФЛ",
                "Рост числа банкротств МСП"
            ],
            "Природный катаклизм": [
                "Аномальные осадки",
                "Неочищенные ливневки"
            ]
        }
        return signals_map.get(black_swan_name, ["Требуется мониторинг"])
    
    async def _get_prevention_measures(self, black_swan_name: str) -> List[str]:
        """Меры предотвращения"""
        measures_map = {
            "Техногенная катастрофа": [
                "Внеплановые проверки промышленных объектов",
                "Инвестиции в модернизацию оборудования"
            ],
            "Экономический кризис": [
                "Создание резервного фонда (5% бюджета)",
                "Диверсификация экономики"
            ],
            "Природный катаклизм": [
                "Модернизация ливневой канализации",
                "Создание резервных источников энергии"
            ]
        }
        return measures_map.get(black_swan_name, ["Разработка плана действий"])
    
    async def _get_mitigation_measures(self, black_swan_name: str) -> List[str]:
        """Меры смягчения последствий"""
        measures_map = {
            "Техногенная катастрофа": [
                "План эвакуации населения",
                "Запасы средств индивидуальной защиты"
            ],
            "Экономический кризис": [
                "Программа поддержки занятости",
                "Социальные выплаты"
            ]
        }
        return measures_map.get(black_swan_name, ["План ликвидации последствий"])
    
    async def _get_examples(self, black_swan_name: str) -> List[str]:
        """Примеры из других городов"""
        examples_map = {
            "Техногенная катастрофа": [
                "Взрыв на заводе в Дзержинске (2019)",
                "Пожар на складе в Электростали (2021)"
            ],
            "Экономический кризис": [
                "Моногород Пикалёво (2009)",
                "Кризис в Набережных Челнах (2015)"
            ]
        }
        return examples_map.get(black_swan_name, ["Изучить опыт других городов"])
    
    # ==================== 4. ОБРАТНЫЙ ФОРСАЙТ ====================
    
    async def backcast(self, 
                        target_year: int,
                        target_metrics: Dict[str, float],
                        current_year: int = None) -> List[BackcastStep]:
        """
        Обратный форсайт — от желаемого будущего к плану действий
        """
        logger.info(f"Обратный форсайт: достичь {target_metrics} к {target_year}")
        
        if current_year is None:
            current_year = datetime.now().year
        
        steps = []
        years_step = (target_year - current_year) // 4  # 4 промежуточных этапа
        
        # Определяем промежуточные цели
        for i in range(1, 5):
            intermediate_year = current_year + years_step * i
            progress = i / 4
            
            intermediate_metrics = {}
            for vector, target in target_metrics.items():
                current = self.current_metrics.get(vector, 3.0)
                intermediate_metrics[vector] = current + (target - current) * progress
            
            # Действия для достижения
            actions = await self._generate_actions_for_metrics(intermediate_metrics)
            
            step = BackcastStep(
                year=intermediate_year,
                target=f"Достичь {intermediate_metrics}",
                required_actions=actions,
                prerequisites=["Бюджет", "Кадры", "Политическая воля"],
                responsible=["Глава города", "Профильные департаменты"],
                budget_estimate=(target_year - current_year) * 50  # млн ₽
            )
            steps.append(step)
        
        return steps
    
    async def _generate_actions_for_metrics(self, target_metrics: Dict[str, float]) -> List[str]:
        """Генерация действий для достижения целевых метрик"""
        actions = []
        
        if target_metrics.get('СБ', 0) > 4.5:
            actions.append("Усиление патрулирования и установка камер")
        
        if target_metrics.get('ТФ', 0) > 4.5:
            actions.append("Привлечение инвесторов, создание ТОР")
        
        if target_metrics.get('УБ', 0) > 4.5:
            actions.append("Программа благоустройства «Комфортная среда»")
        
        if target_metrics.get('ЧВ', 0) > 4.5:
            actions.append("Развитие инициативного бюджетирования и ТОС")
        
        if not actions:
            actions = ["Разработка комплексного плана развития"]
        
        return actions
    
    # ==================== 5. ДЕЛЬФИ-МЕТОД ====================
    
    async def run_delphi(self, 
                          question: str,
                          experts: List[Dict],
                          rounds: int = 3) -> Dict[str, Any]:
        """
        Дельфи-метод для экспертных оценок
        """
        logger.info(f"Запуск Дельфи-метода: {question}")
        
        # Сохраняем экспертов
        self.expert_panel = experts
        
        results = {
            'question': question,
            'rounds': [],
            'consensus': None,
            'confidence': 0
        }
        
        current_estimates = [e.get('initial_estimate', 0.5) for e in experts]
        
        for round_num in range(1, rounds + 1):
            # Статистика раунда
            median = np.median(current_estimates)
            lower_quartile = np.percentile(current_estimates, 25)
            upper_quartile = np.percentile(current_estimates, 75)
            
            round_result = {
                'round': round_num,
                'median': median,
                'lower_quartile': lower_quartile,
                'upper_quartile': upper_quartile,
                'responses': len(current_estimates),
                'convergence': 1 - (upper_quartile - lower_quartile)
            }
            results['rounds'].append(round_result)
            
            # Обновляем оценки экспертов (в реальности — обратная связь)
            if round_num < rounds:
                current_estimates = await self._update_expert_estimates(
                    current_estimates, median, lower_quartile, upper_quartile
                )
        
        results['consensus'] = results['rounds'][-1]['median']
        results['confidence'] = results['rounds'][-1]['convergence']
        
        return results
    
    async def _update_expert_estimates(self, 
                                         estimates: List[float],
                                         median: float,
                                         lower: float,
                                         upper: float) -> List[float]:
        """Обновление оценок экспертов (симуляция)"""
        # В реальной системе — сбор новых оценок от экспертов
        # Здесь — небольшое приближение к медиане
        new_estimates = []
        for e in estimates:
            if e < lower:
                new_estimates.append(e + (median - e) * 0.3)
            elif e > upper:
                new_estimates.append(e - (e - median) * 0.3)
            else:
                new_estimates.append(e)
        return new_estimates
    
    # ==================== 6. СРАВНЕНИЕ СЦЕНАРИЕВ ====================
    
    async def compare_scenarios(self) -> Dict[str, Any]:
        """
        Сравнение всех сценариев
        """
        comparison = {
            'horizon_years': 10,
            'scenarios': []
        }
        
        for scenario in self.scenarios.values():
            # Итоговые показатели
            final_population = scenario.population.get(scenario.horizon_years, 0)
            final_budget = scenario.economy.get(scenario.horizon_years, 0)
            final_metrics = scenario.metrics.get(scenario.horizon_years, {})
            
            # Изменение относительно текущего
            current_pop = self.current_population or 144589
            pop_change = (final_population - current_pop) / current_pop * 100
            
            comparison['scenarios'].append({
                'name': scenario.name,
                'type': scenario.type.value,
                'probability': scenario.probability,
                'final_population': final_population,
                'population_change': round(pop_change, 1),
                'final_budget': round(final_budget, 1),
                'final_metrics': final_metrics,
                'key_risks': scenario.risks[:3],
                'key_infrastructure': scenario.infrastructure[:2]
            })
        
        # Рекомендация
        best_scenario = max(self.scenarios.values(), key=lambda x: x.probability * x.type == ScenarioType.OPTIMISTIC)
        
        comparison['recommendation'] = {
            'most_likely': next((s for s in comparison['scenarios'] if s['type'] == 'baseline'), None),
            'most_ambitious': next((s for s in comparison['scenarios'] if s['type'] == 'optimistic'), None),
            'strategy': "Стремиться к оптимистичному сценарию, готовясь к шоковому"
        }
        
        return comparison
    
    # ==================== 7. ДАШБОРД ====================
    
    async def get_foresight_dashboard(self) -> Dict[str, Any]:
        """
        Дашборд форсайта для мэра
        """
        # Актуальные сценарии
        active_scenarios = list(self.scenarios.values())
        
        # Мегатренды с наибольшим влиянием
        top_trends = sorted(self.megatrends, key=lambda x: abs(x.impact_on_city), reverse=True)[:3]
        
        # Чёрные лебеди с наивысшим риском
        high_risk_swans = [bs for bs in self.black_swans if bs.impact == 'catastrophic' or bs.impact == 'high']
        
        return {
            'timestamp': datetime.now().isoformat(),
            'city': self.city_name,
            'scenarios': [
                {
                    'name': s.name,
                    'type': s.type.value,
                    'probability': f"{s.probability:.0%}",
                    'final_population': s.population.get(s.horizon_years, 0),
                    'final_budget': round(s.economy.get(s.horizon_years, 0), 1)
                }
                for s in active_scenarios
            ],
            'megatrends': [
                {
                    'trend': t.trend.value,
                    'impact': f"{t.impact_on_city:+.1f}",
                    'probability': f"{t.probability:.0%}",
                    'horizon': t.time_horizon_years
                }
                for t in top_trends
            ],
            'black_swans': [
                {
                    'name': bs.name,
                    'probability': f"{bs.probability:.0%}",
                    'impact': bs.impact,
                    'early_signals': bs.early_signals[:2]
                }
                for bs in high_risk_swans
            ],
            'recommendations': [
                "🎯 Фокус на развитии IT-кластера для достижения оптимистичного сценария",
                "⚠️ Создать резервный фонд на случай экономического кризиса",
                "📊 Внедрить систему раннего обнаружения слабых сигналов",
                "🤝 Провести стратегическую сессию с экспертами раз в полугодие"
            ]
        }


# ==================== ИНТЕГРАЦИЯ ====================

async def create_foresight_engine(city_name: str) -> ForesightEngine:
    """Фабричная функция"""
    return ForesightEngine(city_name)


# ==================== ПРИМЕР ====================

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("🧪 Тестирование ForesightEngine...")
        
        engine = ForesightEngine("Коломна")
        
        # 1. Анализ мегатрендов
        print("\n📊 АНАЛИЗ МЕГАТРЕНДОВ:")
        trends = await engine.analyze_megatrends()
        for t in trends[:3]:
            print(f"  • {t.trend.value}: влияние {t.impact_on_city:+.1f}, горизонт {t.time_horizon_years} лет")
        
        # 2. Построение сценариев
        print("\n🎯 СЦЕНАРИИ РАЗВИТИЯ:")
        scenarios = await engine.build_scenarios(horizon_years=10)
        for s in scenarios:
            final_pop = s.population.get(10, 0)
            print(f"  • {s.name} ({s.type.value}): население {final_pop:,} чел., бюджет {s.economy.get(10, 0):.1f} млрд ₽")
        
        # 3. Чёрные лебеди
        print("\n🦢 ЧЁРНЫЕ ЛЕБЕДИ:")
        swans = await engine.identify_black_swans()
        for sw in swans[:2]:
            print(f"  • {sw.name}: вероятность {sw.probability:.0%}, влияние {sw.impact}")
            print(f"    Ранние сигналы: {', '.join(sw.early_signals[:2])}")
        
        # 4. Сравнение сценариев
        print("\n📊 СРАВНЕНИЕ СЦЕНАРИЕВ:")
        comparison = await engine.compare_scenarios()
        for s in comparison['scenarios']:
            print(f"  • {s['name']}: вероятность {s['probability']:.0%}, рост населения {s['population_change']:+.1f}%")
        
        # 5. Дашборд
        print("\n📋 ДАШБОРД ФОРСАЙТА:")
        dashboard = await engine.get_foresight_dashboard()
        print(f"  Сценариев: {len(dashboard['scenarios'])}")
        print(f"  Рекомендации: {dashboard['recommendations'][0]}")
        
        print("\n✅ Тест завершен")
    
    asyncio.run(demo())
