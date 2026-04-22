# metrics/happiness_analyzer.py
"""
Анализ уровня счастья и удовлетворённости горожан
Композитный индекс из различных источников
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging
import math

logger = logging.getLogger(__name__)

@dataclass
class HappinessData:
    """Данные о счастье горожан"""
    timestamp: datetime
    overall_happiness: float  # 0-1
    life_satisfaction: float  # 0-1
    emotional_state: float    # 0-1
    social_connection: float  # 0-1
    purpose_index: float      # 0-1
    sub_indices: Dict[str, float]
    top_factors: List[str]

class HappinessAnalyzer:
    """Анализ уровня счастья"""
    
    def __init__(self, city_name: str):
        self.city_name = city_name
        self.happiness_history = []
        
        # Веса для компонентов счастья
        self.weights = {
            'economic': 0.25,      # доходы, работа
            'social': 0.25,        # отношения, поддержка
            'health': 0.15,        # здоровье, спорт
            'environment': 0.15,   # экология, благоустройство
            'safety': 0.10,        # безопасность
            'leisure': 0.10        # досуг, культура
        }
    
    async def calculate_happiness(self, city_metrics: Dict, trust_data: TrustData, weather: Any) -> HappinessData:
        """Расчёт комплексного индекса счастья"""
        
        # 1. Экономическая составляющая
        economic_score = self._calculate_economic_happiness(city_metrics)
        
        # 2. Социальная составляющая (из доверия)
        social_score = trust_data.trust_index if trust_data else 0.5
        
        # 3. Здоровье (из метрик качества жизни)
        health_score = city_metrics.get('УБ', 3.0) / 6.0
        
        # 4. Экологическая составляющая
        environment_score = self._calculate_environment_happiness(city_metrics)
        
        # 5. Безопасность
        safety_score = city_metrics.get('СБ', 3.0) / 6.0
        
        # 6. Досуг и культура
        leisure_score = self._calculate_leisure_happiness(city_metrics)
        
        # Суб-индексы
        sub_indices = {
            'economic': economic_score,
            'social': social_score,
            'health': health_score,
            'environment': environment_score,
            'safety': safety_score,
            'leisure': leisure_score
        }
        
        # Общий индекс (взвешенный)
        overall = sum(sub_indices[k] * self.weights.get(k, 0.1) for k in sub_indices)
        
        # Дополнительные корректировки
        if weather and hasattr(weather, 'comfort_index'):
            # Хорошая погода повышает счастье
            weather_boost = (weather.comfort_index - 0.5) * 0.1
            overall += weather_boost
            overall = max(0, min(1, overall))
        
        # Эмоциональное состояние (коррелирует с общим счастьем)
        emotional_state = overall * 0.8 + 0.2 * (trust_data.trust_index if trust_data else 0.5)
        
        # Социальные связи (из соцкапитала)
        social_connection = city_metrics.get('ЧВ', 3.0) / 6.0
        
        # Ощущение цели/смысла (из развития города)
        purpose_index = self._calculate_purpose_index(city_metrics)
        
        # Топ-факторы, влияющие на счастье
        top_factors = sorted(sub_indices.items(), key=lambda x: x[1], reverse=True)[:3]
        top_factors_names = {
            'economic': 'экономическое благополучие',
            'social': 'социальные связи',
            'health': 'здоровье',
            'environment': 'экология и благоустройство',
            'safety': 'безопасность',
            'leisure': 'досуг и культура'
        }
        
        happiness_data = HappinessData(
            timestamp=datetime.now(),
            overall_happiness=overall,
            life_satisfaction=overall * 0.9 + 0.1,
            emotional_state=emotional_state,
            social_connection=social_connection,
            purpose_index=purpose_index,
            sub_indices=sub_indices,
            top_factors=[top_factors_names.get(f, f) for f, _ in top_factors]
        )
        
        self.happiness_history.append(happiness_data)
        
        # Оставляем историю за 30 дней
        if len(self.happiness_history) > 30:
            self.happiness_history = self.happiness_history[-30:]
        
        return happiness_data
    
    def _calculate_economic_happiness(self, city_metrics: Dict) -> float:
        """Экономическая составляющая счастья"""
        # Используем уровень экономики (ТФ)
        economy_level = city_metrics.get('ТФ', 3.0) / 6.0
        
        # Добавляем фактор работы (в идеале из данных по безработице)
        # Для демо используем корреляцию с экономикой
        employment_factor = economy_level * 0.8 + 0.2
        
        return (economy_level * 0.6 + employment_factor * 0.4)
    
    def _calculate_environment_happiness(self, city_metrics: Dict) -> float:
        """Экологическая составляющая счастья"""
        # Используем качество жизни (УБ) как прокси для экологии
        quality_level = city_metrics.get('УБ', 3.0) / 6.0
        
        # В идеале добавить реальные экологические данные
        return quality_level
    
    def _calculate_leisure_happiness(self, city_metrics: Dict) -> float:
        """Составляющая досуга и культуры"""
        # Используем социальный капитал и качество жизни
        social_level = city_metrics.get('ЧВ', 3.0) / 6.0
        quality_level = city_metrics.get('УБ', 3.0) / 6.0
        
        return (social_level + quality_level) / 2
    
    def _calculate_purpose_index(self, city_metrics: Dict) -> float:
        """Индекс ощущения цели/смысла"""
        # Люди чувствуют цель, когда город развивается
        economy_level = city_metrics.get('ТФ', 3.0) / 6.0
        social_level = city_metrics.get('ЧВ', 3.0) / 6.0
        
        # Перспективы роста
        growth_potential = (economy_level + social_level) / 2
        
        return growth_potential
    
    def get_happiness_trend(self) -> Dict[str, Any]:
        """Анализ тренда счастья"""
        if len(self.happiness_history) < 2:
            return {'trend': 'stable', 'change': 0}
        
        recent = self.happiness_history[-7:]  # последние 7 дней
        older = self.happiness_history[-14:-7] if len(self.happiness_history) > 14 else []
        
        if older:
            recent_avg = sum(h.overall_happiness for h in recent) / len(recent)
            older_avg = sum(h.overall_happiness for h in older) / len(older)
            change = recent_avg - older_avg
        else:
            change = self.happiness_history[-1].overall_happiness - self.happiness_history[0].overall_happiness
        
        if change > 0.05:
            trend = 'rising'
        elif change < -0.05:
            trend = 'falling'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'change': change,
            'current': self.happiness_history[-1].overall_happiness if self.happiness_history else 0.5
        }
    
    def get_happiness_breakdown(self) -> Dict[str, float]:
        """Детализация компонентов счастья"""
        if not self.happiness_history:
            return {k: 0.5 for k in self.weights.keys()}
        
        latest = self.happiness_history[-1]
        return latest.sub_indices
