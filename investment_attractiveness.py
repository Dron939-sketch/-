#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 22: ИНВЕСТИЦИОННАЯ ПРИВЛЕКАТЕЛЬНОСТЬ (Investment Attractiveness)
Система оценки и улучшения инвестиционного климата города

Основан на методах:
- Расчёт интегрального индекса инвестиционной привлекательности
- Сравнение с городами-конкурентами
- Выявление "узких мест" для инвесторов
- Генерация инвестиционных презентаций
- Рекомендации по улучшению инвестиционного климата
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

class InvestmentFactor(Enum):
    """Факторы инвестиционной привлекательности"""
    ECONOMY = "economy"                 # Экономический потенциал
    INFRASTRUCTURE = "infrastructure"   # Инфраструктура
    LABOR = "labor"                     # Трудовые ресурсы
    ADMIN = "admin"                     # Административные барьеры
    TAX = "tax"                         # Налоговые условия
    REAL_ESTATE = "real_estate"         # Недвижимость и земля
    LOGISTICS = "logistics"             # Логистика
    QUALITY_OF_LIFE = "quality_of_life" # Качество жизни
    INNOVATION = "innovation"           # Инновационный потенциал


@dataclass
class InvestmentProfile:
    """Инвестиционный профиль города"""
    city_name: str
    overall_index: float                # 0-1, общий индекс
    rank: int                           # место среди городов
    total_cities: int
    
    # Факторы с оценками
    factors: Dict[InvestmentFactor, float]
    
    # Сильные и слабые стороны
    strengths: List[str]
    weaknesses: List[str]
    
    # Инвестиционные ниши
    promising_sectors: List[str]
    
    # Конкуренты
    main_competitors: List[str]
    
    # Рекомендации
    recommendations: List[str]
    
    updated_at: datetime


@dataclass
class Investor:
    """Потенциальный инвестор"""
    id: str
    name: str
    sector: str
    investment_size_million_rub: float
    key_requirements: List[str]
    priority: str                       # high/medium/low
    contact_person: str
    status: str                         # prospect/negotiating/committed


# ==================== КОНФИГУРАЦИЯ ====================

class InvestmentConfig:
    """Конфигурация системы инвестиционной привлекательности"""
    
    # Веса факторов
    FACTOR_WEIGHTS = {
        InvestmentFactor.ECONOMY: 0.20,
        InvestmentFactor.INFRASTRUCTURE: 0.15,
        InvestmentFactor.LABOR: 0.12,
        InvestmentFactor.ADMIN: 0.12,
        InvestmentFactor.TAX: 0.10,
        InvestmentFactor.LOGISTICS: 0.10,
        InvestmentFactor.REAL_ESTATE: 0.08,
        InvestmentFactor.QUALITY_OF_LIFE: 0.08,
        InvestmentFactor.INNOVATION: 0.05
    }
    
    # Города-конкуренты (для сравнения)
    COMPETITOR_CITIES = [
        "Серпухов", "Подольск", "Воскресенск", "Егорьевск", "Зарайск", "Кашира"
    ]
    
    # Пороги оценок
    EXCELLENT_THRESHOLD = 0.8
    GOOD_THRESHOLD = 0.6
    POOR_THRESHOLD = 0.4


# ==================== ОСНОВНОЙ КЛАСС ====================

