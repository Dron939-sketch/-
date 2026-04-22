#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 12: ПУЛЬС ГОРОДА (City Pulse)
Система мониторинга "температуры" города в реальном времени

Основан на методах:
- Агрегация данных из 50+ источников в реальном времени
- Интегральные индексы состояния города
- Тепловые карты проблем по районам
- Индикаторы раннего предупреждения
- Трендовый анализ и аномалии
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
from math import sin, cos, sqrt, atan2, radians

logger = logging.getLogger(__name__)


# ==================== МОДЕЛИ ДАННЫХ ====================

class PulseLevel(Enum):
    """Уровень пульса города"""
    CRITICAL = "critical"    # 80-100° — критический, требуется немедленное вмешательство
    HIGH = "high"            # 60-79° — высокий, требуется внимание
    ELEVATED = "elevated"    # 40-59° — повышенный, мониторинг
    NORMAL = "normal"        # 20-39° — нормальный
    LOW = "low"              # 0-19° — спокойный


class AlertType(Enum):
    """Типы оповещений"""
    SAFETY = "safety"           # Безопасность
    SOCIAL = "social"           # Социальная напряжённость
    INFRASTRUCTURE = "infra"    # Инфраструктура
    ECOLOGY = "ecology"         # Экология
    HEALTH = "health"           # Здравоохранение
    TRANSPORT = "transport"     # Транспорт
    UTILITY = "utility"         # Коммунальные услуги
    REPUTATION = "reputation"   # Репутационные риски


@dataclass
class DistrictPulse:
    """Пульс района"""
    district_name: str
    temperature: float           # 0-100°
    level: PulseLevel
    main_problems: List[str]     # главные проблемы района
    metrics: Dict[str, float]    # метрики района
    trend: str                   # rising/stable/declining
    last_update: datetime


@dataclass
class CityPulse:
    """Пульс города в целом"""
    timestamp: datetime
    overall_temperature: float    # 0-100°
    level: PulseLevel
    districts: List[DistrictPulse]
    hotspots: List[Dict]          # горячие точки
    indicators: Dict[str, float]  # ключевые индикаторы
    trend: str
    alerts: List[Dict]


@dataclass
class Alert:
    """Оповещение о проблеме"""
    id: str
    type: AlertType
    severity: str                 # warning/alert/critical
    location: str                 # район или адрес
    title: str
    description: str
    timestamp: datetime
    metrics: Dict[str, float]
    recommended_action: str
    is_acknowledged: bool = False
    resolved_at: Optional[datetime] = None


# ==================== КОНФИГУРАЦИЯ ====================

class CityPulseConfig:
    """Конфигурация пульса города"""
    
    # Веса для расчёта температуры
    TEMPERATURE_WEIGHTS = {
        'safety': 0.25,
        'social': 0.25,
        'infrastructure': 0.20,
        'ecology': 0.10,
        'economy': 0.10,
        'reputation': 0.10
    }
    
    # Пороги температуры
    TEMPERATURE_THRESHOLDS = {
        PulseLevel.CRITICAL: 80,
        PulseLevel.HIGH: 60,
        PulseLevel.ELEVATED: 40,
        PulseLevel.NORMAL: 20,
        PulseLevel.LOW: 0
    }
    
    # Время жизни оповещений (часы)
    ALERT_LIFETIME_HOURS = 48
    
    # Частота обновления пульса (минуты)
    UPDATE_INTERVAL_MINUTES = 15
    
    # Районы Коломны (для демо)
    DISTRICTS = [
        "Центральный", "Запрудня", "Голутвин", "Колычёво",
        "Щурово", "Малаховка", "Пески", "Станкостроитель"
    ]


# ==================== ОСНОВНОЙ КЛАСС ====================

