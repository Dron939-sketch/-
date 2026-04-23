#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 26: АНАЛИЗАТОР РЫНОЧНЫХ НИШ (Market Gap Analyzer)
Система выявления дефицита и профицита бизнеса в городе

Позволяет:
- Определить, каких услуг/товаров не хватает в городе
- Выявить перенасыщенные сегменты рынка
- Рекомендовать предпринимателям свободные ниши
- Планировать развитие инфраструктуры под бизнес
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

logger = logging.getLogger(__name__)


# ==================== МОДЕЛИ ДАННЫХ ====================

class BusinessCategory(Enum):
    """Категории бизнеса"""
    # Ежедневный спрос
    GROCERY = "grocery"                 # Продуктовые магазины
    PHARMACY = "pharmacy"               # Аптеки
    CAFE = "cafe"                       # Кафе и столовые
    FAST_FOOD = "fast_food"             # Фастфуд
    BAKERY = "bakery"                   # Пекарни
    
    # Бытовые услуги
    BEAUTY = "beauty"                   # Парикмахерские, салоны красоты
    LAUNDRY = "laundry"                 # Химчистки, прачечные
    REPAIR = "repair"                   # Ремонт техники, обуви
    CAR_WASH = "car_wash"               # Автомойки
    CAR_SERVICE = "car_service"         # Автосервисы
    TIRE_FITTING = "tire_fitting"       # Шиномонтаж
    
    # Образование и развитие
    KINDERGARTEN = "kindergarten"       # Детские сады
    SCHOOL = "school"                   # Школы
    TUTORING = "tutoring"               # Репетиторы, курсы
    SPORTS = "sports"                   # Спортивные секции
    DANCE = "dance"                     # Танцевальные студии
    LANGUAGE = "language"               # Языковые школы
    
    # Медицина и здоровье
    DENTIST = "dentist"                 # Стоматологии
    LAB = "lab"                         # Медлаборатории
    VET = "vet"                         # Ветеринарные клиники
    FITNESS = "fitness"                 # Фитнес-центры
    
    # Развлечения и досуг
    CINEMA = "cinema"                   # Кинотеатры
    BOWLING = "bowling"                 # Боулинг
    KARAOKE = "karaoke"                 # Караоке
    HOOKAH = "hookah"                   # Кальянные
    ANTI_CAFE = "anti_cafe"             # Антикафе
    
    # Специфические городские
    COWORKING = "coworking"             # Коворкинги
    PRINTING = "printing"               # Копицентры, типографии
    KEYS = "keys"                       # Мастерские по ключам
    CLOTHING_REPAIR = "clothing_repair" # Ателье
    FURNITURE = "furniture"             # Мебельные магазины
    FLOWERS = "flowers"                 # Цветочные магазины
    PET = "pet"                         # Зоомагазины


@dataclass
class BusinessNorm:
    """Норматив бизнеса на 10 000 жителей"""
    category: BusinessCategory
    name_ru: str
    norm_min: float      # минимальное количество на 10к жителей
    norm_optimal: float  # оптимальное количество
    norm_max: float      # максимальное количество
    source: str          # источник данных (Росстат, экспертиза)
    seasonality_factor: float = 1.0  # сезонный коэффициент


@dataclass
class DistrictBusiness:
    """Бизнес в районе"""
    district_name: str
    population: int
    businesses: Dict[BusinessCategory, int]
    gaps: Dict[BusinessCategory, Dict]  # дефицит/профицит
    overall_score: float                # общая оценка сбалансированности


@dataclass
class MarketGap:
    """Рыночная ниша (дефицит или профицит)"""
    category: BusinessCategory
    category_name: str
    district: str
    current_count: int
    optimal_count: int
    gap: int                          # положительный = профицит, отрицательный = дефицит
    gap_percent: float                # процент отклонения от нормы
    type: str                         # "deficit" или "surplus"
    priority: str                     # "critical", "high", "medium", "low"
    recommendation: str
    estimated_demand: int