class InvestmentAttractivenessEngine:
    """
    Система оценки и улучшения инвестиционной привлекательности
    
    Позволяет:
    - Оценить инвестиционный потенциал города
    - Увидеть слабые места для инвесторов
    - Сравнить с городами-конкурентами
    - Получить рекомендации по улучшению
    - Сгенерировать инвестиционную презентацию
    """
    
    def __init__(self, city_name: str, config: InvestmentConfig = None):
        self.city_name = city_name
        self.config = config or InvestmentConfig()
        
        # Данные города
        self.current_profile: Optional[InvestmentProfile] = None
        self.investors: List[Investor] = []
        self.investment_projects: List[Dict] = []
        
        # История
        self.profile_history: List[InvestmentProfile] = []
        
        logger.info(f"InvestmentAttractivenessEngine инициализирован для города {city_name}")
    
    # ==================== 1. ОЦЕНКА ФАКТОРОВ ====================
    
    async def assess_factors(self, city_metrics: Dict[str, float]) -> Dict[InvestmentFactor, float]:
        """
        Оценка факторов инвестиционной привлекательности
        """
        logger.info("Оценка факторов инвестиционной привлекательности...")
        
        scores = {}
        
        # 1. Экономический потенциал (на основе ТФ)
        economy_score = city_metrics.get('ТФ', 3.0) / 6.0
        scores[InvestmentFactor.ECONOMY] = economy_score
        
        # 2. Инфраструктура (на основе УБ)
        infra_score = city_metrics.get('УБ', 3.0) / 6.0
        scores[InvestmentFactor.INFRASTRUCTURE] = infra_score
        
        # 3. Трудовые ресурсы (на основе демографии и образования)
        labor_score = await self._assess_labor_resources()
        scores[InvestmentFactor.LABOR] = labor_score
        
        # 4. Административные барьеры (на основе ЧВ и доверия)
        admin_score = 1 - (city_metrics.get('ЧВ', 3.0) / 6.0) * 0.5
        scores[InvestmentFactor.ADMIN] = min(1.0, max(0.2, admin_score))
        
        # 5. Налоговые условия
        tax_score = await self._assess_tax_conditions()
        scores[InvestmentFactor.TAX] = tax_score
        
        # 6. Логистика (транспортная доступность)
        logistics_score = await self._assess_logistics()
        scores[InvestmentFactor.LOGISTICS] = logistics_score
        
        # 7. Недвижимость и земля
        real_estate_score = await self._assess_real_estate()
        scores[InvestmentFactor.REAL_ESTATE] = real_estate_score
        
        # 8. Качество жизни
        qol_score = city_metrics.get('УБ', 3.0) / 6.0
        scores[InvestmentFactor.QUALITY_OF_LIFE] = qol_score
        
        # 9. Инновационный потенциал
        innovation_score = await self._assess_innovation()
        scores[InvestmentFactor.INNOVATION] = innovation_score
        
        return scores
    
    async def _assess_labor_resources(self) -> float:
        """Оценка трудовых ресурсов"""
        # В реальности — данные по безработице, образованию, демографии
        # Для демо — средняя оценка
        return 0.65
    
    async def _assess_tax_conditions(self) -> float:
        """Оценка налоговых условий"""
        # Наличие льгот, ставки, администрирование
        return 0.55
    
    async def _assess_logistics(self) -> float:
        """Оценка логистики"""
        # Близость к трассам, ж/д, аэропортам
        # Коломна: М5, ж/д, близость к Москве
        return 0.75
    
    async def _assess_real_estate(self) -> float:
        """Оценка рынка недвижимости"""
        # Цены, наличие площадок, свободные земли
        return 0.60
    
    async def _assess_innovation(self) -> float:
        """Оценка инновационного потенциала"""
        # Наличие IT-школ, стартапов, технопарков
        return 0.45
    
    # ==================== 2. РАСЧЁТ ИНТЕГРАЛЬНОГО ИНДЕКСА ====================
    
    async def calculate_investment_index(self, city_metrics: Dict[str, float]) -> InvestmentProfile:
        """
        Расчёт интегрального индекса инвестиционной привлекательности
        """
        logger.info("Расчёт инвестиционного индекса...")
        
        # Оценка факторов
        factors = await self.assess_factors(city_metrics)
        
        # Взвешенная сумма
        overall_index = 0
        for factor, weight in self.config.FACTOR_WEIGHTS.items():
            overall_index += factors.get(factor, 0.5) * weight
        
        # Определяем сильные и слабые стороны
        strengths = []
        weaknesses = []
        
        for factor, score in factors.items():
            if score >= self.config.EXCELLENT_THRESHOLD:
                strengths.append(self._get_factor_name(factor))
            elif score <= self.config.POOR_THRESHOLD:
                weaknesses.append(self._get_factor_name(factor))
        
        # Определяем перспективные сектора
        promising_sectors = await self._identify_promising_sectors(factors)
        
        # Рекомендации
        recommendations = await self._generate_recommendations(weaknesses, factors)
        
        # Сравнение с конкурентами
        competitors_data = await self._compare_with_competitors(city_metrics)
        
        profile = InvestmentProfile(
            city_name=self.city_name,
            overall_index=overall_index,
            rank=competitors_data.get('rank', 5),
            total_cities=len(self.config.COMPETITOR_CITIES) + 1,
            factors=factors,
            strengths=strengths,
            weaknesses=weaknesses,
            promising_sectors=promising_sectors,
            main_competitors=self.config.COMPETITOR_CITIES[:3],
            recommendations=recommendations,
            updated_at=datetime.now()
        )
        
        self.current_profile = profile
        self.profile_history.append(profile)
        
        logger.info(f"Инвестиционный индекс {self.city_name}: {overall_index:.0%}")
        return profile
    
    def _get_factor_name(self, factor: InvestmentFactor) -> str:
        """Название фактора на русском"""
        names = {
            InvestmentFactor.ECONOMY: "Экономический потенциал",
            InvestmentFactor.INFRASTRUCTURE: "Инфраструктура",
            InvestmentFactor.LABOR: "Трудовые ресурсы",
            InvestmentFactor.ADMIN: "Административные барьеры",
            InvestmentFactor.TAX: "Налоговые условия",
            InvestmentFactor.LOGISTICS: "Логистика",
            InvestmentFactor.REAL_ESTATE: "Недвижимость и земля",
            InvestmentFactor.QUALITY_OF_LIFE: "Качество жизни",
            InvestmentFactor.INNOVATION: "Инновационный потенциал"
        }
        return names.get(factor, factor.value)
    
    async def _identify_promising_sectors(self, factors: Dict[InvestmentFactor, float]) -> List[str]:
        """Определение перспективных секторов для инвестиций"""
        sectors = []
        
        if factors.get(InvestmentFactor.LOGISTICS, 0) > 0.7:
            sectors.append("Логистика и складская недвижимость")
        
        if factors.get(InvestmentFactor.INNOVATION, 0) > 0.5:
            sectors.append("IT и цифровые технологии")
        
        if factors.get(InvestmentFactor.QUALITY_OF_LIFE, 0) > 0.6:
            sectors.append("Туризм и гостиничный бизнес")
        
        sectors.append("Производство стройматериалов")
        
        return sectors[:4]
    
    async def _generate_recommendations(self, weaknesses: List[str], factors: Dict[InvestmentFactor, float]) -> List[str]:
        """Генерация рекомендаций по улучшению"""
        recommendations = []
        
        if "Административные барьеры" in weaknesses:
            recommendations.append("📋 Создать инвестиционный портал и сократить сроки согласований")
        
        if "Налоговые условия" in weaknesses:
            recommendations.append("💰 Рассмотреть налоговые льготы для приоритетных инвесторов")
        
        if "Инфраструктура" in weaknesses:
            recommendations.append("🏗️ Подготовить инвестиционные площадки с коммуникациями")
        
        if "Инновационный потенциал" in weaknesses:
            recommendations.append("💡 Создать бизнес-инкубатор или технопарк")
        
        if not recommendations:
            recommendations.append("✅ Поддерживать текущий уровень, фокус на привлечении якорных инвесторов")
        
        return recommendations
    
    async def _compare_with_competitors(self, city_metrics: Dict[str, float]) -> Dict[str, Any]:
        """Сравнение с городами-конкурентами"""
        # В реальности — данные по конкурентам
        # Для демо — симуляция
        return {
            'rank': 4,
            'best_in': "Логистика",
            'worst_in': "Инновации"
        }
    
    # ==================== 3. РАБОТА С ИНВЕСТОРАМИ ====================
    
    async def add_investor(self, investor: Investor):
        """Добавление потенциального инвестора"""
        self.investors.append(investor)
        logger.info(f"Добавлен инвестор: {investor.name} ({investor.sector})")
    
    async def match_investors(self) -> List[Dict]:
        """
        Сопоставление инвесторов с инвестиционными возможностями города
        """
        matches = []
        
        for investor in self.investors:
            # Проверяем соответствие сектора
            if investor.sector in await self._get_city_sectors():
                matches.append({
                    'investor': investor.name,
                    'sector': investor.sector,
                    'investment_size': investor.investment_size_million_rub,
                    'match_score': 0.8,
                    'recommended_action': f"Организовать встречу с {investor.contact_person}"
                })
        
        matches.sort(key=lambda x: x['match_score'], reverse=True)
        return matches
    
    async def _get_city_sectors(self) -> List[str]:
        """Получение приоритетных секторов города"""
        if self.current_profile:
            return self.current_profile.promising_sectors
        return ["Производство", "Логистика", "Туризм"]
    
    # ==================== 4. ИНВЕСТИЦИОННАЯ ПРЕЗЕНТАЦИЯ ====================
    
    async def generate_investment_presentation(self) -> Dict[str, Any]:
        """
        Генерация инвестиционной презентации города
        """
        if not self.current_profile:
            await self.calculate_investment_index({'ТФ': 3.2, 'УБ': 3.8, 'ЧВ': 3.0})
        
        presentation = {
            'city': self.city_name,
            'generated_at': datetime.now().isoformat(),
            'sections': [
                {
                    'title': 'Ключевые показатели',
                    'content': {
                        'Инвестиционный индекс': f"{self.current_profile.overall_index:.0%}",
                        'Место среди городов': f"{self.current_profile.rank}/{self.current_profile.total_cities}",
                        'Население': "144 589 чел.",
                        'Бюджет': "5.8 млрд ₽",
                        'Транспортная доступность': "40 мин до Москвы (МЦД)"
                    }
                },
                {
                    'title': 'Конкурентные преимущества',
                    'content': self.current_profile.strengths
                },
                {
                    'title': 'Перспективные сектора для инвестиций',
                    'content': self.current_profile.promising_sectors
                },
                {
                    'title': 'Инвестиционные площадки',
                    'content': [
                        "Площадка «Северная» (25 га, коммуникации подведены)",
                        "Площадка «Южная» (40 га, рядом с трассой М5)",
                        "Бизнес-центр «Коломенский» (офисные помещения)"
                    ]
                },
                {
                    'title': 'Меры поддержки',
                    'content': [
                        "Налоговые льготы до 50% на 3 года",
                        "Субсидии на подключение к сетям",
                        "Сопровождение инвестора по принципу «одного окна»"
                    ]
                },
                {
                    'title': 'Ключевые контакты',
                    'content': [
                        "Глава города: {self.mayor_name}",
                        "Инвестиционный уполномоченный: +7 (XXX) XXX-XX-XX",
                        "Email: invest@kolomna.ru"
                    ]
                }
            ],
            'recommendations': self.current_profile.recommendations
        }
        
        return presentation
    
    # ==================== 5. ДАШБОРД ====================
    
    async def get_investment_dashboard(self) -> Dict[str, Any]:
        """
        Дашборд инвестиционной привлекательности
        """
        if not self.current_profile:
            await self.calculate_investment_index({'ТФ': 3.2, 'УБ': 3.8, 'ЧВ': 3.0})
        
        # Факторы с цветовой индикацией
        factors_colored = []
        for factor, score in self.current_profile.factors.items():
            if score >= 0.8:
                color = "green"
            elif score >= 0.6:
                color = "yellow"
            elif score >= 0.4:
                color = "orange"
            else:
                color = "red"
            
            factors_colored.append({
                'name': self._get_factor_name(factor),
                'score': score,
                'color': color
            })
        
        return {
            'timestamp': datetime.now().isoformat(),
            'city': self.city_name,
            'overall_index': self.current_profile.overall_index,
            'rank': f"{self.current_profile.rank}/{self.current_profile.total_cities}",
            'factors': factors_colored,
            'strengths': self.current_profile.strengths,
            'weaknesses': self.current_profile.weaknesses,
            'promising_sectors': self.current_profile.promising_sectors,
            'active_investors': len(self.investors),
            'recommendations': self.current_profile.recommendations,
            'quick_wins': self._get_quick_wins()
        }
    
    def _get_quick_wins(self) -> List[str]:
        """Быстрые победы для улучшения инвестклимата"""
        return [
            "🚀 Запустить инвестиционный портал (2 недели)",
            "📋 Создать реестр инвестиционных площадок (1 месяц)",
            "🤝 Провести инвестиционный форум (3 месяца)",
            "🏆 Привлечь первого якорного инвестора (6 месяцев)"
        ]