class CityPulseMonitor:
    """
    Пульс города — мониторинг "температуры" в реальном времени
    
    Позволяет мэру:
    - Видеть текущее состояние города (0-100°)
    - Отслеживать тренды и аномалии
    - Получать оповещения о проблемах
    - Смотреть тепловую карту по районам
    """
    
    def __init__(self, city_name: str, config: CityPulseConfig = None):
        self.city_name = city_name
        self.config = config or CityPulseConfig()
        
        # Текущие данные
        self.current_pulse: Optional[CityPulse] = None
        self.alerts: List[Alert] = []
        self.history: List[CityPulse] = []
        
        # Данные по районам
        self.district_data: Dict[str, Dict] = {}
        
        # Кэш для быстрого доступа
        self.cache = {}
        
        # Фоновые задачи
        self.is_running = False
        self.update_task = None
        
        logger.info(f"CityPulseMonitor инициализирован для города {city_name}")
    
    # ==================== 1. СБОР ДАННЫХ ====================
    
    async def collect_district_data(self) -> Dict[str, Dict]:
        """
        Сбор данных по районам города
        В реальной системе — интеграция с датчиками, соцсетями, обращениями
        """
        district_data = {}
        
        # Симуляция данных для каждого района
        # В реальности здесь будут API датчиков, анализ соцсетей и т.д.
        
        for district in self.config.DISTRICTS:
            # Генерируем реалистичные данные
            district_data[district] = {
                'safety': np.random.uniform(2.0, 5.0),      # уровень безопасности
                'social_negativity': np.random.uniform(0.1, 0.8),  # негатив в соцсетях
                'infrastructure': np.random.uniform(2.0, 5.0),      # состояние инфраструктуры
                'ecology': np.random.uniform(3.0, 5.0),             # экология
                'economy': np.random.uniform(2.5, 4.5),             # экономика
                'complaints_count': np.random.randint(0, 50),       # количество жалоб
                'incidents_count': np.random.randint(0, 10),        # происшествия
                'last_update': datetime.now()
            }
        
        self.district_data = district_data
        return district_data
    
    async def collect_indicators(self) -> Dict[str, float]:
        """
        Сбор ключевых индикаторов города
        """
        indicators = {}
        
        # Безопасность
        safety_values = [d['safety'] for d in self.district_data.values()]
        indicators['safety'] = np.mean(safety_values) / 6.0 * 100
        
        # Социальная напряжённость (негатив в соцсетях)
        social_values = [d['social_negativity'] for d in self.district_data.values()]
        indicators['social'] = np.mean(social_values) * 100
        
        # Инфраструктура
        infra_values = [d['infrastructure'] for d in self.district_data.values()]
        indicators['infrastructure'] = np.mean(infra_values) / 6.0 * 100
        
        # Экология
        eco_values = [d['ecology'] for d in self.district_data.values()]
        indicators['ecology'] = np.mean(eco_values) / 6.0 * 100
        
        # Экономика
        economy_values = [d['economy'] for d in self.district_data.values()]
        indicators['economy'] = np.mean(economy_values) / 6.0 * 100
        
        # Жалобы (нормализованные)
        complaints = [d['complaints_count'] for d in self.district_data.values()]
        indicators['complaints_normalized'] = min(100, np.mean(complaints) / 50 * 100)
        
        # Происшествия
        incidents = [d['incidents_count'] for d in self.district_data.values()]
        indicators['incidents_normalized'] = min(100, np.mean(incidents) / 20 * 100)
        
        # Репутационный индекс (обратный к негативу)
        indicators['reputation'] = 100 - indicators['social']
        
        return indicators
    
    async def detect_hotspots(self, indicators: Dict[str, float]) -> List[Dict]:
        """
        Обнаружение горячих точек — районов с критическими показателями
        """
        hotspots = []
        
        for district, data in self.district_data.items():
            # Вычисляем "температуру" района
            district_temp = self._calculate_district_temperature(data)
            
            if district_temp >= self.config.TEMPERATURE_THRESHOLDS[PulseLevel.HIGH]:
                # Определяем главную проблему
                main_issue = self._identify_main_issue(data)
                
                hotspots.append({
                    'district': district,
                    'temperature': district_temp,
                    'level': self._get_pulse_level(district_temp).value,
                    'main_issue': main_issue,
                    'metrics': data
                })
        
        # Сортируем по температуре
        hotspots.sort(key=lambda x: x['temperature'], reverse=True)
        
        return hotspots
    
    def _calculate_district_temperature(self, district_data: Dict) -> float:
        """Расчёт температуры района"""
        weights = self.config.TEMPERATURE_WEIGHTS
        
        # Нормализуем показатели
        safety_score = (6.0 - district_data['safety']) / 6.0 * 100
        social_score = district_data['social_negativity'] * 100
        infra_score = (6.0 - district_data['infrastructure']) / 6.0 * 100
        ecology_score = (6.0 - district_data['ecology']) / 6.0 * 100
        economy_score = (6.0 - district_data['economy']) / 6.0 * 100
        
        # Жалобы и происшествия увеличивают температуру
        complaints_factor = min(30, district_data['complaints_count'] / 50 * 30)
        incidents_factor = min(40, district_data['incidents_count'] / 10 * 40)
        
        # Взвешенная сумма
        temperature = (
            safety_score * weights.get('safety', 0.25) +
            social_score * weights.get('social', 0.25) +
            infra_score * weights.get('infrastructure', 0.20) +
            ecology_score * weights.get('ecology', 0.10) +
            economy_score * weights.get('economy', 0.10) +
            complaints_factor * 0.05 +
            incidents_factor * 0.05
        )
        
        return min(100, max(0, temperature))
    
    def _identify_main_issue(self, district_data: Dict) -> str:
        """Определение главной проблемы района"""
        issues = []
        
        if district_data['safety'] < 3.0:
            issues.append(('безопасность', 3.0 - district_data['safety']))
        if district_data['social_negativity'] > 0.6:
            issues.append(('социальная напряжённость', district_data['social_negativity']))
        if district_data['infrastructure'] < 3.0:
            issues.append(('инфраструктура', 3.0 - district_data['infrastructure']))
        if district_data['ecology'] < 3.0:
            issues.append(('экология', 3.0 - district_data['ecology']))
        if district_data['economy'] < 3.0:
            issues.append(('экономика', 3.0 - district_data['economy']))
        
        if not issues:
            return "нет критических проблем"
        
        # Возвращаем проблему с максимальным отклонением
        return max(issues, key=lambda x: x[1])[0]
    
    # ==================== 2. РАСЧЁТ ПУЛЬСА ====================
    
    async def calculate_pulse(self) -> CityPulse:
        """
        Расчёт пульса города на основе собранных данных
        """
        # 1. Собираем данные по районам
        await self.collect_district_data()
        
        # 2. Собираем индикаторы
        indicators = await self.collect_indicators()
        
        # 3. Вычисляем общую температуру
        overall_temperature = self._calculate_overall_temperature(indicators)
        
        # 4. Определяем уровень
        level = self._get_pulse_level(overall_temperature)
        
        # 5. Создаём пульс районов
        districts_pulse = []
        for district, data in self.district_data.items():
            district_temp = self._calculate_district_temperature(data)
            district_level = self._get_pulse_level(district_temp)
            
            # Определяем главные проблемы района
            main_problems = self._get_district_problems(data)
            
            # Тренд (упрощённо — сравнение с предыдущим значением)
            trend = self._get_district_trend(district, district_temp)
            
            districts_pulse.append(DistrictPulse(
                district_name=district,
                temperature=district_temp,
                level=district_level,
                main_problems=main_problems,
                metrics=data,
                trend=trend,
                last_update=datetime.now()
            ))
        
        # 6. Обнаруживаем горячие точки
        hotspots = await self.detect_hotspots(indicators)
        
        # 7. Определяем общий тренд
        trend = self._get_overall_trend(overall_temperature)
        
        # 8. Формируем оповещения
        alerts = await self._generate_alerts(indicators, hotspots)
        
        pulse = CityPulse(
            timestamp=datetime.now(),
            overall_temperature=overall_temperature,
            level=level,
            districts=districts_pulse,
            hotspots=hotspots,
            indicators=indicators,
            trend=trend,
            alerts=alerts
        )
        
        # Сохраняем в историю
        self.current_pulse = pulse
        self.history.append(pulse)
        
        # Ограничиваем историю (последние 30 дней)
        if len(self.history) > 2880:  # 15 минут * 2880 = 30 дней
            self.history = self.history[-2880:]
        
        logger.info(f"Пульс города рассчитан: {overall_temperature:.1f}° ({level.value})")
        
        return pulse
    
    def _calculate_overall_temperature(self, indicators: Dict[str, float]) -> float:
        """Расчёт общей температуры города"""
        weights = self.config.TEMPERATURE_WEIGHTS
        
        temperature = (
            indicators.get('safety', 50) * weights.get('safety', 0.25) +
            indicators.get('social', 50) * weights.get('social', 0.25) +
            indicators.get('infrastructure', 50) * weights.get('infrastructure', 0.20) +
            indicators.get('ecology', 50) * weights.get('ecology', 0.10) +
            indicators.get('economy', 50) * weights.get('economy', 0.10) +
            (100 - indicators.get('reputation', 50)) * weights.get('reputation', 0.10)
        )
        
        return min(100, max(0, temperature))
    
    def _get_pulse_level(self, temperature: float) -> PulseLevel:
        """Определение уровня пульса по температуре"""
        thresholds = self.config.TEMPERATURE_THRESHOLDS
        
        for level, threshold in sorted(thresholds.items(), key=lambda x: x[1], reverse=True):
            if temperature >= threshold:
                return level
        
        return PulseLevel.LOW
    
    def _get_district_problems(self, district_data: Dict) -> List[str]:
        """Получение списка проблем района"""
        problems = []
        
        if district_data['safety'] < 3.0:
            problems.append(f"Низкая безопасность ({district_data['safety']:.1f}/6)")
        if district_data['social_negativity'] > 0.6:
            problems.append(f"Высокая социальная напряжённость")
        if district_data['infrastructure'] < 3.0:
            problems.append(f"Плохая инфраструктура ({district_data['infrastructure']:.1f}/6)")
        if district_data['complaints_count'] > 30:
            problems.append(f"Много жалоб ({district_data['complaints_count']} шт)")
        if district_data['incidents_count'] > 5:
            problems.append(f"Происшествия ({district_data['incidents_count']} шт)")
        
        return problems[:3]  # топ-3 проблем
    
    def _get_district_trend(self, district: str, current_temp: float) -> str:
        """Определение тренда района"""
        if not self.history:
            return 'stable'
        
        # Ищем предыдущее значение
        prev_pulse = None
        for pulse in reversed(self.history):
            for d in pulse.districts:
                if d.district_name == district:
                    prev_pulse = d
                    break
            if prev_pulse:
                break
        
        if not prev_pulse:
            return 'stable'
        
        change = current_temp - prev_pulse.temperature
        
        if change > 5:
            return 'rising'
        elif change < -5:
            return 'declining'
        else:
            return 'stable'
    
    def _get_overall_trend(self, current_temp: float) -> str:
        """Определение общего тренда города"""
        if len(self.history) < 2:
            return 'stable'
        
        prev_temp = self.history[-1].overall_temperature
        change = current_temp - prev_temp
        
        if change > 3:
            return 'rising'
        elif change < -3:
            return 'declining'
        else:
            return 'stable'
    
    # ==================== 3. ГЕНЕРАЦИЯ ОПОВЕЩЕНИЙ ====================
    
    async def _generate_alerts(self, indicators: Dict[str, float], hotspots: List[Dict]) -> List[Dict]:
        """
        Генерация оповещений на основе текущего пульса
        """
        alerts = []
        
        # 1. Проверка критических индикаторов
        if indicators.get('safety', 100) < 30:
            alerts.append({
                'type': AlertType.SAFETY.value,
                'severity': 'critical',
                'title': 'Критическое падение безопасности',
                'description': f"Уровень безопасности упал до {indicators['safety']:.1f}°",
                'recommended_action': 'Немедленно усилить патрулирование'
            })
        
        if indicators.get('social', 100) > 70:
            alerts.append({
                'type': AlertType.SOCIAL.value,
                'severity': 'critical' if indicators['social'] > 85 else 'alert',
                'title': 'Высокий уровень социальной напряжённости',
                'description': f"Негатив в соцсетях достиг {indicators['social']:.1f}%",
                'recommended_action': 'Провести встречи с активистами'
            })
        
        if indicators.get('infrastructure', 100) < 40:
            alerts.append({
                'type': AlertType.INFRASTRUCTURE.value,
                'severity': 'alert',
                'title': 'Проблемы с инфраструктурой',
                'description': f"Состояние инфраструктуры оценено в {indicators['infrastructure']:.1f}°",
                'recommended_action': 'Провести внеплановые проверки'
            })
        
        # 2. Проверка горячих точек
        for hotspot in hotspots[:3]:  # топ-3 горячих точки
            if hotspot['level'] == 'critical':
                alerts.append({
                    'type': AlertType.SAFETY.value,
                    'severity': 'critical',
                    'title': f"Критическая ситуация в районе {hotspot['district']}",
                    'description': f"Температура района: {hotspot['temperature']:.1f}°. Основная проблема: {hotspot['main_issue']}",
                    'location': hotspot['district'],
                    'recommended_action': f'Направить комиссию в район {hotspot["district"]}'
                })
        
        # 3. Добавляем оповещения в систему
        new_alerts = []
        for alert_data in alerts:
            alert = Alert(
                id=f"alert_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hashlib.md5(alert_data['title'].encode()).hexdigest()[:4]}",
                type=AlertType(alert_data['type']),
                severity=alert_data['severity'],
                location=alert_data.get('location', 'город в целом'),
                title=alert_data['title'],
                description=alert_data['description'],
                timestamp=datetime.now(),
                metrics=indicators,
                recommended_action=alert_data['recommended_action']
            )
            new_alerts.append(alert)
            self.alerts.append(alert)
        
        # Очищаем старые оповещения
        self._cleanup_old_alerts()
        
        return [self._alert_to_dict(a) for a in new_alerts]
    
    def _cleanup_old_alerts(self):
        """Очистка старых оповещений"""
        cutoff = datetime.now() - timedelta(hours=self.config.ALERT_LIFETIME_HOURS)
        self.alerts = [a for a in self.alerts if a.timestamp > cutoff or a.is_acknowledged]
    
    def _alert_to_dict(self, alert: Alert) -> Dict:
        """Конвертация оповещения в словарь"""
        return {
            'id': alert.id,
            'type': alert.type.value,
            'severity': alert.severity,
            'location': alert.location,
            'title': alert.title,
            'description': alert.description,
            'timestamp': alert.timestamp.isoformat(),
            'recommended_action': alert.recommended_action,
            'is_acknowledged': alert.is_acknowledged
        }
    
    # ==================== 4. ВИЗУАЛИЗАЦИЯ ====================
    
    def get_thermal_map_data(self) -> Dict[str, Any]:
        """
        Получение данных для тепловой карты города
        """
        if not self.current_pulse:
            return {'error': 'No pulse data available'}
        
        thermal_data = []
        
        for district in self.current_pulse.districts:
            # Координаты районов (в реальности — из геоданных)
            coords = self._get_district_coordinates(district.district_name)
            
            thermal_data.append({
                'district': district.district_name,
                'temperature': district.temperature,
                'level': district.level.value,
                'coordinates': coords,
                'problems': district.main_problems,
                'metrics': district.metrics
            })
        
        return {
            'city': self.city_name,
            'timestamp': self.current_pulse.timestamp.isoformat(),
            'overall_temperature': self.current_pulse.overall_temperature,
            'overall_level': self.current_pulse.level.value,
            'thermal_data': thermal_data,
            'hotspots': self.current_pulse.hotspots
        }
    
    def _get_district_coordinates(self, district: str) -> Dict[str, float]:
        """
        Получение координат района (центр района)
        В реальности — из геоинформационной системы
        """
        # Координаты районов Коломны (приблизительные)
        coordinates = {
            "Центральный": {"lat": 55.1025, "lon": 38.7531},
            "Запрудня": {"lat": 55.0950, "lon": 38.7400},
            "Голутвин": {"lat": 55.0880, "lon": 38.7650},
            "Колычёво": {"lat": 55.1150, "lon": 38.7300},
            "Щурово": {"lat": 55.0800, "lon": 38.7900},
            "Малаховка": {"lat": 55.1100, "lon": 38.7700},
            "Пески": {"lat": 55.0980, "lon": 38.7450},
            "Станкостроитель": {"lat": 55.1050, "lon": 38.7600}
        }
        return coordinates.get(district, {"lat": 55.1025, "lon": 38.7531})
    
    def get_trend_chart_data(self, days: int = 7) -> Dict[str, Any]:
        """
        Получение данных для графика трендов
        """
        if not self.history:
            return {'error': 'No history data available'}
        
        # Берём данные за указанное количество дней
        # 1 день = 96 записей (15-минутные интервалы)
        points_per_day = 96
        required_points = days * points_per_day
        
        recent_history = self.history[-required_points:] if len(self.history) >= required_points else self.history
        
        timeline = []
        temperatures = []
        safety_series = []
        social_series = []
        infra_series = []
        
        for pulse in recent_history:
            timeline.append(pulse.timestamp.isoformat())
            temperatures.append(pulse.overall_temperature)
            safety_series.append(pulse.indicators.get('safety', 50))
            social_series.append(pulse.indicators.get('social', 50))
            infra_series.append(pulse.indicators.get('infrastructure', 50))
        
        return {
            'timeline': timeline,
            'temperatures': temperatures,
            'safety': safety_series,
            'social': social_series,
            'infrastructure': infra_series,
            'days': days
        }
    
    # ==================== 5. ДАШБОРД И ОПОВЕЩЕНИЯ ====================
    
    async def get_pulse_dashboard(self) -> Dict[str, Any]:
        """
        Получение полного дашборда пульса города
        """
        if not self.current_pulse or (datetime.now() - self.current_pulse.timestamp).seconds > 900:
            # Данные устарели, обновляем
            await self.calculate_pulse()
        
        # Неподтверждённые оповещения
        unacknowledged_alerts = [self._alert_to_dict(a) for a in self.alerts if not a.is_acknowledged]
        
        # Статистика
        stats = self._get_pulse_statistics()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'city': self.city_name,
            'current_pulse': {
                'temperature': self.current_pulse.overall_temperature,
                'level': self.current_pulse.level.value,
                'trend': self.current_pulse.trend,
                'color': self._get_temperature_color(self.current_pulse.overall_temperature)
            },
            'districts': [
                {
                    'name': d.district_name,
                    'temperature': d.temperature,
                    'level': d.level.value,
                    'main_problems': d.main_problems,
                    'trend': d.trend
                }
                for d in self.current_pulse.districts
            ],
            'hotspots': self.current_pulse.hotspots[:5],
            'alerts': unacknowledged_alerts[:10],
            'statistics': stats,
            'trend_data': self.get_trend_chart_data(7),
            'thermal_map': self.get_thermal_map_data()
        }
    
    def _get_temperature_color(self, temperature: float) -> str:
        """Цвет температуры для дашборда"""
        if temperature >= 80:
            return '#DC3545'  # красный
        elif temperature >= 60:
            return '#FD7E14'  # оранжевый
        elif temperature >= 40:
            return '#FFC107'  # жёлтый
        elif temperature >= 20:
            return '#28A745'  # зелёный
        else:
            return '#20C997'  # бирюзовый
    
    def _get_pulse_statistics(self) -> Dict[str, Any]:
        """Статистика пульса"""
        if not self.history:
            return {}
        
        # Данные за последние 24 часа
        day_ago = datetime.now() - timedelta(days=1)
        day_history = [p for p in self.history if p.timestamp > day_ago]
        
        if not day_history:
            return {}
        
        avg_temperature = np.mean([p.overall_temperature for p in day_history])
        max_temperature = max([p.overall_temperature for p in day_history])
        min_temperature = min([p.overall_temperature for p in day_history])
        
        # Время в критической зоне
        critical_time = sum(1 for p in day_history if p.overall_temperature >= 80)
        critical_percent = critical_time / len(day_history) * 100
        
        return {
            'avg_temperature': round(avg_temperature, 1),
            'max_temperature': round(max_temperature, 1),
            'min_temperature': round(min_temperature, 1),
            'critical_time_percent': round(critical_percent, 1),
            'data_points': len(day_history)
        }
    
    # ==================== 6. УПРАВЛЕНИЕ ОПОВЕЩЕНИЯМИ ====================
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """
        Подтверждение оповещения (мэр ознакомился)
        """
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.is_acknowledged = True
                logger.info(f"Оповещение {alert_id} подтверждено пользователем {acknowledged_by}")
                return True
        
        return False
    
    async def resolve_alert(self, alert_id: str, resolution: str) -> bool:
        """
        Закрытие оповещения после решения проблемы
        """
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved_at = datetime.now()
                logger.info(f"Оповещение {alert_id} закрыто. Решение: {resolution}")
                return True
        
        return False
    
    # ==================== 7. ФОНОВЫЙ МОНИТОРИНГ ====================
    
    async def start_monitoring(self, interval_minutes: int = None):
        """
        Запуск фонового мониторинга с регулярным обновлением пульса
        """
        interval = interval_minutes or self.config.UPDATE_INTERVAL_MINUTES
        
        self.is_running = True
        logger.info(f"Запуск фонового мониторинга с интервалом {interval} минут")
        
        while self.is_running:
            try:
                await self.calculate_pulse()
                
                # Проверяем критические оповещения для немедленного уведомления
                critical_alerts = [a for a in self.alerts if a.severity == 'critical' and not a.is_acknowledged]
                
                if critical_alerts:
                    logger.warning(f"КРИТИЧЕСКИЕ ОПОВЕЩЕНИЯ: {len(critical_alerts)}")
                    for alert in critical_alerts:
                        logger.warning(f"  - {alert.title}: {alert.description}")
                
            except Exception as e:
                logger.error(f"Ошибка при обновлении пульса: {e}")
            
            await asyncio.sleep(interval * 60)
    
    async def stop_monitoring(self):
        """Остановка фонового мониторинга"""
        self.is_running = False
        logger.info("Фоновый мониторинг остановлен")
    
    # ==================== 8. ЭКСПОРТ ОТЧЁТОВ ====================
    
    async def export_pulse_report(self, hours: int = 24) -> Dict[str, Any]:
        """
        Экспорт отчёта по пульсу города
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        relevant_history = [p for p in self.history if p.timestamp > cutoff]
        
        if not relevant_history:
            return {'error': 'No data for specified period'}
        
        # Агрегируем данные
        avg_temp = np.mean([p.overall_temperature for p in relevant_history])
        max_temp = max([p.overall_temperature for p in relevant_history])
        min_temp = min([p.overall_temperature for p in relevant_history])
        
        # Время на разных уровнях
        level_distribution = defaultdict(int)
        for pulse in relevant_history:
            level_distribution[pulse.level.value] += 1
        
        # Самые проблемные районы
        district_issues = defaultdict(list)
        for pulse in relevant_history:
            for district in pulse.districts:
                if district.temperature >= 60:
                    district_issues[district.district_name].append({
                        'temperature': district.temperature,
                        'problems': district.main_problems,
                        'timestamp': pulse.timestamp.isoformat()
                    })
        
        # Топ районов по проблемам
        top_districts = sorted(
            [(name, len(issues)) for name, issues in district_issues.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return {
            'report_id': f"pulse_report_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'period_hours': hours,
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'average_temperature': round(avg_temp, 1),
                'maximum_temperature': round(max_temp, 1),
                'minimum_temperature': round(min_temp, 1),
                'critical_hours': level_distribution.get('critical', 0),
                'total_data_points': len(relevant_history)
            },
            'level_distribution': dict(level_distribution),
            'problem_districts': [
                {'district': name, 'incidents_count': count}
                for name, count in top_districts
            ],
            'alerts_generated': len([a for a in self.alerts if a.timestamp > cutoff]),
            'trend': self._get_overall_trend(avg_temp)
        }


# ==================== ИНТЕГРАЦИЯ С ОСНОВНЫМ ПРИЛОЖЕНИЕМ ====================

async def create_city_pulse_monitor(city_name: str) -> CityPulseMonitor:
    """Фабричная функция для создания монитора пульса города"""
    return CityPulseMonitor(city_name)


# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("🧪 Тестирование CityPulseMonitor...")
        
        # Создаём монитор
        monitor = CityPulseMonitor("Коломна")
        
        # 1. Расчёт пульса
        pulse = await monitor.calculate_pulse()
        
        print(f"\n🌡️ ПУЛЬС ГОРОДА:")
        print(f"  Температура: {pulse.overall_temperature:.1f}°")
        print(f"  Уровень: {pulse.level.value}")
        print(f"  Тренд: {pulse.trend}")
        
        # 2. Районы
        print(f"\n🏘️ РАЙОНЫ:")
        for district in pulse.districts[:4]:
            print(f"  {district.district_name}: {district.temperature:.1f}° ({district.level.value})")
            if district.main_problems:
                print(f"    Проблемы: {', '.join(district.main_problems)}")
        
        # 3. Горячие точки
        if pulse.hotspots:
            print(f"\n🔥 ГОРЯЧИЕ ТОЧКИ:")
            for hotspot in pulse.hotspots[:3]:
                print(f"  {hotspot['district']}: {hotspot['temperature']:.1f}° — {hotspot['main_issue']}")
        
        # 4. Оповещения
        if pulse.alerts:
            print(f"\n⚠️ ОПОВЕЩЕНИЯ:")
            for alert in pulse.alerts:
                print(f"  [{alert['severity'].upper()}] {alert['title']}")
                print(f"    {alert['description'][:80]}...")
        
        # 5. Дашборд
        dashboard = await monitor.get_pulse_dashboard()
        print(f"\n📊 ДАШБОРД ПУЛЬСА:")
        print(f"  Текущая температура: {dashboard['current_pulse']['temperature']:.1f}°")
        print(f"  Статус: {dashboard['current_pulse']['level']}")
        print(f"  Активных оповещений: {len(dashboard['alerts'])}")
        
        # 6. Тепловая карта
        thermal = monitor.get_thermal_map_data()
        print(f"\n🗺️ ТЕПЛОВАЯ КАРТА:")
        print(f"  Горячих точек: {len(thermal['thermal_data'])}")
        
        # 7. Экспорт отчёта
        report = await monitor.export_pulse_report(hours=24)
        print(f"\n📄 ОТЧЁТ ЗА 24 ЧАСА:")
        print(f"  Средняя температура: {report['summary']['average_temperature']:.1f}°")
        print(f"  Часов в критической зоне: {report['summary']['critical_hours']}")
        
        print("\n✅ Тест завершен")
    
    asyncio.run(demo())
