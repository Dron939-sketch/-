#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 15: СРАВНЕНИЕ С ГОРОДАМИ (City Benchmark)
Система бенчмаркинга и сравнения с городами-аналогами

Основан на методах:
- Многомерное сравнение городов по 50+ метрикам
- Кластеризация городов-аналогов
- Анализ лучших практик
- Рейтингование и позиционирование
- Рекомендации по заимствованию успешных решений
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
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


# ==================== МОДЕЛИ ДАННЫХ ====================

class CityCategory(Enum):
    """Категории городов по размеру"""
    MILLIONAIRE = "millionaire"      # > 1 млн
    LARGE = "large"                   # 500k - 1 млн
    MEDIUM = "medium"                 # 100k - 500k
    SMALL = "small"                   # 50k - 100k
    TOWN = "town"                     # < 50k


@dataclass
class CityProfile:
    """Профиль города для сравнения"""
    id: str
    name: str
    region: str
    category: CityCategory
    population: int
    area_sq_km: float
    
    # Основные метрики
    metrics: Dict[str, float]          # СБ, ТФ, УБ, ЧВ
    sub_metrics: Dict[str, float]      # детальные метрики
    
    # Бюджетные показатели
    budget_million_rub: float
    budget_per_capita: float
    
    # Социальные показатели
    trust_index: float                 # 0-1
    happiness_index: float             # 0-1
    unemployment_rate: float
    
    # Инфраструктура
    road_quality: float                # 0-1
    public_transport_score: float      # 0-1
    green_zones_per_capita: float
    
    # Лучшие практики
    best_practices: List[Dict]
    last_update: datetime


@dataclass
class BenchmarkComparison:
    """Результат сравнения с городом"""
    city_name: str
    overall_score: float               # 0-1
    rank: int
    category: CityCategory
    
    # Сравнение по векторам
    vector_comparison: Dict[str, Dict]  # {vector: {current, benchmark, gap}}
    
    # Детальное сравнение
    strengths: List[str]               # где город лучше
    weaknesses: List[str]              # где город хуже
    opportunities: List[str]           # возможности для улучшения
    
    # Лучшие практики для заимствования
    recommended_practices: List[Dict]
    similar_cities: List[str]


# ==================== КОНФИГУРАЦИЯ ====================