# ==================== ИНТЕГРАЦИЯ ====================

async def create_investment_engine(city_name: str) -> InvestmentAttractivenessEngine:
    """Фабричная функция"""
    return InvestmentAttractivenessEngine(city_name)


# ==================== ПРИМЕР ====================

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("🧪 Тестирование InvestmentAttractivenessEngine...")
        
        engine = InvestmentAttractivenessEngine("Коломна")
        
        # 1. Расчёт индекса
        print("\n📊 РАСЧЁТ ИНВЕСТИЦИОННОГО ИНДЕКСА:")
        metrics = {'ТФ': 3.2, 'УБ': 3.8, 'ЧВ': 3.0}
        profile = await engine.calculate_investment_index(metrics)
        print(f"  Общий индекс: {profile.overall_index:.0%}")
        print(f"  Место: {profile.rank}/{profile.total_cities}")
        print(f"  Сильные стороны: {', '.join(profile.strengths)}")
        print(f"  Слабые стороны: {', '.join(profile.weaknesses)}")
        
        # 2. Перспективные сектора
        print(f"\n🎯 ПЕРСПЕКТИВНЫЕ СЕКТОРА:")
        for sector in profile.promising_sectors:
            print(f"  • {sector}")
        
        # 3. Рекомендации
        print(f"\n💡 РЕКОМЕНДАЦИИ:")
        for rec in profile.recommendations:
            print(f"  • {rec}")
        
        # 4. Добавление инвестора
        print("\n🤝 РАБОТА С ИНВЕСТОРАМИ:")
        investor = Investor(
            id="inv_001",
            name="ООО «Логистик Плюс»",
            sector="Логистика",
            investment_size_million_rub=500,
            key_requirements=["Земельный участок 10 га", "Подъездные пути"],
            priority="high",
            contact_person="Иванов И.И.",
            status="prospect"
        )
        await engine.add_investor(investor)
        print(f"  Добавлен инвестор: {investor.name}")
        
        # 5. Инвестиционная презентация
        print("\n📄 ИНВЕСТИЦИОННАЯ ПРЕЗЕНТАЦИЯ:")
        presentation = await engine.generate_investment_presentation()
        for section in presentation['sections'][:2]:
            print(f"  • {section['title']}")
        
        # 6. Дашборд
        print("\n📋 ДАШБОРД ИНВЕСТИЦИОННОЙ ПРИВЛЕКАТЕЛЬНОСТИ:")
        dashboard = await engine.get_investment_dashboard()
        print(f"  Индекс: {dashboard['overall_index']:.0%}")
        print(f"  Ранг: {dashboard['rank']}")
        print(f"  Активных инвесторов: {dashboard['active_investors']}")
        print(f"  Быстрая победа: {dashboard['quick_wins'][0]}")
        
        print("\n✅ Тест завершен")
    
    asyncio.run(demo())
