# metrics/composite_index.py
"""
Композитные индексы для дашборда мэра
Объединяет все метрики в единую систему
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class CompositeIndices:
    """Композитные индексы города"""
    timestamp: datetime
    
    # Основные индексы
    quality_of_life_index: float      # 0-1 качество жизни
    economic_development_index: float # 0-1 экономическое развитие
    social_cohesion_index: float      # 0-1 социальная сплочённость
    environmental_index: float        # 0-1 экологическое благополучие
    infrastructure_index: float       # 0-1 инфраструктура
    
    # Производные
    mayoral_performance_index: float  # 0-1 эффективность мэра
    city_attractiveness_index: float  # 0-1 привлекательность для жизни
    future_outlook_index: float       # 0-1 перспективы развития
    
    # Цветовая индикация
    overall_color: str  # red, orange, yellow, lightgreen, green
    
class CompositeIndexCalculator:
    """Калькулятор композитных индексов"""
    
    def __init__(self):
        self.history = []
    
    def calculate_all_indices(self, 
                              city_metrics: Dict,
                              trust_data: Any,
                              happiness_data: Any,
                              weather_data: Any,
                              infrastructure_data: Dict = None) -> CompositeIndices:
        """Расчёт всех композитных индексов"""
        
        # 1. Качество жизни
        quality_of_life = self._calculate_quality_of_life(city_metrics, happiness_data)
        
        # 2. Экономическое развитие
        economic_development = self._calculate_economic_development(city_metrics)
        
        # 3. Социальная сплочённость
        social_cohesion = self._calculate_social_cohesion(city_metrics, trust_data)
        
        # 4. Экологическое благополучие
        environmental = self._calculate_environmental(city_metrics, weather_data)
        
        # 5. Инфраструктура
        infrastructure = self._calculate_infrastructure(infrastructure_data)
        
        # 6. Эффективность мэра (композит)
        mayoral_performance = self._calculate_mayoral_performance(
            trust_data, economic_development, quality_of_life
        )
        
        # 7. Привлекательность города
        city_attractiveness = self._calculate_attractiveness(
            quality_of_life, economic_development, environmental
        )
        
        # 8. Перспективы развития
        future_outlook = self._calculate_future_outlook(
            economic_development, social_cohesion, mayoral_performance
        )
        
        # Определяем общий цвет
        overall_score = (quality_of_life + economic_development + social_cohesion) / 3
        overall_color = self._get_color_by_score(overall_score)
        
        indices = CompositeIndices(
            timestamp=datetime.now(),
            quality_of_life_index=quality_of_life,
            economic_development_index=economic_development,
            social_cohesion_index=social_cohesion,
            environmental_index=environmental,
            infrastructure_index=infrastructure,
            mayoral_performance_index=mayoral_performance,
            city_attractiveness_index=city_attractiveness,
            future_outlook_index=future_outlook,
            overall_color=overall_color
        )
        
        self.history.append(indices)
        
        # Оставляем историю за 90 дней
        if len(self.history) > 90:
            self.history = self.history[-90:]
        
        return indices
    
    def _calculate_quality_of_life(self, city_metrics: Dict, happiness_data: Any) -> float:
        """Индекс качества жизни"""
        # Комбинация вектора УБ и индекса счастья
        ub_score = city_metrics.get('УБ', 3.0) / 6.0
        
        if happiness_data:
            happiness_score = happiness_data.overall_happiness
        else:
            happiness_score = 0.5
        
        # Взвешенное среднее
        return ub_score * 0.6 + happiness_score * 0.4
    
    def _calculate_economic_development(self, city_metrics: Dict) -> float:
        """Индекс экономического развития"""
        # Комбинация вектора ТФ и дополнительных факторов
        tf_score = city_metrics.get('ТФ', 3.0) / 6.0
        
        # В идеале добавить: рост бюджета, инвестиции, занятость
        # Для демо используем только базовый вектор
        return tf_score
    
    def _calculate_social_cohesion(self, city_metrics: Dict, trust_data: Any) -> float:
        """Индекс социальной сплочённости"""
        # Комбинация вектора ЧВ и доверия
        chv_score = city_metrics.get('ЧВ', 3.0) / 6.0
        
        if trust_data:
            trust_score = trust_data.trust_index
        else:
            trust_score = 0.5
        
        return chv_score * 0.5 + trust_score * 0.5
    
    def _calculate_environmental(self, city_metrics: Dict, weather_data: Any) -> float:
        """Экологический индекс"""
        # Базовое значение из качества жизни
        ub_score = city_metrics.get('УБ', 3.0) / 6.0
        
        # Корректировка погодой (хорошая погода = приятно)
        if weather_data and hasattr(weather_data, 'comfort_index'):
            weather_factor = weather_data.comfort_index
        else:
            weather_factor = 0.5
        
        return ub_score * 0.7 + weather_factor * 0.3
    
    def _calculate_infrastructure(self, infrastructure_data: Dict) -> float:
        """Инфраструктурный индекс"""
        if not infrastructure_data:
            return 0.5
        
        # Пример: дороги, транспорт, связь, энергетика
        weights = {
            'roads': 0.3,
            'transport': 0.3,
            'utilities': 0.2,
            'digital': 0.2
        }
        
        score = 0
        for key, weight in weights.items():
            score += infrastructure_data.get(key, 0.5) * weight
        
        return score
    
    def _calculate_mayoral_performance(self, trust_data: Any, 
                                       economic_score: float, 
                                       quality_score: float) -> float:
        """Индекс эффективности мэра"""
        if trust_data:
            trust_score = trust_data.trust_index
        else:
            trust_score = 0.5
        
        # Доверие - главный показатель, плюс объективные результаты
        return trust_score * 0.5 + economic_score * 0.25 + quality_score * 0.25
    
    def _calculate_attractiveness(self, quality_score: float, 
                                  economic_score: float, 
                                  environmental_score: float) -> float:
        """Индекс привлекательности города"""
        return (quality_score * 0.4 + economic_score * 0.3 + environmental_score * 0.3)
    
    def _calculate_future_outlook(self, economic_score: float, 
                                  social_score: float, 
                                  mayoral_score: float) -> float:
        """Индекс перспектив развития"""
        # Оптимистичный взгляд: если сейчас хорошо и мэр эффективен
        current_state = (economic_score + social_score) / 2
        leadership_factor = mayoral_score
        
        return current_state * 0.6 + leadership_factor * 0.4
    
    def _get_color_by_score(self, score: float) -> str:
        """Цветовая индикация по оценке"""
        if score >= 0.8:
            return 'green'
        elif score >= 0.6:
            return 'lightgreen'
        elif score >= 0.4:
            return 'yellow'
        elif score >= 0.2:
            return 'orange'
        else:
            return 'red'
    
    def get_historical_trend(self, index_name: str, days: int = 30) -> List[float]:
        """Получение исторического тренда по индексу"""
        if not self.history:
            return []
        
        relevant = self.history[-days:]
        return [getattr(h, index_name, 0) for h in relevant]