# ==================== НОРМАТИВЫ БИЗНЕСА ====================

class MarketGapConfig:
    """Конфигурация с нормативами бизнеса на 10 000 жителей"""
    
    # Нормативы основаны на данных Росстата, экспертных оценках и анализе городов-аналогов
    BUSINESS_NORMS = {
        # Ежедневный спрос
        BusinessCategory.GROCERY: {
            "name_ru": "Продуктовые магазины",
            "norm_min": 15,
            "norm_optimal": 25,
            "norm_max": 40,
            "source": "Росстат, среднее по МО"
        },
        BusinessCategory.PHARMACY: {
            "name_ru": "Аптеки",
            "norm_min": 3,
            "norm_optimal": 6,
            "norm_max": 10,
            "source": "Росстат"
        },
        BusinessCategory.CAFE: {
            "name_ru": "Кафе и столовые",
            "norm_min": 8,
            "norm_optimal": 15,
            "norm_max": 25,
            "source": "Экспертная оценка"
        },
        BusinessCategory.FAST_FOOD: {
            "name_ru": "Фастфуд",
            "norm_min": 3,
            "norm_optimal": 7,
            "norm_max": 12,
            "source": "Экспертная оценка"
        },
        BusinessCategory.BAKERY: {
            "name_ru": "Пекарни",
            "norm_min": 2,
            "norm_optimal": 4,
            "norm_max": 8,
            "source": "Экспертная оценка"
        },
        
        # Бытовые услуги
        BusinessCategory.BEAUTY: {
            "name_ru": "Парикмахерские",
            "norm_min": 5,
            "norm_optimal": 10,
            "norm_max": 18,
            "source": "2ГИС, анализ городов"
        },
        BusinessCategory.LAUNDRY: {
            "name_ru": "Химчистки и прачечные",
            "norm_min": 1,
            "norm_optimal": 2,
            "norm_max": 4,
            "source": "Экспертная оценка"
        },
        BusinessCategory.REPAIR: {
            "name_ru": "Мастерские по ремонту",
            "norm_min": 2,
            "norm_optimal": 4,
            "norm_max": 7,
            "source": "Экспертная оценка"
        },
        BusinessCategory.CAR_WASH: {
            "name_ru": "Автомойки",
            "norm_min": 2,
            "norm_optimal": 4,
            "norm_max": 7,
            "source": "Экспертная оценка (с учётом числа авто)"
        },
        BusinessCategory.CAR_SERVICE: {
            "name_ru": "Автосервисы",
            "norm_min": 3,
            "norm_optimal": 5,
            "norm_max": 9,
            "source": "Экспертная оценка"
        },
        BusinessCategory.TIRE_FITTING: {
            "name_ru": "Шиномонтаж",
            "norm_min": 1,
            "norm_optimal": 2,
            "norm_max": 4,
            "source": "Экспертная оценка",
            "seasonality_factor": 1.5  # зимой/летом выше спрос
        },
        
        # Образование
        BusinessCategory.TUTORING: {
            "name_ru": "Репетиторы и курсы",
            "norm_min": 3,
            "norm_optimal": 6,
            "norm_max": 12,
            "source": "Экспертная оценка"
        },
        BusinessCategory.SPORTS: {
            "name_ru": "Спортивные секции",
            "norm_min": 2,
            "norm_optimal": 5,
            "norm_max": 10,
            "source": "Экспертная оценка"
        },
        BusinessCategory.DANCE: {
            "name_ru": "Танцевальные студии",
            "norm_min": 1,
            "norm_optimal": 3,
            "norm_max": 6,
            "source": "Экспертная оценка"
        },
        BusinessCategory.LANGUAGE: {
            "name_ru": "Языковые школы",
            "norm_min": 1,
            "norm_optimal": 3,
            "norm_max": 6,
            "source": "Экспертная оценка"
        },
        
        # Медицина
        BusinessCategory.DENTIST: {
            "name_ru": "Стоматологии",
            "norm_min": 2,
            "norm_optimal": 4,
            "norm_max": 8,
            "source": "Росстат"
        },
        BusinessCategory.LAB: {
            "name_ru": "Медлаборатории",
            "norm_min": 1,
            "norm_optimal": 2,
            "norm_max": 3,
            "source": "Экспертная оценка"
        },
        BusinessCategory.VET: {
            "name_ru": "Ветеринарные клиники",
            "norm_min": 1,
            "norm_optimal": 2,
            "norm_max": 4,
            "source": "Экспертная оценка"
        },
        BusinessCategory.FITNESS: {
            "name_ru": "Фитнес-центры",
            "norm_min": 1,
            "norm_optimal": 2,
            "norm_max": 4,
            "source": "Экспертная оценка"
        },
        
        # Развлечения
        BusinessCategory.CINEMA: {
            "name_ru": "Кинотеатры",
            "norm_min": 0.5,
            "norm_optimal": 1,
            "norm_max": 2,
            "source": "Экспертная оценка"
        },
        BusinessCategory.BOWLING: {
            "name_ru": "Боулинг",
            "norm_min": 0.3,
            "norm_optimal": 0.5,
            "norm_max": 1,
            "source": "Экспертная оценка"
        },
        BusinessCategory.ANTI_CAFE: {
            "name_ru": "Антикафе",
            "norm_min": 0.3,
            "norm_optimal": 0.5,
            "norm_max": 1,
            "source": "Экспертная оценка"
        },
        
        # Специфические
        BusinessCategory.COWORKING: {
            "name_ru": "Коворкинги",
            "norm_min": 0.3,
            "norm_optimal": 0.5,
            "norm_max": 1,
            "source": "Экспертная оценка"
        },
        BusinessCategory.PRINTING: {
            "name_ru": "Копицентры",
            "norm_min": 1,
            "norm_optimal": 2,
            "norm_max": 4,
            "source": "Экспертная оценка"
        },
        BusinessCategory.KEYS: {
            "name_ru": "Мастерские по ключам",
            "norm_min": 1,
            "norm_optimal": 1.5,
            "norm_max": 3,
            "source": "Экспертная оценка"
        },
        BusinessCategory.CLOTHING_REPAIR: {
            "name_ru": "Ателье",
            "norm_min": 1,
            "norm_optimal": 2,
            "norm_max": 4,
            "source": "Экспертная оценка"
        },
        BusinessCategory.FLOWERS: {
            "name_ru": "Цветочные магазины",
            "norm_min": 1,
            "norm_optimal": 2,
            "norm_max": 4,
            "source": "Экспертная оценка"
        },
        BusinessCategory.PET: {
            "name_ru": "Зоомагазины",
            "norm_min": 1,
            "norm_optimal": 2,
            "norm_max": 4,
            "source": "Экспертная оценка"
        }
    }
    
    # Районы города (для Коломны)
    DISTRICTS = [
        {"name": "Центральный", "population": 35000, "coefficient": 1.2},
        {"name": "Колычёво", "population": 28000, "coefficient": 1.0},
        {"name": "Голутвин", "population": 22000, "coefficient": 0.9},
        {"name": "Щурово", "population": 18000, "coefficient": 0.8},
        {"name": "Запрудня", "population": 15000, "coefficient": 0.7},
        {"name": "Малаховка", "population": 12000, "coefficient": 0.6},
        {"name": "Пески", "population": 8000, "coefficient": 0.5},
        {"name": "Станкостроитель", "population": 6000, "coefficient": 0.4}
    ]