class BenchmarkConfig:
    """Конфигурация системы бенчмаркинга"""
    
    # База данных городов (в реальности — из БД)
    CITIES_DATABASE = {
        "Коломна": {
            "region": "Московская область",
            "population": 144589,
            "area_sq_km": 65,
            "budget_million_rub": 5800,
            "metrics": {"СБ": 3.8, "ТФ": 3.5, "УБ": 4.2, "ЧВ": 3.2},
            "trust_index": 0.52,
            "happiness_index": 0.61,
            "unemployment_rate": 3.8,
            "road_quality": 0.55,
            "public_transport_score": 0.48,
            "green_zones_per_capita": 0.012
        },
        "Серпухов": {
            "region": "Московская область",
            "population": 125000,
            "area_sq_km": 56,
            "budget_million_rub": 5200,
            "metrics": {"СБ": 4.0, "ТФ": 3.8, "УБ": 4.0, "ЧВ": 3.5},
            "trust_index": 0.58,
            "happiness_index": 0.63,
            "unemployment_rate": 3.5,
            "road_quality": 0.58,
            "public_transport_score": 0.52,
            "green_zones_per_capita": 0.014
        },
        "Подольск": {
            "region": "Московская область",
            "population": 312000,
            "area_sq_km": 40,
            "budget_million_rub": 15000,
            "metrics": {"СБ": 4.2, "ТФ": 4.0, "УБ": 4.3, "ЧВ": 3.8},
            "trust_index": 0.62,
            "happiness_index": 0.67,
            "unemployment_rate": 3.2,
            "road_quality": 0.62,
            "public_transport_score": 0.58,
            "green_zones_per_capita": 0.010
        },
        "Воскресенск": {
            "region": "Московская область",
            "population": 95000,
            "area_sq_km": 44,
            "budget_million_rub": 3800,
            "metrics": {"СБ": 3.5, "ТФ": 3.2, "УБ": 3.8, "ЧВ": 3.0},
            "trust_index": 0.45,
            "happiness_index": 0.52,
            "unemployment_rate": 4.5,
            "road_quality": 0.45,
            "public_transport_score": 0.40,
            "green_zones_per_capita": 0.008
        },
        "Егорьевск": {
            "region": "Московская область",
            "population": 85000,
            "area_sq_km": 38,
            "budget_million_rub": 3500,
            "metrics": {"СБ": 3.6, "ТФ": 3.3, "УБ": 3.9, "ЧВ": 3.1},
            "trust_index": 0.48,
            "happiness_index": 0.55,
            "unemployment_rate": 4.2,
            "road_quality": 0.48,
            "public_transport_score": 0.42,
            "green_zones_per_capita": 0.009
        },
        "Зарайск": {
            "region": "Московская область",
            "population": 42000,
            "area_sq_km": 20,
            "budget_million_rub": 1800,
            "metrics": {"СБ": 4.1, "ТФ": 3.4, "УБ": 4.1, "ЧВ": 3.4},
            "trust_index": 0.55,
            "happiness_index": 0.60,
            "unemployment_rate": 3.9,
            "road_quality": 0.52,
            "public_transport_score": 0.45,
            "green_zones_per_capita": 0.018
        },
        "Озёры": {
            "region": "Московская область",
            "population": 25000,
            "area_sq_km": 12,
            "budget_million_rub": 1200,
            "metrics": {"СБ": 3.9, "ТФ": 3.1, "УБ": 3.8, "ЧВ": 3.3},
            "trust_index": 0.50,
            "happiness_index": 0.56,
            "unemployment_rate": 4.0,
            "road_quality": 0.46,
            "public_transport_score": 0.38,
            "green_zones_per_capita": 0.020
        },
        "Кашира": {
            "region": "Московская область",
            "population": 58000,
            "area_sq_km": 25,
            "budget_million_rub": 2200,
            "metrics": {"СБ": 3.7, "ТФ": 3.2, "УБ": 3.7, "ЧВ": 3.1},
            "trust_index": 0.47,
            "happiness_index": 0.54,
            "unemployment_rate": 4.3,
            "road_quality": 0.44,
            "public_transport_score": 0.39,
            "green_zones_per_capita": 0.011
        }
    }
    
    # Лучшие практики по городам
    BEST_PRACTICES = {
        "Серпухов": [
            {
                "title": "Программа 'Соседский дозор'",
                "description": "Вовлечение жителей в обеспечение безопасности",
                "impact": "Снижение преступности на 30% за 2 года",
                "cost": "Низкий",
                "difficulty": "Низкая",
                "vector": "СБ"
            },
            {
                "title": "Инвестиционный портал",
                "description": "Единая платформа для инвесторов",
                "impact": "Привлечено 15 инвесторов за год",
                "cost": "Средний",
                "difficulty": "Средняя",
                "vector": "ТФ"
            }
        ],
        "Подольск": [
            {
                "title": "Цифровизация госуслуг",
                "description": "Перевод 90% услуг в электронный вид",
                "impact": "Время ожидания сократилось на 70%",
                "cost": "Высокий",
                "difficulty": "Высокая",
                "vector": "ЧВ"
            },
            {
                "title": "Бюджетирование с участием граждан",
                "description": "Жители выбирают проекты для благоустройства",
                "impact": "Рост доверия на 25%",
                "cost": "Низкий",
                "difficulty": "Средняя",
                "vector": "ЧВ"
            }
        ],
        "Зарайск": [
            {
                "title": "Туристический кластер",
                "description": "Развитие исторического центра",
                "impact": "Рост туристического потока на 40%",
                "cost": "Средний",
                "difficulty": "Средняя",
                "vector": "УБ"
            }
        ],
        "Коломна": [
            {
                "title": "Фестиваль 'Ледовая Коломна'",
                "description": "Ежегодный фестиваль ледовых скульптур",
                "impact": "Привлечение туристов, развитие культуры",
                "cost": "Низкий",
                "difficulty": "Низкая",
                "vector": "ЧВ"
            }
        ]
    }


