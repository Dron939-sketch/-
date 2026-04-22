#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 10: ПРЕДИКТОР КРИЗИСОВ (Crisis Predictor)
Система раннего предупреждения о кризисных ситуациях в городе

Основан на методах:
- Анализ временных рядов и трендов
- Машинное обучение (Random Forest, LSTM для временных рядов)
- Детекция аномалий (Isolation Forest)
- Мультифакторное прогнозирование
- Геопространственный анализ
"""

import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import logging
import json
import hashlib
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error

# Для временных рядов (если доступно)
try:
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    logging.warning("TensorFlow не установлен. LSTM-прогнозы будут отключены.")

logger = logging.getLogger(__name__)


# ==================== МОДЕЛИ ДАННЫХ ====================

class CrisisType(Enum):
    """Типы кризисов"""
    SAFETY = "safety"                 # Кризис безопасности
    SOCIAL = "social"                 # Социальный кризис (протесты)
    ECONOMIC = "economic"             # Экономический кризис
    INFRASTRUCTURE = "infrastructure" # Инфраструктурный кризис
    ECOLOGICAL = "ecological"         # Экологический кризис
    REPUTATIONAL = "reputational"     # Репутационный кризис
    HEALTH = "health"                 # Кризис здравоохранения
    TRANSPORT = "transport"           # Транспортный коллапс
    UTILITY = "utility"               # Коммунальная авария


class CrisisLevel(Enum):
    """Уровень кризиса"""
    CRITICAL = "critical"    # Неминуемый кризис, 24-48 часов
    HIGH = "high"            # Высокая вероятность, 3-7 дней
    MEDIUM = "medium"        # Средняя вероятность, 1-4 недели
    LOW = "low"              # Низкая вероятность, 1-3 месяца
    WATCH = "watch"          # Мониторинг, 3-6 месяцев


@dataclass
class CrisisPrediction:
    """Прогноз кризиса"""
    id: str
    crisis_type: CrisisType
    level: CrisisLevel
    probability: float              # 0-1, вероятность наступления
    time_horizon_days: int         # через сколько дней ожидается
    location: str                   # район или локация
    description: str
    triggers: List[str]             # триггеры, которые могут спровоцировать
    indicators: Dict[str, float]    # текущие значения индикаторов
    threshold: float                # пороговое значение
    trend: str                      # rising/stable/declining
    confidence: float               # уверенность прогноза (0-1)
    recommended_actions: List[str]
    affected_vectors: List[str]     # векторы Мейстера
    created_at: datetime
    expires_at: datetime


@dataclass
class EarlyWarning:
    """Раннее предупреждение"""
    id: str
    crisis_prediction_id: str
    severity: str                   # warning/alert/critical
    message: str
    timestamp: datetime
    is_acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None


# ==================== КОНФИГУРАЦИЯ ====================

class CrisisPredictorConfig:
    """Конфигурация предиктора кризисов"""
    
    # Пороги для разных типов кризисов
    CRISIS_THRESHOLDS = {
        CrisisType.SAFETY: {
            'crime_rate': 0.7,      # рост преступности > 70% от нормы
            'social_negativity': 0.8,  # негатив в соцсетях > 80%
            'fear_index': 0.75
        },
        CrisisType.SOCIAL: {
            'protest_mentions': 50,     # >50 упоминаний протестов
            'radical_activity': 0.7,    # радикальная активность >70%
            'trust_decline': -0.3       # падение доверия >30%
        },
        CrisisType.ECONOMIC: {
            'business_closures': 0.4,   # закрытие >40% бизнеса
            'unemployment_rate': 0.12,  # безработица >12%
            'budget_deficit': 0.2       # дефицит бюджета >20%
        },
        CrisisType.INFRASTRUCTURE: {
            'road_accidents': 0.5,      # рост ДТП >50%
            'utility_breakdowns': 10,   # >10 аварий в день
            'complaints_volume': 100    # >100 жалоб в день
        },
        CrisisType.REPUTATIONAL: {
            'negative_narratives': 0.6, # негативные нарративы >60%
            'trust_index': 0.4,         # доверие <40%
            'coordinated_attack': 0.7   # скоординированная атака
        }
    }
    
    # Веса для мультифакторного прогноза
    FACTOR_WEIGHTS = {
        'current_value': 0.30,
        'trend_slope': 0.25,
        'acceleration': 0.20,
        'seasonal_factor': 0.10,
        'external_factors': 0.15
    }
    
    # Периоды прогнозирования (дни)
    FORECAST_HORIZONS = [3, 7, 14, 30, 60, 90]
    
    # Частота обновления прогнозов (часы)
    UPDATE_INTERVAL_HOURS = 6


# ==================== ОСНОВНОЙ КЛАСС ====================

class CrisisPredictor:
    """
    Предиктор кризисов — система раннего предупреждения
    
    Анализирует временные ряды метрик и соцсетей,
    предсказывает вероятность кризисов различных типов
    """
    
    def __init__(self, city_name: str, config: CrisisPredictorConfig = None):
        self.city_name = city_name
        self.config = config or CrisisPredictorConfig()
        
        # Хранилище
        self.predictions: Dict[str, CrisisPrediction] = {}
        self.warnings: List[EarlyWarning] = []
        self.historical_data: Dict[str, List[Dict]] = defaultdict(list)
        
        # Модели ML
        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        
        # Кэш для временных рядов
        self.time_series_cache: Dict[str, pd.Series] = {}
        
        # История для обучения моделей
        self.training_history: List[Dict] = []
        
        # Параметры
        self.last_prediction_time = None
        self.is_trained = False
        
        logger.info(f"CrisisPredictor инициализирован для города {city_name}")
    
    # ==================== 1. СБОР И ПОДГОТОВКА ДАННЫХ ====================
    
    async def collect_indicators(self, 
                                  metrics: Dict[str, float],
                                  social_data: List[Dict],
                                  opinion_results: Dict,
                                  weather_data: Any = None) -> pd.DataFrame:
        """
        Сбор всех индикаторов для анализа
        
        Args:
            metrics: метрики города (СБ, ТФ, УБ, ЧВ)
            social_data: данные из соцсетей
            opinion_results: результаты opinion intelligence
            weather_data: данные погоды
            
        Returns:
            DataFrame со всеми индикаторами
        """
        indicators = {}
        
        # 1. Метрики города
        indicators['safety'] = metrics.get('СБ', 3.0) / 6.0
        indicators['economy'] = metrics.get('ТФ', 3.0) / 6.0
        indicators['quality'] = metrics.get('УБ', 3.0) / 6.0
        indicators['social_capital'] = metrics.get('ЧВ', 3.0) / 6.0
        
        # 2. Социальные индикаторы
        social_indicators = await self._extract_social_indicators(social_data)
        indicators.update(social_indicators)
        
        # 3. Индикаторы из opinion intelligence
        if opinion_results:
            opinion_indicators = self._extract_opinion_indicators(opinion_results)
            indicators.update(opinion_indicators)
        
        # 4. Погодные факторы
        if weather_data:
            weather_indicators = self._extract_weather_indicators(weather_data)
            indicators.update(weather_indicators)
        
        # 5. Временные факторы (сезонность, день недели)
        time_indicators = self._extract_time_indicators()
        indicators.update(time_indicators)
        
        # Добавляем временную метку
        indicators['timestamp'] = datetime.now()
        
        # Сохраняем историю
        self.historical_data['all'].append(indicators)
        
        # Ограничиваем историю (последние 365 дней)
        if len(self.historical_data['all']) > 365:
            self.historical_data['all'] = self.historical_data['all'][-365:]
        
        # Конвертируем в DataFrame
        df = pd.DataFrame([indicators])
        
        return df
    
    async def _extract_social_indicators(self, social_data: List[Dict]) -> Dict[str, float]:
        """Извлечение социальных индикаторов"""
        if not social_data:
            return {}
        
        # Данные за последние 24 часа
        cutoff = datetime.now() - timedelta(hours=24)
        recent_posts = []
        
        for post in social_data:
            post_date = post.get('date', datetime.now())
            if isinstance(post_date, str):
                post_date = datetime.fromisoformat(post_date)
            if post_date >= cutoff:
                recent_posts.append(post)
        
        if not recent_posts:
            return {}
        
        # Анализ тональности
        negative_count = 0
        positive_count = 0
        protest_mentions = 0
        radical_mentions = 0
        
        negative_keywords = ['плохо', 'ужасно', 'возмутительно', 'позор', 'безобразие']
        protest_keywords = ['митинг', 'протест', 'забастовка', 'бунт', 'революция']
        radical_keywords = ['свергнуть', 'насилие', 'оружие', 'убить', 'захватить']
        
        for post in recent_posts:
            text = post.get('text', '').lower()
            
            # Тональность
            if any(kw in text for kw in negative_keywords):
                negative_count += 1
            else:
                positive_count += 1
            
            # Протестные упоминания
            if any(kw in text for kw in protest_keywords):
                protest_mentions += 1
            
            # Радикальные упоминания
            if any(kw in text for kw in radical_keywords):
                radical_mentions += 1
        
        total = len(recent_posts)
        
        return {
            'social_negativity': negative_count / total if total > 0 else 0,
            'social_positivity': positive_count / total if total > 0 else 0,
            'protest_mentions': protest_mentions,
            'radical_mentions': radical_mentions,
            'social_volume': total
        }
    
    def _extract_opinion_indicators(self, opinion_results: Dict) -> Dict[str, float]:
        """Извлечение индикаторов из opinion intelligence"""
        indicators = {}
        
        # Лидеры мнений
        leaders = opinion_results.get('opinion_leaders', [])
        critical_leaders = sum(1 for l in leaders if l.get('risk_level') == 'critical')
        indicators['critical_leaders_count'] = critical_leaders
        indicators['leaders_negativity'] = sum(
            l.get('sentiment_towards_admin', 0) for l in leaders
        ) / len(leaders) if leaders else 0
        
        # Радикалы
        radicals = opinion_results.get('radical_users', [])
        critical_radicals = sum(1 for r in radicals if r.get('threat_level') == 'critical')
        indicators['critical_radicals_count'] = critical_radicals
        indicators['avg_radical_score'] = sum(
            r.get('radical_score', 0) for r in radicals
        ) / len(radicals) if radicals else 0
        
        # Нарративы
        narratives = opinion_results.get('narratives', [])
        negative_narratives = sum(1 for n in narratives if n.get('sentiment', 0) < -0.3)
        artificial_narratives = sum(1 for n in narratives if n.get('is_artificial', False))
        indicators['negative_narratives_ratio'] = negative_narratives / len(narratives) if narratives else 0
        indicators['artificial_narratives_count'] = artificial_narratives
        
        # Кампании
        campaigns = opinion_results.get('disinformation_campaigns', [])
        active_campaigns = len(campaigns)
        critical_campaigns = sum(1 for c in campaigns if c.get('threat_level') == 'critical')
        indicators['active_campaigns'] = active_campaigns
        indicators['critical_campaigns'] = critical_campaigns
        
        return indicators
    
    def _extract_weather_indicators(self, weather_data) -> Dict[str, float]:
        """Извлечение погодных индикаторов"""
        if not weather_data:
            return {}
        
        indicators = {}
        
        # Температура
        if hasattr(weather_data, 'temperature'):
            temp = weather_data.temperature
            indicators['temperature'] = temp
            
            # Экстремальные температуры
            if temp < -20:
                indicators['cold_stress'] = min(1.0, abs(temp + 20) / 20)
            elif temp > 30:
                indicators['heat_stress'] = min(1.0, (temp - 30) / 15)
            else:
                indicators['cold_stress'] = 0
                indicators['heat_stress'] = 0
        
        # Осадки
        if hasattr(weather_data, 'precipitation'):
            precip = weather_data.precipitation
            indicators['precipitation'] = precip
            indicators['heavy_rain_risk'] = min(1.0, precip / 50)
        
        # Ветер
        if hasattr(weather_data, 'wind_speed'):
            wind = weather_data.wind_speed
            indicators['wind_speed'] = wind
            indicators['storm_risk'] = min(1.0, wind / 30)
        
        return indicators
    
    def _extract_time_indicators(self) -> Dict[str, float]:
        """Извлечение временных индикаторов"""
        now = datetime.now()
        
        return {
            'day_of_week': now.weekday() / 6,  # 0-1, где 0 = понедельник
            'is_weekend': 1 if now.weekday() >= 5 else 0,
            'day_of_month': now.day / 31,
            'month': now.month / 12,
            'is_holiday': self._is_holiday(now),
            'season': self._get_season_factor(now)
        }
    
    def _is_holiday(self, date: datetime) -> float:
        """Проверка на праздничный день"""
        # Упрощённая версия — в реальности нужен календарь праздников
        holidays = ['01-01', '01-07', '02-23', '03-08', '05-01', '05-09', '06-12', '11-04']
        return 1 if date.strftime('%m-%d') in holidays else 0
    
    def _get_season_factor(self, date: datetime) -> float:
        """Сезонный фактор (0-1)"""
        month = date.month
        # Зима = 0, Весна = 0.33, Лето = 0.66, Осень = 1
        if month in [12, 1, 2]:
            return 0
        elif month in [3, 4, 5]:
            return 0.33
        elif month in [6, 7, 8]:
            return 0.66
        else:
            return 1.0
    
    # ==================== 2. АНАЛИЗ ТРЕНДОВ И АНОМАЛИЙ ====================
    
    async def analyze_trends(self, indicator_name: str, days: int = 30) -> Dict[str, Any]:
        """
        Анализ тренда индикатора за период
        """
        if indicator_name not in self.historical_data:
            return {'trend': 'insufficient_data', 'slope': 0, 'acceleration': 0}
        
        # Извлекаем историю
        history = self.historical_data[indicator_name][-days:] if indicator_name in self.historical_data else []
        
        if len(history) < 7:
            return {'trend': 'insufficient_data', 'slope': 0, 'acceleration': 0}
        
        # Создаём временной ряд
        values = [h[indicator_name] for h in history if indicator_name in h]
        
        if len(values) < 7:
            return {'trend': 'insufficient_data', 'slope': 0, 'acceleration': 0}
        
        # Вычисляем тренд (линейная регрессия)
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        
        # Нормализованный наклон (относительно среднего)
        mean_val = np.mean(values)
        normalized_slope = slope / mean_val if mean_val > 0 else slope
        
        # Ускорение (вторая производная)
        if len(values) >= 14:
            first_half = values[:len(values)//2]
            second_half = values[len(values)//2:]
            slope_first = np.polyfit(range(len(first_half)), first_half, 1)[0]
            slope_second = np.polyfit(range(len(second_half)), second_half, 1)[0]
            acceleration = slope_second - slope_first
        else:
            acceleration = 0
        
        # Определение направления тренда
        if normalized_slope > 0.05:
            trend = 'rising'
        elif normalized_slope < -0.05:
            trend = 'declining'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'slope': normalized_slope,
            'acceleration': acceleration,
            'current_value': values[-1] if values else 0,
            'mean_value': mean_val,
            'volatility': np.std(values) / mean_val if mean_val > 0 else 0
        }
    
    async def detect_anomalies(self, indicator_name: str) -> List[Dict[str, Any]]:
        """
        Обнаружение аномалий в индикаторе
        """
        if indicator_name not in self.historical_data:
            return []
        
        history = self.historical_data[indicator_name][-90:]  # последние 90 дней
        
        if len(history) < 30:
            return []
        
        values = [h[indicator_name] for h in history if indicator_name in h]
        
        if len(values) < 30:
            return []
        
        # Метод IQR для обнаружения выбросов
        q1 = np.percentile(values, 25)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        anomalies = []
        current_value = values[-1]
        
        if current_value < lower_bound or current_value > upper_bound:
            anomalies.append({
                'value': current_value,
                'lower_bound': lower_bound,
                'upper_bound': upper_bound,
                'severity': 'high' if current_value < q1 - 3 * iqr or current_value > q3 + 3 * iqr else 'medium',
                'direction': 'below' if current_value < lower_bound else 'above'
            })
        
        return anomalies
    
    # ==================== 3. МОДЕЛИ ПРОГНОЗИРОВАНИЯ ====================
    
    async def train_models(self):
        """
        Обучение моделей машинного обучения на исторических данных
        """
        if len(self.training_history) < 100:
            logger.warning(f"Недостаточно данных для обучения моделей. Нужно минимум 100 записей, есть {len(self.training_history)}")
            return
        
        logger.info("Начинаю обучение моделей прогнозирования...")
        
        # Подготовка данных
        df = pd.DataFrame(self.training_history)
        
        # Выбираем признаки для обучения
        feature_cols = [c for c in df.columns if c not in ['timestamp', 'target_crisis', 'target_days']]
        
        X = df[feature_cols].values
        y = df['target_crisis'].values if 'target_crisis' in df.columns else None
        
        if y is not None:
            # Нормализация
            self.scalers['crisis'] = StandardScaler()
            X_scaled = self.scalers['crisis'].fit_transform(X)
            
            # Обучение Random Forest
            self.models['crisis_rf'] = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            self.models['crisis_rf'].fit(X_scaled, y)
            
            # Оценка качества
            predictions = self.models['crisis_rf'].predict(X_scaled)
            mae = mean_absolute_error(y, predictions)
            logger.info(f"Модель Random Forest обучена. MAE: {mae:.3f}")
        
        # Обучение моделей для каждого типа кризиса
        crisis_types = [ct.value for ct in CrisisType]
        for crisis_type in crisis_types:
            target_col = f'crisis_{crisis_type}'
            if target_col in df.columns:
                y_type = df[target_col].values
                
                self.scalers[crisis_type] = StandardScaler()
                X_scaled = self.scalers[crisis_type].fit_transform(X)
                
                self.models[crisis_type] = RandomForestRegressor(
                    n_estimators=100,
                    max_depth=8,
                    random_state=42
                )
                self.models[crisis_type].fit(X_scaled, y_type)
                logger.info(f"Модель для {crisis_type} обучена")
        
        self.is_trained = True
        logger.info("Обучение моделей завершено")
    
    async def predict_with_ml(self, current_features: np.ndarray, crisis_type: str) -> float:
        """
        Прогнозирование с использованием ML-модели
        """
        if not self.is_trained or crisis_type not in self.models:
            return None
        
        try:
            scaler = self.scalers.get(crisis_type, self.scalers.get('crisis'))
            if scaler:
                features_scaled = scaler.transform(current_features.reshape(1, -1))
                prediction = self.models[crisis_type].predict(features_scaled)[0]
                return max(0, min(1, prediction))
        except Exception as e:
            logger.error(f"Ошибка ML-прогноза для {crisis_type}: {e}")
        
        return None
    
    async def predict_with_trend(self, indicator_name: str, horizon_days: int) -> float:
        """
        Прогнозирование на основе тренда
        """
        trend_data = await self.analyze_trends(indicator_name, days=min(horizon_days * 2, 60))
        
        if trend_data['trend'] == 'insufficient_data':
            return None
        
        current_value = trend_data['current_value']
        slope = trend_data['slope']
        
        # Экстраполяция
        predicted_value = current_value + slope * horizon_days
        
        # Ограничиваем значения
        predicted_value = max(0, min(1, predicted_value))
        
        return predicted_value
    
    async def predict_with_arima(self, indicator_name: str, horizon_days: int) -> Optional[float]:
        """
        Прогнозирование с использованием ARIMA (упрощённая версия)
        """
        # В реальной системе здесь должна быть полноценная ARIMA-модель
        # Для демо используем экспоненциальное сглаживание
        return await self.predict_with_trend(indicator_name, horizon_days)
    
    # ==================== 4. ОЦЕНКА РИСКОВ ПО ТИПАМ КРИЗИСОВ ====================
    
    async def assess_safety_crisis_risk(self, indicators: pd.DataFrame) -> Dict[str, Any]:
        """Оценка риска кризиса безопасности"""
        risk_score = 0
        triggers = []
        
        # Фактор 1: Уровень безопасности (СБ)
        safety_level = indicators['safety'].iloc[-1] if 'safety' in indicators else 0.5
        if safety_level < 0.4:
            risk_score += 0.3
            triggers.append(f"Критически низкий уровень безопасности ({safety_level:.2f})")
        elif safety_level < 0.5:
            risk_score += 0.15
            triggers.append(f"Низкий уровень безопасности ({safety_level:.2f})")
        
        # Фактор 2: Негатив в соцсетях
        social_negativity = indicators['social_negativity'].iloc[-1] if 'social_negativity' in indicators else 0
        if social_negativity > 0.7:
            risk_score += 0.25
            triggers.append(f"Высокий уровень негатива в соцсетях ({social_negativity:.0%})")
        elif social_negativity > 0.5:
            risk_score += 0.1
        
        # Фактор 3: Протестные упоминания
        protest_mentions = indicators['protest_mentions'].iloc[-1] if 'protest_mentions' in indicators else 0
        if protest_mentions > 50:
            risk_score += 0.25
            triggers.append(f"Массовые упоминания протестов ({protest_mentions})")
        elif protest_mentions > 20:
            risk_score += 0.1
        
        # Фактор 4: Погодные условия (экстремальная погода повышает риск)
        cold_stress = indicators.get('cold_stress', [0]).iloc[-1] if 'cold_stress' in indicators else 0
        heat_stress = indicators.get('heat_stress', [0]).iloc[-1] if 'heat_stress' in indicators else 0
        if cold_stress > 0.5 or heat_stress > 0.5:
            risk_score += 0.1
            triggers.append("Экстремальные погодные условия")
        
        # ML-прогноз, если модель обучена
        ml_risk = None
        if self.is_trained:
            features = indicators.iloc[-1].values
            ml_risk = await self.predict_with_ml(features, CrisisType.SAFETY.value)
            if ml_risk is not None:
                risk_score = risk_score * 0.6 + ml_risk * 0.4
        
        return {
            'risk_score': min(1.0, risk_score),
            'triggers': triggers,
            'ml_prediction': ml_risk
        }
    
    async def assess_social_crisis_risk(self, indicators: pd.DataFrame) -> Dict[str, Any]:
        """Оценка риска социального кризиса (протесты)"""
        risk_score = 0
        triggers = []
        
        # Фактор 1: Радикальная активность
        radical_mentions = indicators['radical_mentions'].iloc[-1] if 'radical_mentions' in indicators else 0
        critical_radicals = indicators['critical_radicals_count'].iloc[-1] if 'critical_radicals_count' in indicators else 0
        
        if radical_mentions > 30 or critical_radicals > 5:
            risk_score += 0.3
            triggers.append(f"Высокая радикальная активность ({radical_mentions} упоминаний, {critical_radicals} радикалов)")
        elif radical_mentions > 10:
            risk_score += 0.15
        
        # Фактор 2: Негативные нарративы
        negative_narratives = indicators['negative_narratives_ratio'].iloc[-1] if 'negative_narratives_ratio' in indicators else 0
        if negative_narratives > 0.6:
            risk_score += 0.25
            triggers.append(f"Доминирование негативных нарративов ({negative_narratives:.0%})")
        elif negative_narratives > 0.4:
            risk_score += 0.1
        
        # Фактор 3: Информационные кампании
        active_campaigns = indicators['active_campaigns'].iloc[-1] if 'active_campaigns' in indicators else 0
        if active_campaigns > 3:
            risk_score += 0.25
            triggers.append(f"Активные информационные кампании ({active_campaigns})")
        
        # Фактор 4: Социальный капитал (ЧВ)
        social_capital = indicators['social_capital'].iloc[-1] if 'social_capital' in indicators else 0.5
        if social_capital < 0.4:
            risk_score += 0.2
            triggers.append(f"Крайне низкий социальный капитал ({social_capital:.2f})")
        
        return {
            'risk_score': min(1.0, risk_score),
            'triggers': triggers
        }
    
    async def assess_economic_crisis_risk(self, indicators: pd.DataFrame) -> Dict[str, Any]:
        """Оценка риска экономического кризиса"""
        risk_score = 0
        triggers = []
        
        # Фактор 1: Уровень экономики (ТФ)
        economy_level = indicators['economy'].iloc[-1] if 'economy' in indicators else 0.5
        if economy_level < 0.35:
            risk_score += 0.4
            triggers.append(f"Критическое падение экономики ({economy_level:.2f})")
        elif economy_level < 0.45:
            risk_score += 0.2
            triggers.append(f"Экономическая рецессия ({economy_level:.2f})")
        
        # Фактор 2: Негатив по экономической тематике
        social_negativity = indicators['social_negativity'].iloc[-1] if 'social_negativity' in indicators else 0
        if social_negativity > 0.6:
            risk_score += 0.2
            triggers.append(f"Высокий негатив в соцсетях ({social_negativity:.0%})")
        
        # Фактор 3: Лидеры мнений с экономической критикой
        leaders_negativity = indicators['leaders_negativity'].iloc[-1] if 'leaders_negativity' in indicators else 0
        if leaders_negativity < -0.5:
            risk_score += 0.2
            triggers.append("Ключевые ЛОМ критикуют экономическую политику")
        
        return {
            'risk_score': min(1.0, risk_score),
            'triggers': triggers
        }
    
    async def assess_reputational_crisis_risk(self, indicators: pd.DataFrame) -> Dict[str, Any]:
        """Оценка риска репутационного кризиса"""
        risk_score = 0
        triggers = []
        
        # Фактор 1: Информационные кампании
        critical_campaigns = indicators['critical_campaigns'].iloc[-1] if 'critical_campaigns' in indicators else 0
        if critical_campaigns > 2:
            risk_score += 0.35
            triggers.append(f"Критические инфо-кампании ({critical_campaigns})")
        elif critical_campaigns > 0:
            risk_score += 0.15
        
        # Фактор 2: Искусственные нарративы
        artificial_narratives = indicators['artificial_narratives_count'].iloc[-1] if 'artificial_narratives_count' in indicators else 0
        if artificial_narratives > 3:
            risk_score += 0.25
            triggers.append(f"Множество искусственных нарративов ({artificial_narratives})")
        
        # Фактор 3: Критические лидеры мнений
        critical_leaders = indicators['critical_leaders_count'].iloc[-1] if 'critical_leaders_count' in indicators else 0
        if critical_leaders > 3:
            risk_score += 0.2
            triggers.append(f"Критически настроенные ЛОМ ({critical_leaders})")
        
        # Фактор 4: Социальный капитал
        social_capital = indicators['social_capital'].iloc[-1] if 'social_capital' in indicators else 0.5
        if social_capital < 0.35:
            risk_score += 0.2
            triggers.append("Низкий уровень доверия к администрации")
        
        return {
            'risk_score': min(1.0, risk_score),
            'triggers': triggers
        }
    
    async def assess_infrastructure_crisis_risk(self, indicators: pd.DataFrame) -> Dict[str, Any]:
        """Оценка риска инфраструктурного кризиса"""
        risk_score = 0
        triggers = []
        
        # Фактор 1: Качество жизни (УБ) как прокси для инфраструктуры
        quality_level = indicators['quality'].iloc[-1] if 'quality' in indicators else 0.5
        if quality_level < 0.35:
            risk_score += 0.3
            triggers.append(f"Низкое качество жизни ({quality_level:.2f})")
        
        # Фактор 2: Погодные условия
        heavy_rain = indicators.get('heavy_rain_risk', [0]).iloc[-1] if 'heavy_rain_risk' in indicators else 0
        storm = indicators.get('storm_risk', [0]).iloc[-1] if 'storm_risk' in indicators else 0
        
        if heavy_rain > 0.5:
            risk_score += 0.25
            triggers.append("Высокий риск подтоплений")
        if storm > 0.5:
            risk_score += 0.2
            triggers.append("Штормовой ветер")
        
        # Фактор 3: Объём жалоб (прокси через социальную активность)
        social_volume = indicators['social_volume'].iloc[-1] if 'social_volume' in indicators else 0
        if social_volume > 200:
            risk_score += 0.15
            triggers.append("Всплеск жалоб в соцсетях")
        
        return {
            'risk_score': min(1.0, risk_score),
            'triggers': triggers
        }
    
    # ==================== 5. ФОРМИРОВАНИЕ ПРОГНОЗОВ ====================
    
    async def generate_predictions(self, indicators: pd.DataFrame) -> List[CrisisPrediction]:
        """
        Генерация всех прогнозов кризисов
        """
        predictions = []
        
        # Оценка рисков по каждому типу
        risk_assessments = {
            CrisisType.SAFETY: await self.assess_safety_crisis_risk(indicators),
            CrisisType.SOCIAL: await self.assess_social_crisis_risk(indicators),
            CrisisType.ECONOMIC: await self.assess_economic_crisis_risk(indicators),
            CrisisType.REPUTATIONAL: await self.assess_reputational_crisis_risk(indicators),
            CrisisType.INFRASTRUCTURE: await self.assess_infrastructure_crisis_risk(indicators)
        }
        
        # Определяем уровни и временные горизонты
        for crisis_type, assessment in risk_assessments.items():
            risk_score = assessment['risk_score']
            
            if risk_score < 0.2:
                continue
            
            # Определяем уровень кризиса
            if risk_score >= 0.8:
                level = CrisisLevel.CRITICAL
                time_horizon = 2
                confidence = 0.85
            elif risk_score >= 0.6:
                level = CrisisLevel.HIGH
                time_horizon = 5
                confidence = 0.75
            elif risk_score >= 0.4:
                level = CrisisLevel.MEDIUM
                time_horizon = 14
                confidence = 0.65
            elif risk_score >= 0.25:
                level = CrisisLevel.LOW
                time_horizon = 30
                confidence = 0.55
            else:
                level = CrisisLevel.WATCH
                time_horizon = 60
                confidence = 0.45
            
            # Описания для разных типов кризисов
            descriptions = {
                CrisisType.SAFETY: "Рост преступности и падение уровня безопасности",
                CrisisType.SOCIAL: "Риск протестной активности и социальной напряжённости",
                CrisisType.ECONOMIC: "Экономическая рецессия, закрытие предприятий",
                CrisisType.REPUTATIONAL: "Информационная атака на администрацию города",
                CrisisType.INFRASTRUCTURE: "Аварии на инфраструктурных объектах"
            }
            
            # Рекомендации
            recommendations = {
                CrisisType.SAFETY: [
                    "Усилить патрулирование в проблемных районах",
                    "Установить дополнительные камеры видеонаблюдения",
                    "Провести встречи с жителями по безопасности"
                ],
                CrisisType.SOCIAL: [
                    "Организовать открытые встречи с активистами",
                    "Оперативно реагировать на жалобы жителей",
                    "Запустить позитивную информационную кампанию"
                ],
                CrisisType.ECONOMIC: [
                    "Провести встречу с предпринимателями",
                    "Рассмотреть налоговые льготы для МСП",
                    "Активизировать инвестиционную деятельность"
                ],
                CrisisType.REPUTATIONAL: [
                    "Подготовить официальное опровержение",
                    "Задействовать лояльных лидеров мнений",
                    "Усилить мониторинг соцсетей"
                ],
                CrisisType.INFRASTRUCTURE: [
                    "Провести внеплановые проверки инфраструктуры",
                    "Сформировать аварийные бригады",
                    "Оповестить жителей о возможных перебоях"
                ]
            }
            
            prediction = CrisisPrediction(
                id=f"crisis_{crisis_type.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                crisis_type=crisis_type,
                level=level,
                probability=risk_score,
                time_horizon_days=time_horizon,
                location="город в целом",
                description=descriptions.get(crisis_type, "Кризисная ситуация"),
                triggers=assessment['triggers'],
                indicators={
                    'risk_score': risk_score,
                    'ml_prediction': assessment.get('ml_prediction')
                },
                threshold=self.config.CRISIS_THRESHOLDS.get(crisis_type, {}).get('default', 0.5),
                trend='rising' if risk_score > 0.5 else 'stable',
                confidence=confidence,
                recommended_actions=recommendations.get(crisis_type, ["Провести дополнительный анализ"]),
                affected_vectors=self._get_affected_vectors(crisis_type),
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=time_horizon)
            )
            
            predictions.append(prediction)
            self.predictions[prediction.id] = prediction
        
        # Сортируем по вероятности
        predictions.sort(key=lambda x: x.probability, reverse=True)
        
        logger.info(f"Сгенерировано {len(predictions)} прогнозов кризисов")
        return predictions
    
    def _get_affected_vectors(self, crisis_type: CrisisType) -> List[str]:
        """Определение затронутых векторов Мейстера"""
        mapping = {
            CrisisType.SAFETY: ['СБ'],
            CrisisType.SOCIAL: ['ЧВ', 'СБ'],
            CrisisType.ECONOMIC: ['ТФ', 'УБ'],
            CrisisType.REPUTATIONAL: ['ЧВ'],
            CrisisType.INFRASTRUCTURE: ['УБ', 'СБ'],
            CrisisType.ECOLOGICAL: ['УБ'],
            CrisisType.HEALTH: ['УБ', 'СБ'],
            CrisisType.TRANSPORT: ['УБ', 'ТФ'],
            CrisisType.UTILITY: ['УБ']
        }
        return mapping.get(crisis_type, ['УБ'])
    
    # ==================== 6. РАННЕЕ ПРЕДУПРЕЖДЕНИЕ ====================
    
    async def check_early_warnings(self, predictions: List[CrisisPrediction]) -> List[EarlyWarning]:
        """
        Проверка на необходимость раннего предупреждения
        """
        warnings = []
        
        for pred in predictions:
            # Критический уровень или высокая вероятность
            if pred.level == CrisisLevel.CRITICAL or pred.probability > 0.85:
                severity = "critical"
                message = f"🚨 КРИТИЧЕСКОЕ ПРЕДУПРЕЖДЕНИЕ: {pred.description}. Вероятность {pred.probability:.0%}. Требуются немедленные действия."
            elif pred.level == CrisisLevel.HIGH or pred.probability > 0.7:
                severity = "alert"
                message = f"⚠️ ВАЖНОЕ ПРЕДУПРЕЖДЕНИЕ: {pred.description}. Вероятность {pred.probability:.0%}. Рекомендуется подготовить план действий."
            elif pred.level == CrisisLevel.MEDIUM and pred.probability > 0.5:
                severity = "warning"
                message = f"📢 ПРЕДУПРЕЖДЕНИЕ: {pred.description}. Вероятность {pred.probability:.0%}. Рекомендуется мониторинг ситуации."
            else:
                continue
            
            # Проверяем, не было ли уже такого предупреждения
            existing = [w for w in self.warnings if w.crisis_prediction_id == pred.id]
            if not existing:
                warning = EarlyWarning(
                    id=f"warn_{pred.id}",
                    crisis_prediction_id=pred.id,
                    severity=severity,
                    message=message,
                    timestamp=datetime.now()
                )
                warnings.append(warning)
                self.warnings.append(warning)
        
        return warnings
    
    # ==================== 7. ОСНОВНОЙ ЦИКЛ ПРОГНОЗИРОВАНИЯ ====================
    
    async def run_prediction_cycle(self,
                                    metrics: Dict[str, float],
                                    social_data: List[Dict],
                                    opinion_results: Dict,
                                    weather_data: Any = None) -> Dict[str, Any]:
        """
        Полный цикл прогнозирования кризисов
        """
        logger.info(f"Запуск цикла прогнозирования для города {self.city_name}")
        
        # 1. Сбор индикаторов
        indicators = await self.collect_indicators(metrics, social_data, opinion_results, weather_data)
        
        # 2. Сохраняем для обучения
        self.training_history.append(indicators.iloc[-1].to_dict())
        
        # 3. Периодическое обучение моделей
        if len(self.training_history) >= 30 and not self.is_trained:
            await self.train_models()
        
        # 4. Генерация прогнозов
        predictions = await self.generate_predictions(indicators)
        
        # 5. Проверка на ранние предупреждения
        warnings = await self.check_early_warnings(predictions)
        
        # 6. Обновление времени последнего прогноза
        self.last_prediction_time = datetime.now()
        
        # 7. Формирование результата
        result = {
            'city': self.city_name,
            'timestamp': datetime.now().isoformat(),
            'predictions': [
                {
                    'id': p.id,
                    'crisis_type': p.crisis_type.value,
                    'level': p.level.value,
                    'probability': p.probability,
                    'time_horizon_days': p.time_horizon_days,
                    'description': p.description,
                    'triggers': p.triggers[:5],
                    'recommended_actions': p.recommended_actions,
                    'confidence': p.confidence
                }
                for p in predictions
            ],
            'warnings': [
                {
                    'severity': w.severity,
                    'message': w.message,
                    'timestamp': w.timestamp.isoformat()
                }
                for w in warnings
            ],
            'summary': {
                'total_predictions': len(predictions),
                'critical_count': sum(1 for p in predictions if p.level == CrisisLevel.CRITICAL),
                'high_count': sum(1 for p in predictions if p.level == CrisisLevel.HIGH),
                'top_risk': predictions[0].crisis_type.value if predictions else None,
                'max_probability': max(p.probability for p in predictions) if predictions else 0
            }
        }
        
        logger.info(f"Прогнозирование завершено. Критических прогнозов: {result['summary']['critical_count']}")
        
        return result
    
    # ==================== 8. DASHBOARD И ОТЧЁТНОСТЬ ====================
    
    async def get_crisis_dashboard(self) -> Dict[str, Any]:
        """
        Получение дашборда кризисов для мэра
        """
        active_predictions = [
            p for p in self.predictions.values()
            if p.expires_at > datetime.now()
        ]
        
        # Группировка по уровню
        by_level = {
            'critical': [p for p in active_predictions if p.level == CrisisLevel.CRITICAL],
            'high': [p for p in active_predictions if p.level == CrisisLevel.HIGH],
            'medium': [p for p in active_predictions if p.level == CrisisLevel.MEDIUM],
            'low': [p for p in active_predictions if p.level == CrisisLevel.LOW]
        }
        
        # Неподтверждённые предупреждения
        unacknowledged_warnings = [w for w in self.warnings if not w.is_acknowledged]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'city': self.city_name,
            'active_crisis_predictions': len(active_predictions),
            'by_level': {
                level: len(predictions) for level, predictions in by_level.items()
            },
            'critical_predictions': [
                {
                    'type': p.crisis_type.value,
                    'probability': p.probability,
                    'time_horizon_hours': p.time_horizon_days * 24,
                    'description': p.description,
                    'actions': p.recommended_actions[:3]
                }
                for p in by_level['critical']
            ],
            'unacknowledged_warnings': len(unacknowledged_warnings),
            'warnings': [
                {
                    'severity': w.severity,
                    'message': w.message,
                    'timestamp': w.timestamp.isoformat()
                }
                for w in unacknowledged_warnings[:5]
            ],
            'trends': await self._get_crisis_trends(),
            'recommendations': self._get_global_recommendations(active_predictions)
        }
    
    async def _get_crisis_trends(self) -> Dict[str, Any]:
        """Анализ трендов кризисов"""
        if len(self.historical_data['all']) < 7:
            return {'overall_trend': 'insufficient_data'}
        
        # Берём последние 7 дней
        recent = self.historical_data['all'][-7:]
        older = self.historical_data['all'][-14:-7] if len(self.historical_data['all']) >= 14 else []
        
        if not older:
            return {'overall_trend': 'stable'}
        
        # Средний риск за последнюю неделю
        recent_risk = np.mean([self._calculate_risk_from_indicators(r) for r in recent])
        older_risk = np.mean([self._calculate_risk_from_indicators(o) for o in older])
        
        change = recent_risk - older_risk
        
        if change > 0.1:
            trend = 'deteriorating'
        elif change < -0.1:
            trend = 'improving'
        else:
            trend = 'stable'
        
        return {
            'overall_trend': trend,
            'risk_change': change,
            'current_risk_level': recent_risk
        }
    
    def _calculate_risk_from_indicators(self, indicators: Dict) -> float:
        """Расчёт общего риска из индикаторов"""
        # Упрощённая формула
        risk = 0
        risk += indicators.get('safety', 0.5) * 0.25
        risk += indicators.get('social_negativity', 0) * 0.25
        risk += (1 - indicators.get('social_capital', 0.5)) * 0.25
        risk += indicators.get('critical_campaigns', 0) * 0.25
        return min(1.0, risk)
    
    def _get_global_recommendations(self, predictions: List[CrisisPrediction]) -> List[str]:
        """Глобальные рекомендации на основе всех прогнозов"""
        recommendations = []
        
        # Проверяем наличие критических прогнозов
        critical = [p for p in predictions if p.level == CrisisLevel.CRITICAL]
        if critical:
            recommendations.append("🚨 КРИТИЧЕСКАЯ СИТУАЦИЯ: Немедленно созвать оперативный штаб")
            recommendations.append(f"🎯 Приоритет: {critical[0].crisis_type.value} — {critical[0].recommended_actions[0]}")
        
        # Проверяем экономические риски
        economic = [p for p in predictions if p.crisis_type == CrisisType.ECONOMIC and p.level in [CrisisLevel.HIGH, CrisisLevel.CRITICAL]]
        if economic:
            recommendations.append("💰 ЭКОНОМИЧЕСКИЙ РИСК: Провести встречу с бизнес-сообществом")
        
        # Проверяем репутационные риски
        reputational = [p for p in predictions if p.crisis_type == CrisisType.REPUTATIONAL and p.probability > 0.6]
        if reputational:
            recommendations.append("📢 РЕПУТАЦИОННЫЙ РИСК: Усилить информационную работу")
        
        if not recommendations:
            recommendations.append("✅ Критических рисков не выявлено. Продолжать мониторинг.")
        
        return recommendations
    
    # ==================== 9. ПОДТВЕРЖДЕНИЕ ПРЕДУПРЕЖДЕНИЙ ====================
    
    async def acknowledge_warning(self, warning_id: str, acknowledged_by: str) -> bool:
        """
        Подтверждение предупреждения (мэр ознакомился)
        """
        for warning in self.warnings:
            if warning.id == warning_id:
                warning.is_acknowledged = True
                warning.acknowledged_by = acknowledged_by
                warning.acknowledged_at = datetime.now()
                logger.info(f"Предупреждение {warning_id} подтверждено пользователем {acknowledged_by}")
                return True
        
        return False


# ==================== ИНТЕГРАЦИЯ С ОСНОВНЫМ ПРИЛОЖЕНИЕМ ====================

async def create_crisis_predictor(city_name: str) -> CrisisPredictor:
    """Фабричная функция для создания предиктора кризисов"""
    return CrisisPredictor(city_name)


# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("🧪 Тестирование CrisisPredictor...")
        
        # Создаём предиктор
        predictor = CrisisPredictor("Коломна")
        
        # Симулируем данные
        test_metrics = {'СБ': 3.2, 'ТФ': 3.8, 'УБ': 4.2, 'ЧВ': 3.5}
        
        test_social_data = [
            {
                'id': '1',
                'text': 'Ужасные дороги, ничего не делают! Пора выходить на митинг!',
                'date': datetime.now() - timedelta(hours=1)
            },
            {
                'id': '2',
                'text': 'Криминал растёт, страшно гулять вечером',
                'date': datetime.now() - timedelta(hours=2)
            }
        ]
        
        test_opinion = {
            'opinion_leaders': [
                {'risk_level': 'critical', 'sentiment_towards_admin': -0.8}
            ],
            'radical_users': [
                {'threat_level': 'critical', 'radical_score': 0.9}
            ],
            'narratives': [
                {'sentiment': -0.7, 'is_artificial': True}
            ],
            'disinformation_campaigns': [
                {'threat_level': 'high'}
            ]
        }
        
        # Запускаем цикл прогнозирования
        result = await predictor.run_prediction_cycle(
            metrics=test_metrics,
            social_data=test_social_data,
            opinion_results=test_opinion
        )
        
        print(f"\n📊 РЕЗУЛЬТАТЫ ПРОГНОЗИРОВАНИЯ:")
        print(f"  Всего прогнозов: {result['summary']['total_predictions']}")
        print(f"  Критических: {result['summary']['critical_count']}")
        print(f"  Высоких: {result['summary']['high_count']}")
        print(f"  Главный риск: {result['summary']['top_risk']}")
        
        if result['predictions']:
            print(f"\n🔮 ПРОГНОЗЫ:")
            for p in result['predictions'][:3]:
                print(f"  • {p['crisis_type']}: {p['probability']:.0%} через {p['time_horizon_days']} дней")
                if p['triggers']:
                    print(f"    Триггеры: {', '.join(p['triggers'][:2])}")
        
        if result['warnings']:
            print(f"\n⚠️ ПРЕДУПРЕЖДЕНИЯ:")
            for w in result['warnings']:
                print(f"  [{w['severity'].upper()}] {w['message'][:100]}...")
        
        # Дашборд
        dashboard = await predictor.get_crisis_dashboard()
        print(f"\n📊 ДАШБОРД КРИЗИСОВ:")
        print(f"  Активных прогнозов: {dashboard['active_crisis_predictions']}")
        print(f"  Неподтверждённых предупреждений: {dashboard['unacknowledged_warnings']}")
        
        print("\n✅ Тест завершен")
    
    asyncio.run(demo())