# ==================== ОСНОВНОЙ КЛАСС ====================

class MarketGapAnalyzer:
    """
    Анализатор рыночных ниш — выявление дефицита и профицита бизнеса
    
    Позволяет:
    - Увидеть, каких услуг не хватает в городе
    - Выявить перенасыщенные сегменты
    - Получить рекомендации для инвесторов
    - Планировать развитие районов
    """
    
    def __init__(self, city_name: str, population: int):
        self.city_name = city_name
        self.total_population = population
        self.config = MarketGapConfig()
        
        # Данные о бизнесе (в реальности — из 2ГИС, Яндекс.Карт, ФНС)
        self.business_data: Dict[str, Dict[BusinessCategory, int]] = {}
        self.district_analysis: List[DistrictBusiness] = []
        
        # Кэш
        self.market_gaps: List[MarketGap] = []
        
        # Инициализация данных по районам
        self._init_district_data()
        
        logger.info(f"MarketGapAnalyzer инициализирован для города {city_name} (население {population:,} чел.)")
    
    def _init_district_data(self):
        """Инициализация данных по районам"""
        for district in self.config.DISTRICTS:
            self.business_data[district["name"]] = defaultdict(int)
    
    # ==================== 1. СБОР ДАННЫХ О БИЗНЕСЕ ====================
    
    async def load_business_data(self, data_source: List[Dict] = None):
        """
        Загрузка данных о бизнесе (из 2ГИС, Яндекс.Карт, ФНС)
        
        В реальной системе здесь интеграция с API 2ГИС или парсинг карт
        """
        if data_source:
            for item in data_source:
                district = item.get("district")
                category = item.get("category")
                count = item.get("count", 1)
                
                if district in self.business_data:
                    self.business_data[district][category] += count
        else:
            # Демо-данные для Коломны
            await self._load_demo_data()
    
    async def _load_demo_data(self):
        """Загрузка демо-данных для тестирования"""
        
        # Данные по районам (приблизительные)
        demo_data = {
            "Центральный": {
                BusinessCategory.GROCERY: 42,
                BusinessCategory.PHARMACY: 15,
                BusinessCategory.CAFE: 28,
                BusinessCategory.FAST_FOOD: 18,
                BusinessCategory.BEAUTY: 35,
                BusinessCategory.LAUNDRY: 3,
                BusinessCategory.REPAIR: 8,
                BusinessCategory.CAR_WASH: 5,
                BusinessCategory.CAR_SERVICE: 7,
                BusinessCategory.TUTORING: 12,
                BusinessCategory.SPORTS: 8,
                BusinessCategory.DENTIST: 9,
                BusinessCategory.FITNESS: 4,
                BusinessCategory.CINEMA: 2,
                BusinessCategory.COWORKING: 2,
                BusinessCategory.PRINTING: 6,
                BusinessCategory.KEYS: 4,
                BusinessCategory.CLOTHING_REPAIR: 5,
                BusinessCategory.FLOWERS: 8,
                BusinessCategory.PET: 4
            },
            "Колычёво": {
                BusinessCategory.GROCERY: 18,
                BusinessCategory.PHARMACY: 5,
                BusinessCategory.CAFE: 6,
                BusinessCategory.FAST_FOOD: 4,
                BusinessCategory.BEAUTY: 8,
                BusinessCategory.LAUNDRY: 0,
                BusinessCategory.REPAIR: 3,
                BusinessCategory.CAR_WASH: 8,
                BusinessCategory.CAR_SERVICE: 6,
                BusinessCategory.TUTORING: 2,
                BusinessCategory.SPORTS: 1,
                BusinessCategory.DENTIST: 2,
                BusinessCategory.FITNESS: 0,
                BusinessCategory.PRINTING: 1,
                BusinessCategory.KEYS: 1,
                BusinessCategory.CLOTHING_REPAIR: 1,
                BusinessCategory.FLOWERS: 1,
                BusinessCategory.PET: 2
            },
            "Голутвин": {
                BusinessCategory.GROCERY: 12,
                BusinessCategory.PHARMACY: 4,
                BusinessCategory.CAFE: 4,
                BusinessCategory.FAST_FOOD: 2,
                BusinessCategory.BEAUTY: 5,
                BusinessCategory.REPAIR: 2,
                BusinessCategory.CAR_WASH: 3,
                BusinessCategory.CAR_SERVICE: 3,
                BusinessCategory.TUTORING: 1,
                BusinessCategory.DENTIST: 1,
                BusinessCategory.PRINTING: 1,
                BusinessCategory.KEYS: 1
            },
            "Щурово": {
                BusinessCategory.GROCERY: 8,
                BusinessCategory.PHARMACY: 2,
                BusinessCategory.CAFE: 2,
                BusinessCategory.BEAUTY: 3,
                BusinessCategory.CAR_WASH: 4,
                BusinessCategory.CAR_SERVICE: 3,
                BusinessCategory.TIRE_FITTING: 2
            },
            "Запрудня": {
                BusinessCategory.GROCERY: 6,
                BusinessCategory.PHARMACY: 1,
                BusinessCategory.BEAUTY: 2,
                BusinessCategory.CAR_WASH: 2,
                BusinessCategory.CAR_SERVICE: 2
            },
            "Малаховка": {
                BusinessCategory.GROCERY: 5,
                BusinessCategory.PHARMACY: 1,
                BusinessCategory.BEAUTY: 1
            },
            "Пески": {
                BusinessCategory.GROCERY: 3,
                BusinessCategory.PHARMACY: 1
            },
            "Станкостроитель": {
                BusinessCategory.GROCERY: 2
            }
        }
        
        for district, categories in demo_data.items():
            for category, count in categories.items():
                self.business_data[district][category] += count
    
    # ==================== 2. РАСЧЁТ ДЕФИЦИТА/ПРОФИЦИТА ====================
    
    async def analyze_all_districts(self) -> List[DistrictBusiness]:
        """
        Анализ всех районов города
        """
        logger.info("Анализ рыночных ниш по районам...")
        
        self.district_analysis = []
        all_gaps = []
        
        for district_info in self.config.DISTRICTS:
            district_name = district_info["name"]
            population = district_info["population"]
            coefficient = district_info["coefficient"]
            
            businesses = self.business_data.get(district_name, {})
            gaps = {}
            
            # Анализ каждой категории
            for category, norm_data in self.config.BUSINESS_NORMS.items():
                current = businesses.get(category, 0)
                
                # Норма для данного района (с учётом коэффициента)
                norm_per_10k = norm_data["norm_optimal"]
                expected = (population / 10000) * norm_per_10k * coefficient
                expected = max(0.5, expected)
                
                gap = current - expected
                gap_percent = (gap / expected) * 100 if expected > 0 else 100
                
                # Определяем тип
                if gap < -1:
                    gap_type = "deficit"
                    priority = self._get_priority(abs(gap_percent), is_deficit=True)
                    recommendation = self._get_recommendation(category, gap_type, abs(gap))
                elif gap > 1:
                    gap_type = "surplus"
                    priority = self._get_priority(gap_percent, is_deficit=False)
                    recommendation = self._get_recommendation(category, gap_type, gap)
                else:
                    gap_type = "normal"
                    priority = "low"
                    recommendation = "Рынок сбалансирован"
                
                gaps[category] = {
                    "current": round(current, 1),
                    "expected": round(expected, 1),
                    "gap": round(gap, 1),
                    "gap_percent": round(gap_percent, 1),
                    "type": gap_type,
                    "priority": priority,
                    "recommendation": recommendation
                }
                
                # Сохраняем значимые gaps
                if gap_type != "normal" and abs(gap_percent) > 30:
                    all_gaps.append(MarketGap(
                        category=category,
                        category_name=norm_data["name_ru"],
                        district=district_name,
                        current_count=round(current, 1),
                        optimal_count=round(expected, 1),
                        gap=round(gap, 1),
                        gap_percent=round(gap_percent, 1),
                        type=gap_type,
                        priority=priority,
                        recommendation=recommendation,
                        estimated_demand=round(abs(gap), 1) if gap_type == "deficit" else 0
                    ))
            
            # Оценка сбалансированности района
            total_deficit = sum(1 for g in gaps.values() if g["type"] == "deficit")
            total_surplus = sum(1 for g in gaps.values() if g["type"] == "surplus")
            overall_score = 1 - (total_deficit + total_surplus) / len(gaps) if gaps else 1
            
            district_business = DistrictBusiness(
                district_name=district_name,
                population=population,
                businesses={k: v for k, v in businesses.items()},
                gaps=gaps,
                overall_score=overall_score
            )
            self.district_analysis.append(district_business)
        
        # Сортируем gaps по приоритету
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        all_gaps.sort(key=lambda x: (priority_order.get(x.priority, 4), -abs(x.gap_percent)))
        
        self.market_gaps = all_gaps
        
        logger.info(f"Анализ завершён. Выявлено {len([g for g in all_gaps if g.type == 'deficit'])} дефицитных ниш, {len([g for g in all_gaps if g.type == 'surplus'])} перенасыщенных")
        
        return self.district_analysis
    
    def _get_priority(self, percent: float, is_deficit: bool) -> str:
        """Определение приоритета ниши"""
        if is_deficit:
            # Дефицит — чем больше, тем важнее
            if percent >= 80:
                return "critical"
            elif percent >= 50:
                return "high"
            elif percent >= 30:
                return "medium"
            else:
                return "low"
        else:
            # Профицит — чем больше, тем важнее предупреждение
            if percent >= 100:
                return "critical"
            elif percent >= 60:
                return "high"
            elif percent >= 30:
                return "medium"
            else:
                return "low"
    
    def _get_recommendation(self, category: BusinessCategory, gap_type: str, gap: float) -> str:
        """Генерация рекомендации"""
        category_name = self.config.BUSINESS_NORMS.get(category, {}).get("name_ru", category.value)
        
        if gap_type == "deficit":
            recommendations = {
                BusinessCategory.CAR_WASH: f"Открыть {int(abs(gap))} автомойку(и) — высокий спрос",
                BusinessCategory.LAUNDRY: f"Открыть химчистку/прачечную — в районе нет ни одной",
                BusinessCategory.TUTORING: f"Открыть центр дополнительного образования",
                BusinessCategory.FAST_FOOD: f"Открыть точку фастфуда — дефицит",
                BusinessCategory.CAFE: f"Открыть кафе/столовую — мало заведений",
                BusinessCategory.BEAUTY: f"Открыть парикмахерскую — есть спрос",
                BusinessCategory.REPAIR: f"Открыть мастерскую по ремонту",
                BusinessCategory.FITNESS: f"Открыть фитнес-клуб или секцию"
            }
            return recommendations.get(category, f"Открыть {category_name} — дефицит {int(abs(gap))} шт.")
        else:
            return f"Рынок {category_name} перенасыщен. Рекомендуется избегать входа в этот сегмент в данном районе."
    
    # ==================== 3. ТОП ДЕФИЦИТНЫХ НИШ ====================
    
    async def get_top_deficits(self, limit: int = 10) -> List[MarketGap]:
        """
        Получение топ дефицитных ниш для предпринимателей
        """
        deficits = [g for g in self.market_gaps if g.type == "deficit"]
        deficits.sort(key=lambda x: (-abs(x.gap_percent), -x.estimated_demand))
        
        return deficits[:limit]
    
    async def get_top_surpluses(self, limit: int = 10) -> List[MarketGap]:
        """
        Получение топ перенасыщенных ниш (для предупреждения)
        """
        surpluses = [g for g in self.market_gaps if g.type == "surplus"]
        surpluses.sort(key=lambda x: -abs(x.gap_percent))
        
        return surpluses[:limit]
    
    # ==================== 4. ДАШБОРД ДЛЯ МЭРА ====================
    
    async def get_market_dashboard(self) -> Dict[str, Any]:
        """
        Дашборд рыночных ниш для мэра
        """
        if not self.district_analysis:
            await self.analyze_all_districts()
        
        # Статистика по городу
        total_businesses = 0
        for district in self.district_analysis:
            total_businesses += sum(district.businesses.values())
        
        deficits = [g for g in self.market_gaps if g.type == "deficit"]
        surpluses = [g for g in self.market_gaps if g.type == "surplus"]
        
        # Самые дефицитные районы
        district_deficit_rank = []
        for district in self.district_analysis:
            district_deficits = [g for g in deficits if g.district == district.district_name]
            district_deficit_rank.append({
                "name": district.district_name,
                "deficit_count": len(district_deficits),
                "score": district.overall_score
            })
        district_deficit_rank.sort(key=lambda x: x["deficit_count"], reverse=True)
        
        # Категории с наибольшим дефицитом
        category_deficit = defaultdict(int)
        for gap in deficits:
            category_deficit[gap.category_name] += gap.estimated_demand
        
        top_category_deficits = sorted(
            [{"category": k, "demand": v} for k, v in category_deficit.items()],
            key=lambda x: x["demand"],
            reverse=True
        )[:5]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "city": self.city_name,
            "population": self.total_population,
            "statistics": {
                "total_businesses": total_businesses,
                "businesses_per_10k": round(total_businesses / (self.total_population / 10000), 1),
                "deficit_niches": len(deficits),
                "surplus_niches": len(surpluses),
                "balanced_districts": sum(1 for d in self.district_analysis if 0.7 <= d.overall_score <= 1.3)
            },
            "top_deficits": [
                {
                    "category": g.category_name,
                    "district": g.district,
                    "current": g.current_count,
                    "optimal": g.optimal_count,
                    "demand": g.estimated_demand,
                    "priority": g.priority,
                    "recommendation": g.recommendation
                }
                for g in deficits[:10]
            ],
            "top_surpluses": [
                {
                    "category": g.category_name,
                    "district": g.district,
                    "current": g.current_count,
                    "optimal": g.optimal_count,
                    "excess": g.gap,
                    "priority": g.priority
                }
                for g in surpluses[:5]
            ],
            "district_ranking": district_deficit_rank[:5],
            "top_deficit_categories": top_category_deficits,
            "recommendations": self._generate_market_recommendations(deficits, surpluses)
        }
    
    def _generate_market_recommendations(self, deficits: List[MarketGap], surpluses: List[MarketGap]) -> List[str]:
        """Генерация рекомендаций для мэра и бизнеса"""
        recommendations = []
        
        # Для мэра
        if deficits:
            critical_deficits = [d for d in deficits if d.priority == "critical"]
            if critical_deficits:
                recommendations.append(f"🎯 Приоритет: в городе острая нехватка {', '.join(set(d.category_name for d in critical_deficits[:3]))}. Рекомендуется привлекать инвесторов в эти сегменты.")
        
        # Для предпринимателей
        if deficits:
            top_deficit = deficits[0]
            recommendations.append(f"💡 Предпринимателям: самая востребованная ниша — {top_deficit.category_name} в районе {top_deficit.district} (дефицит {top_deficit.estimated_demand} объекта).")
        
        # О перенасыщении
        if surpluses:
            top_surplus = surpluses[0]
            recommendations.append(f"⚠️ Внимание: рынок {top_surplus.category_name} в районе {top_surplus.district} перенасыщен. Не рекомендуется открывать новые точки.")
        
        return recommendations
    
    # ==================== 5. РЕКОМЕНДАЦИИ ДЛЯ ИНВЕСТОРОВ ====================
    
    async def get_investment_recommendations(self) -> Dict[str, Any]:
        """
        Инвестиционные рекомендации для бизнеса
        """
        deficits = await self.get_top_deficits(limit=20)
        
        # Группировка по категориям
        by_category = defaultdict(list)
        for gap in deficits:
            by_category[gap.category_name].append({
                "district": gap.district,
                "demand": gap.estimated_demand,
                "priority": gap.priority
            })
        
        # Формирование рекомендаций
        recommendations = []
        for category, locations in by_category.items():
            total_demand = sum(l["demand"] for l in locations)
            recommendations.append({
                "category": category,
                "total_demand": total_demand,
                "locations": locations[:3],
                "recommended_action": f"Открыть {int(total_demand)} {self._get_inflected_word(category)} в {', '.join([l['district'] for l in locations[:3]])}"
            })
        
        recommendations.sort(key=lambda x: x["total_demand"], reverse=True)
        
        return {
            "city": self.city_name,
            "generated_at": datetime.now().isoformat(),
            "top_opportunities": recommendations[:10],
            "total_potential_businesses": sum(r["total_demand"] for r in recommendations),
            "disclaimer": "Рекомендации основаны на анализе нормативов и текущей насыщенности рынка"
        }
    
    def _get_inflected_word(self, category: str) -> str:
        """Склонение названия категории"""
        # Упрощённая версия
        if category.endswith("ы") or category.endswith("и"):
            return category[:-1]
        return category