# ==================== ОСНОВНОЙ КЛАСС ====================

class CityBenchmark:
    """
    Система сравнения городов и бенчмаркинга
    
    Позволяет мэру:
    - Сравнить свой город с аналогами
    - Увидеть сильные и слабые стороны
    - Заимствовать успешные практики
    - Отслеживать позицию в рейтинге
    """
    
    def __init__(self, city_name: str, config: BenchmarkConfig = None):
        self.city_name = city_name
        self.config = config or BenchmarkConfig()
        
        # Данные городов
        self.cities_data = self.config.CITIES_DATABASE.copy()
        self.best_practices = self.config.BEST_PRACTICES
        
        # Текущий профиль города
        self.current_profile: Optional[CityProfile] = None
        
        # Кэш для сравнений
        self.comparison_cache = {}
        
        # Статистика
        self.benchmark_history = []
        
        logger.info(f"CityBenchmark инициализирован для города {city_name}")
    
    # ==================== 1. ЗАГРУЗКА И ОБНОВЛЕНИЕ ДАННЫХ ====================
    
    async def load_city_profile(self, city_name: str = None) -> CityProfile:
        """
        Загрузка профиля города
        """
        target_city = city_name or self.city_name
        
        if target_city not in self.cities_data:
            logger.warning(f"Город {target_city} не найден в базе")
            return None
        
        data = self.cities_data[target_city]
        
        # Определяем категорию по населению
        population = data['population']
        if population >= 1000000:
            category = CityCategory.MILLIONAIRE
        elif population >= 500000:
            category = CityCategory.LARGE
        elif population >= 100000:
            category = CityCategory.MEDIUM
        elif population >= 50000:
            category = CityCategory.SMALL
        else:
            category = CityCategory.TOWN
        
        profile = CityProfile(
            id=target_city,
            name=target_city,
            region=data['region'],
            category=category,
            population=population,
            area_sq_km=data['area_sq_km'],
            metrics=data['metrics'],
            sub_metrics={},
            budget_million_rub=data['budget_million_rub'],
            budget_per_capita=data['budget_million_rub'] / population * 1000,
            trust_index=data['trust_index'],
            happiness_index=data['happiness_index'],
            unemployment_rate=data['unemployment_rate'],
            road_quality=data['road_quality'],
            public_transport_score=data['public_transport_score'],
            green_zones_per_capita=data['green_zones_per_capita'],
            best_practices=self.best_practices.get(target_city, []),
            last_update=datetime.now()
        )
        
        if target_city == self.city_name:
            self.current_profile = profile
        
        return profile
    
    async def update_city_metrics(self, metrics: Dict[str, float]) -> bool:
        """
        Обновление метрик текущего города
        """
        if self.current_profile:
            self.current_profile.metrics = metrics
            self.current_profile.last_update = datetime.now()
            
            # Обновляем в базе
            if self.city_name in self.cities_data:
                self.cities_data[self.city_name]['metrics'] = metrics
            
            logger.info(f"Обновлены метрики для {self.city_name}: {metrics}")
            return True
        
        return False
    
    # ==================== 2. ПОИСК ГОРОДОВ-АНАЛОГОВ ====================
    
    async def find_similar_cities(self, n_clusters: int = 5) -> List[str]:
        """
        Поиск городов-аналогов на основе кластеризации
        """
        if not self.current_profile:
            await self.load_city_profile()
        
        # Подготовка данных для кластеризации
        features = []
        city_names = []
        
        for city_name, data in self.cities_data.items():
            if city_name == self.city_name:
                continue
            
            features.append([
                data['population'] / 100000,  # нормализованное население
                data['budget_per_capita'] if 'budget_per_capita' in data else data['budget_million_rub'] / data['population'] * 1000,
                data['metrics']['СБ'],
                data['metrics']['ТФ'],
                data['metrics']['УБ'],
                data['metrics']['ЧВ'],
                data['unemployment_rate'],
                data['road_quality'],
                data['trust_index']
            ])
            city_names.append(city_name)
        
        if len(features) < 3:
            return city_names[:5]  # возвращаем все, если мало данных
        
        # Нормализация и кластеризация
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)
        
        kmeans = KMeans(n_clusters=min(n_clusters, len(features)), random_state=42, n_init=10)
        clusters = kmeans.fit_predict(features_scaled)
        
        # Находим кластер текущего города
        current_features = [
            self.current_profile.population / 100000,
            self.current_profile.budget_per_capita,
            self.current_profile.metrics['СБ'],
            self.current_profile.metrics['ТФ'],
            self.current_profile.metrics['УБ'],
            self.current_profile.metrics['ЧВ'],
            self.current_profile.unemployment_rate,
            self.current_profile.road_quality,
            self.current_profile.trust_index
        ]
        current_scaled = scaler.transform([current_features])
        current_cluster = kmeans.predict(current_scaled)[0]
        
        # Города из того же кластера
        similar = [city_names[i] for i, c in enumerate(clusters) if c == current_cluster]
        
        # Добавляем ближайшие по косинусной близости
        similarities = cosine_similarity(current_scaled, features_scaled)[0]
        sorted_indices = np.argsort(similarities)[::-1]
        
        for idx in sorted_indices:
            city = city_names[idx]
            if city not in similar and len(similar) < 10:
                similar.append(city)
        
        logger.info(f"Найдено {len(similar)} городов-аналогов для {self.city_name}")
        return similar[:10]
    
    # ==================== 3. СРАВНЕНИЕ С ГОРОДОМ ====================
    
    async def compare_with_city(self, target_city: str) -> BenchmarkComparison:
        """
        Сравнение текущего города с указанным
        """
        if not self.current_profile:
            await self.load_city_profile()
        
        target_profile = await self.load_city_profile(target_city)
        if not target_profile:
            return None
        
        cache_key = f"{self.city_name}_{target_city}"
        if cache_key in self.comparison_cache:
            return self.comparison_cache[cache_key]
        
        # 1. Сравнение по векторам
        vector_comparison = {}
        strengths = []
        weaknesses = []
        
        for vector in ['СБ', 'ТФ', 'УБ', 'ЧВ']:
            current_val = self.current_profile.metrics.get(vector, 3.0)
            benchmark_val = target_profile.metrics.get(vector, 3.0)
            gap = current_val - benchmark_val
            
            vector_comparison[vector] = {
                'current': current_val,
                'benchmark': benchmark_val,
                'gap': gap,
                'is_better': gap > 0,
                'percent': (current_val / benchmark_val - 1) * 100 if benchmark_val > 0 else 0
            }
            
            if gap > 0.3:
                strengths.append(f"{vector} выше на {gap:.1f} балла (чем в {target_city})")
            elif gap < -0.3:
                weaknesses.append(f"{vector} ниже на {abs(gap):.1f} балла (чем в {target_city})")
        
        # 2. Сравнение дополнительных метрик
        additional_metrics = [
            ('Доверие к власти', self.current_profile.trust_index, target_profile.trust_index),
            ('Индекс счастья', self.current_profile.happiness_index, target_profile.happiness_index),
            ('Качество дорог', self.current_profile.road_quality, target_profile.road_quality),
            ('Транспорт', self.current_profile.public_transport_score, target_profile.public_transport_score)
        ]
        
        for name, current, benchmark in additional_metrics:
            if current > benchmark + 0.05:
                strengths.append(f"{name} выше на {(current - benchmark) * 100:.0f}%")
            elif current < benchmark - 0.05:
                weaknesses.append(f"{name} ниже на {(benchmark - current) * 100:.0f}%")
        
        # 3. Возможности для улучшения (на основе лучших практик)
        opportunities = []
        for practice in target_profile.best_practices:
            vector = practice.get('vector')
            if vector and self.current_profile.metrics.get(vector, 3.0) < 4.0:
                opportunities.append(f"Внедрить '{practice['title']}' как в {target_city}")
        
        # 4. Рекомендуемые практики
        recommended_practices = []
        for practice in target_profile.best_practices:
            vector = practice.get('vector')
            if vector and self.current_profile.metrics.get(vector, 3.0) < target_profile.metrics.get(vector, 3.0):
                recommended_practices.append(practice)
        
        # 5. Общая оценка
        total_current = sum(self.current_profile.metrics.values())
        total_benchmark = sum(target_profile.metrics.values())
        overall_score = total_current / total_benchmark if total_benchmark > 0 else 1.0
        overall_score = min(1.0, max(0.5, overall_score))
        
        # 6. Ранг (упрощённо)
        all_scores = []
        for city in self.cities_data:
            city_metrics = self.cities_data[city]['metrics']
            all_scores.append(sum(city_metrics.values()))
        all_scores.sort(reverse=True)
        current_total = sum(self.current_profile.metrics.values())
        rank = all_scores.index(current_total) + 1 if current_total in all_scores else len(all_scores)
        
        comparison = BenchmarkComparison(
            city_name=target_city,
            overall_score=overall_score,
            rank=rank,
            category=target_profile.category,
            vector_comparison=vector_comparison,
            strengths=strengths[:5],
            weaknesses=weaknesses[:5],
            opportunities=opportunities[:5],
            recommended_practices=recommended_practices,
            similar_cities=await self.find_similar_cities()
        )
        
        self.comparison_cache[cache_key] = comparison
        return comparison
    
    # ==================== 4. ПОЛНЫЙ БЕНЧМАРКИНГ ====================
    
    async def run_full_benchmark(self) -> Dict[str, Any]:
        """
        Запуск полного бенчмаркинга со всеми городами-аналогами
        """
        if not self.current_profile:
            await self.load_city_profile()
        
        # Находим города-аналоги
        similar_cities = await self.find_similar_cities()
        
        # Сравниваем с каждым
        comparisons = []
        for city in similar_cities:
            comp = await self.compare_with_city(city)
            if comp:
                comparisons.append(comp)
        
        # Сортируем по общей оценке
        comparisons.sort(key=lambda x: x.overall_score, reverse=True)
        
        # Вычисляем средние показатели по аналогам
        avg_metrics = {'СБ': 0, 'ТФ': 0, 'УБ': 0, 'ЧВ': 0}
        for city in similar_cities:
            profile = await self.load_city_profile(city)
            if profile:
                for v in avg_metrics:
                    avg_metrics[v] += profile.metrics.get(v, 3.0)
        
        for v in avg_metrics:
            avg_metrics[v] /= len(similar_cities) if similar_cities else 1
        
        # Агрегируем лучшие практики со всех городов
        all_practices = []
        for city in similar_cities:
            practices = self.best_practices.get(city, [])
            for p in practices:
                all_practices.append({
                    'city': city,
                    'practice': p
                })
        
        # Формируем отчёт
        result = {
            'city': self.city_name,
            'timestamp': datetime.now().isoformat(),
            'category': self.current_profile.category.value,
            'population': self.current_profile.population,
            'similar_cities_count': len(similar_cities),
            'ranking': {
                'position': comparisons[0].rank if comparisons else 1,
                'total_cities': len(self.cities_data),
                'score': comparisons[0].overall_score if comparisons else 0.5
            },
            'vs_average': {
                'metrics': {
                    v: {
                        'current': self.current_profile.metrics.get(v, 3.0),
                        'average': avg_metrics[v],
                        'gap': self.current_profile.metrics.get(v, 3.0) - avg_metrics[v]
                    }
                    for v in avg_metrics
                },
                'trust': {
                    'current': self.current_profile.trust_index,
                    'average': sum(await self._get_avg_metric('trust_index', similar_cities)),
                    'gap': self.current_profile.trust_index - sum(await self._get_avg_metric('trust_index', similar_cities))
                },
                'happiness': {
                    'current': self.current_profile.happiness_index,
                    'average': sum(await self._get_avg_metric('happiness_index', similar_cities)),
                    'gap': self.current_profile.happiness_index - sum(await self._get_avg_metric('happiness_index', similar_cities))
                }
            },
            'strengths': [],
            'weaknesses': [],
            'opportunities': [],
            'best_practices_to_adopt': [],
            'comparisons': [
                {
                    'city': c.city_name,
                    'overall_score': c.overall_score,
                    'best_in': [v for v, data in c.vector_comparison.items() if data['is_better']]
                }
                for c in comparisons[:5]
            ]
        }
        
        # Собираем strengths, weaknesses, opportunities из всех сравнений
        for comp in comparisons:
            result['strengths'].extend(comp.strengths)
            result['weaknesses'].extend(comp.weaknesses)
            result['opportunities'].extend(comp.opportunities)
        
        # Дедупликация
        result['strengths'] = list(set(result['strengths']))[:10]
        result['weaknesses'] = list(set(result['weaknesses']))[:10]
        result['opportunities'] = list(set(result['opportunities']))[:10]
        
        # Лучшие практики для заимствования
        practice_scores = {}
        for item in all_practices:
            p = item['practice']
            key = p['title']
            if key not in practice_scores:
                practice_scores[key] = {
                    'practice': p,
                    'cities': [],
                    'count': 0
                }
            practice_scores[key]['cities'].append(item['city'])
            practice_scores[key]['count'] += 1
        
        # Сортируем по популярности
        sorted_practices = sorted(practice_scores.values(), key=lambda x: x['count'], reverse=True)
        
        result['best_practices_to_adopt'] = [
            {
                'title': p['practice']['title'],
                'description': p['practice']['description'],
                'impact': p['practice']['impact'],
                'cost': p['practice']['cost'],
                'difficulty': p['practice']['difficulty'],
                'implemented_in': p['cities']
            }
            for p in sorted_practices[:10]
        ]
        
        # Сохраняем в историю
        self.benchmark_history.append({
            'timestamp': datetime.now(),
            'result': result
        })
        
        logger.info(f"Бенчмаркинг завершён для {self.city_name}")
        return result
    
    async def _get_avg_metric(self, metric_name: str, cities: List[str]) -> float:
        """Получение среднего значения метрики по городам"""
        total = 0
        count = 0
        for city in cities:
            profile = await self.load_city_profile(city)
            if profile:
                value = getattr(profile, metric_name, 0)
                total += value
                count += 1
        return total / count if count > 0 else 0
    
    # ==================== 5. РЕЙТИНГ ГОРОДОВ ====================
    
    async def get_ranking(self, metric: str = "overall") -> List[Dict]:
        """
        Получение рейтинга городов по указанной метрике
        """
        rankings = []
        
        for city_name, data in self.cities_data.items():
            if metric == "overall":
                score = sum(data['metrics'].values()) / 4
            elif metric in data['metrics']:
                score = data['metrics'][metric]
            elif metric == "trust":
                score = data.get('trust_index', 0)
            elif metric == "happiness":
                score = data.get('happiness_index', 0)
            elif metric == "economy":
                score = data.get('budget_per_capita', data['budget_million_rub'] / data['population'] * 1000)
            else:
                score = 0
            
            rankings.append({
                'city': city_name,
                'score': score,
                'population': data['population'],
                'region': data['region']
            })
        
        # Сортировка
        rankings.sort(key=lambda x: x['score'], reverse=True)
        
        # Добавляем позицию
        for i, r in enumerate(rankings):
            r['position'] = i + 1
            if r['city'] == self.city_name:
                r['is_current'] = True
        
        return rankings
    
    # ==================== 6. ДАШБОРД БЕНЧМАРКИНГА ====================
    
    async def get_benchmark_dashboard(self) -> Dict[str, Any]:
        """
        Получение дашборда бенчмаркинга для мэра
        """
        if not self.current_profile:
            await self.load_city_profile()
        
        # Последний бенчмаркинг
        latest_benchmark = self.benchmark_history[-1]['result'] if self.benchmark_history else None
        
        if not latest_benchmark:
            latest_benchmark = await self.run_full_benchmark()
        
        # Рейтинги
        overall_ranking = await self.get_ranking("overall")
        safety_ranking = await self.get_ranking("СБ")
        economy_ranking = await self.get_ranking("ТФ")
        
        # Позиция города
        current_position = next((r for r in overall_ranking if r['city'] == self.city_name), None)
        
        # Лучшие города для заимствования
        best_by_vector = {}
        for vector in ['СБ', 'ТФ', 'УБ', 'ЧВ']:
            ranking = await self.get_ranking(vector)
            best_by_vector[vector] = ranking[0] if ranking else None
        
        return {
            'timestamp': datetime.now().isoformat(),
            'city': self.city_name,
            'current_position': current_position,
            'total_cities': len(self.cities_data),
            'ranking_by_vector': {
                'safety': {
                    'position': next((r['position'] for r in safety_ranking if r['city'] == self.city_name), 0),
                    'total': len(safety_ranking),
                    'leader': safety_ranking[0]['city'] if safety_ranking else None,
                    'leader_score': safety_ranking[0]['score'] if safety_ranking else 0
                },
                'economy': {
                    'position': next((r['position'] for r in economy_ranking if r['city'] == self.city_name), 0),
                    'total': len(economy_ranking),
                    'leader': economy_ranking[0]['city'] if economy_ranking else None,
                    'leader_score': economy_ranking[0]['score'] if economy_ranking else 0
                }
            },
            'vs_similar_cities': {
                'better_than': sum(1 for c in latest_benchmark['comparisons'] if c['overall_score'] < 1),
                'worse_than': sum(1 for c in latest_benchmark['comparisons'] if c['overall_score'] > 1),
                'average_score': sum(c['overall_score'] for c in latest_benchmark['comparisons']) / len(latest_benchmark['comparisons']) if latest_benchmark['comparisons'] else 0
            },
            'top_strengths': latest_benchmark['strengths'][:3],
            'top_weaknesses': latest_benchmark['weaknesses'][:3],
            'top_opportunities': latest_benchmark['opportunities'][:3],
            'recommended_practices': latest_benchmark['best_practices_to_adopt'][:5],
            'best_practices_by_vector': best_by_vector
        }
    
    # ==================== 7. ЭКСПОРТ ОТЧЁТА ====================
    
    async def export_benchmark_report(self) -> Dict[str, Any]:
        """
        Экспорт отчёта по бенчмаркингу
        """
        benchmark = await self.run_full_benchmark()
        
        return {
            'report_id': f"benchmark_{self.city_name}_{datetime.now().strftime('%Y%m%d')}",
            'generated_at': datetime.now().isoformat(),
            'city': self.city_name,
            'benchmark': benchmark,
            'recommendations': self._generate_benchmark_recommendations(benchmark)
        }
    
    def _generate_benchmark_recommendations(self, benchmark: Dict) -> List[str]:
        """
        Генерация рекомендаций на основе бенчмаркинга
        """
        recommendations = []
        
        # Рекомендации по слабым местам
        if benchmark['weaknesses']:
            recommendations.append(f"🎯 Приоритетное направление для улучшения: {benchmark['weaknesses'][0][:50]}")
        
        # Рекомендации по лучшим практикам
        if benchmark['best_practices_to_adopt']:
            top_practice = benchmark['best_practices_to_adopt'][0]
            recommendations.append(f"💡 Рекомендуется внедрить: {top_practice['title']} (успешно работает в {', '.join(top_practice['implemented_in'][:2])})")
        
        # Рекомендации по лидерам
        if benchmark['vs_average']['metrics']:
            worst_gap = min(benchmark['vs_average']['metrics'].items(), key=lambda x: x[1]['gap'])
            recommendations.append(f"📊 Отставание по {worst_gap[0]} составляет {abs(worst_gap[1]['gap']):.1f} балла. Обратите внимание на опыт городов-лидеров.")
        
        if not recommendations:
            recommendations.append("✅ Город показывает хорошие результаты по сравнению с аналогами. Продолжайте в том же духе!")
        
        return recommendations