# ==================== ИНТЕГРАЦИЯ ====================

async def create_market_gap_analyzer(city_name: str, population: int) -> MarketGapAnalyzer:
    """Фабричная функция"""
    return MarketGapAnalyzer(city_name, population)


# ==================== ПРИМЕР ====================

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("🧪 Тестирование MarketGapAnalyzer...")
        
        # Создаём анализатор для Коломны
        analyzer = MarketGapAnalyzer("Коломна", 144589)
        
        # Загружаем демо-данные
        await analyzer.load_business_data()
        
        # 1. Анализ всех районов
        print("\n📊 АНАЛИЗ РАЙОНОВ:")
        districts = await analyzer.analyze_all_districts()
        
        for d in districts[:3]:
            print(f"  • {d.district_name}: {d.population:,} чел., сбалансированность {d.overall_score:.0%}")
        
        # 2. Топ дефицитных ниш
        print("\n🚨 ТОП ДЕФИЦИТНЫХ НИШ:")
        deficits = await analyzer.get_top_deficits(limit=5)
        for gap in deficits:
            print(f"  • {gap.category_name} в {gap.district}: дефицит {gap.estimated_demand} шт. ({gap.priority})")
        
        # 3. Топ перенасыщенных
        print("\n⚠️ ТОП ПЕРЕНАСЫЩЕННЫХ НИШ:")
        surpluses = await analyzer.get_top_surpluses(limit=3)
        for gap in surpluses:
            print(f"  • {gap.category_name} в {gap.district}: профицит {gap.gap} шт.")
        
        # 4. Дашборд
        print("\n📋 ДАШБОРД РЫНОЧНЫХ НИШ:")
        dashboard = await analyzer.get_market_dashboard()
        print(f"  Всего бизнесов: {dashboard['statistics']['total_businesses']}")
        print(f"  Дефицитных ниш: {dashboard['statistics']['deficit_niches']}")
        print(f"  Перенасыщенных: {dashboard['statistics']['surplus_niches']}")
        
        if dashboard['recommendations']:
            print(f"  Рекомендация: {dashboard['recommendations'][0]}")
        
        # 5. Инвестиционные рекомендации
        print("\n💼 ИНВЕСТИЦИОННЫЕ РЕКОМЕНДАЦИИ:")
        investments = await analyzer.get_investment_recommendations()
        print(f"  Потенциал новых бизнесов: {investments['total_potential_businesses']} шт.")
        
        if investments['top_opportunities']:
            top = investments['top_opportunities'][0]
            print(f"  Топ: {top['category']} — {top['recommended_action']}")
        
        print("\n✅ Тест завершен")
    
    asyncio.run(demo())