# ==================== ИНТЕГРАЦИЯ С ОСНОВНЫМ ПРИЛОЖЕНИЕМ ====================

async def create_city_benchmark(city_name: str) -> CityBenchmark:
    """Фабричная функция для создания системы бенчмаркинга"""
    return CityBenchmark(city_name)


# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("🧪 Тестирование CityBenchmark...")
        
        # Создаём бенчмаркинг
        benchmark = CityBenchmark("Коломна")
        
        # 1. Загружаем профиль города
        print("\n📊 ПРОФИЛЬ ГОРОДА:")
        profile = await benchmark.load_city_profile()
        print(f"  {profile.name}: население {profile.population:,} чел.")
        print(f"  Метрики: СБ={profile.metrics['СБ']}, ТФ={profile.metrics['ТФ']}, УБ={profile.metrics['УБ']}, ЧВ={profile.metrics['ЧВ']}")
        
        # 2. Поиск городов-аналогов
        print("\n🔍 ГОРОДА-АНАЛОГИ:")
        similar = await benchmark.find_similar_cities()
        print(f"  Найдено {len(similar)} городов: {', '.join(similar[:5])}")
        
        # 3. Сравнение с конкретным городом
        print("\n📊 СРАВНЕНИЕ С СЕРПУХОВОМ:")
        comparison = await benchmark.compare_with_city("Серпухов")
        if comparison:
            print(f"  Общая оценка: {comparison.overall_score:.0%}")
            print(f"  Сильные стороны: {', '.join(comparison.strengths[:2])}")
            print(f"  Слабые стороны: {', '.join(comparison.weaknesses[:2])}")
            print(f"  Рекомендуемые практики: {len(comparison.recommended_practices)}")
        
        # 4. Полный бенчмаркинг
        print("\n🏆 ПОЛНЫЙ БЕНЧМАРКИНГ:")
        full_benchmark = await benchmark.run_full_benchmark()
        print(f"  Позиция в рейтинге: {full_benchmark['ranking']['position']}/{full_benchmark['ranking']['total_cities']}")
        print(f"  Лучшие практики для внедрения: {len(full_benchmark['best_practices_to_adopt'])}")
        
        if full_benchmark['best_practices_to_adopt']:
            top = full_benchmark['best_practices_to_adopt'][0]
            print(f"    • {top['title']} (из {', '.join(top['implemented_in'][:2])})")
        
        # 5. Рейтинг городов
        print("\n📊 РЕЙТИНГ ГОРОДОВ (общий):")
        ranking = await benchmark.get_ranking("overall")
        for r in ranking[:5]:
            marker = "👉" if r['city'] == "Коломна" else "  "
            print(f"  {marker} {r['position']}. {r['city']} — {r['score']:.2f}")
        
        # 6. Дашборд
        print("\n📋 ДАШБОРД БЕНЧМАРКИНГА:")
        dashboard = await benchmark.get_benchmark_dashboard()
        print(f"  Текущая позиция: {dashboard['current_position']['position']}/{dashboard['total_cities']}")
        print(f"  Лучше аналогов: {dashboard['vs_similar_cities']['better_than']} городов")
        print(f"  Хуже аналогов: {dashboard['vs_similar_cities']['worse_than']} городов")
        
        if dashboard['top_opportunities']:
            print(f"  Возможности: {dashboard['top_opportunities'][0][:60]}...")
        
        print("\n✅ Тест завершен")
    
    asyncio.run(demo())
