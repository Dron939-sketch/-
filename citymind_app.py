# app_citymind.py
"""
CityMind - Система управления городским развитием на основе конфайнт-модели
Для мэров и городских администраций
"""

import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
from fastapi import FastAPI, BackgroundTasks, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import pandas as pd
import numpy as np

# Наши модули
from confinement_model import ConfinementModel9, VECTORS
from loop_analyzer import CityLoopAnalyzer
from key_confinement import CityKeyConfinementDetector
from intervention_library import CityInterventionLibrary
from confinement_reporter import ConfinementReporter
from question_context_analyzer import CityQuestionContextAnalyzer

logger = logging.getLogger(__name__)

# ==================== МОДЕЛИ ДАННЫХ ====================

class NewsSource(str, Enum):
    TELEGRAM = "telegram"
    VK = "vk"
    OK = "ok"
    YANDEX_NEWS = "yandex_news"
    RSS = "rss"
    CUSTOM_API = "custom_api"

class EventType(str, Enum):
    SAFETY = "safety"
    ECONOMY = "economy"
    INFRASTRUCTURE = "infrastructure"
    SOCIAL = "social"
    CULTURE = "culture"
    ECOLOGY = "ecology"
    EDUCATION = "education"
    HEALTHCARE = "healthcare"

class Priority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class NewsItem:
    """Новостной элемент"""
    id: str
    title: str
    content: str
    source: str
    published_at: datetime
    url: str
    vector: str  # СБ, ТФ, УБ, ЧВ
    sentiment: float  # -1..1
    importance: float  # 0..1
    keywords: List[str] = field(default_factory=list)
    entities: Dict[str, Any] = field(default_factory=dict)
    
@dataclass
class CityAgenda:
    """Повестка дня города"""
    date: datetime
    title: str
    description: str
    priority: Priority
    vector: str
    related_news: List[NewsItem]
    suggested_actions: List[Dict]
    expected_impact: float
    deadline: datetime

@dataclass
class DesiredEvent:
    """Желаемое событие (ввод мэра)"""
    name: str
    description: str
    target_date: datetime
    target_vector: str  # какой вектор хотим улучшить
    target_level: int  # желаемый уровень 1-6
    current_level: int  # текущий уровень
    budget: Optional[float] = None
    stakeholders: List[str] = field(default_factory=list)

@dataclass
class EventRoadmap:
    """Дорожная карта мероприятий"""
    event: DesiredEvent
    required_actions: List[Dict]
    timeline: Dict[str, List[Dict]]
    resources_needed: Dict[str, float]
    risks: List[Dict]
    success_probability: float
    alternative_scenarios: List[Dict]

# ==================== СБОРЩИК НОВОСТЕЙ ====================

class NewsCollector:
    """Сбор новостей из различных источников"""
    
    def __init__(self, city_name: str, city_id: str):
        self.city_name = city_name
        self.city_id = city_id
        self.sources_config = {}
        self.news_cache = []
        
    async def collect_from_all_sources(self, hours_back: int = 24) -> List[NewsItem]:
        """Сбор из всех настроенных источников"""
        all_news = []
        
        # Параллельный сбор из разных источников
        tasks = []
        for source in self.sources_config:
            tasks.append(self._collect_from_source(source, hours_back))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, list):
                all_news.extend(result)
        
        # Дедипликация и сортировка
        all_news = self._deduplicate_news(all_news)
        all_news.sort(key=lambda x: x.published_at, reverse=True)
        
        self.news_cache = all_news
        return all_news
    
    async def _collect_from_source(self, source: str, hours_back: int) -> List[NewsItem]:
        """Сбор из конкретного источника"""
        # Здесь интеграция с реальными API
        # Telegram API, VK API, Yandex News API и т.д.
        
        # Для демо - генерация тестовых новостей
        return self._generate_mock_news(source, hours_back)
    
    def _generate_mock_news(self, source: str, hours_back: int) -> List[NewsItem]:
        """Генерация тестовых новостей (заменить на реальные API)"""
        mock_news = []
        
        templates = {
            'СБ': [
                ("В городе {city} снизилась преступность", "За месяц количество грабежей уменьшилось на 15%", 0.7),
                ("Авария на {city} трассе", "Столкновение 3 автомобилей, пострадавших нет", -0.5),
                ("Новая система видеонаблюдения", "В городе установили 100 камер", 0.8),
            ],
            'ТФ': [
                ("Открытие нового завода в {city}", "Создано 500 рабочих мест", 0.9),
                ("Бюджет города вырос на 20%", "Дополнительные средства пойдут на развитие", 0.8),
                ("Рост цен на продукты", "Инфляция достигла 8%", -0.6),
            ],
            'УБ': [
                ("Новый парк открылся в {city}", "Площадь благоустройства 5 гектаров", 0.9),
                ("Проблемы с вывозом мусора", "Жители жалуются на запах", -0.7),
                ("Ремонт дорог в центре", "Завершены работы на 5 улицах", 0.6),
            ],
            'ЧВ': [
                ("Городской фестиваль собрал 10 тыс. человек", "Жители довольны программой", 0.8),
                ("Конфликт жителей с застройщиком", "Активисты требуют соблюдения норм", -0.6),
                ("Волонтёры помогли приюту", "Собрано 100 тыс. рублей", 0.7),
            ]
        }
        
        for vector, news_list in templates.items():
            for title, content, sentiment in news_list:
                news = NewsItem(
                    id=f"{source}_{vector}_{datetime.now().timestamp()}",
                    title=title.format(city=self.city_name),
                    content=content,
                    source=source,
                    published_at=datetime.now() - timedelta(hours=np.random.randint(0, hours_back)),
                    url=f"https://{source}.com/news/123",
                    vector=vector,
                    sentiment=sentiment,
                    importance=abs(sentiment) * 0.8 + 0.2,
                    keywords=[vector, self.city_name]
                )
                mock_news.append(news)
        
        return mock_news
    
    def _deduplicate_news(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """Удаление дубликатов"""
        seen = set()
        unique = []
        for news in news_list:
            key = f"{news.title}_{news.published_at.date()}"
            if key not in seen:
                seen.add(key)
                unique.append(news)
        return unique

# ==================== АНАЛИЗАТОР НОВОСТЕЙ ====================

class NewsAnalyzer:
    """Анализ новостей и формирование метрик города"""
    
    def __init__(self, city_name: str):
        self.city_name = city_name
        self.current_metrics = {
            'СБ': 3.0, 'ТФ': 3.0, 'УБ': 3.0, 'ЧВ': 3.0
        }
        self.metrics_history = []
        
    def analyze_news_batch(self, news_items: List[NewsItem]) -> Dict[str, float]:
        """Анализ пачки новостей и обновление метрик"""
        
        # Агрегируем сентименты по векторам
        vector_scores = {'СБ': [], 'ТФ': [], 'УБ': [], 'ЧВ': []}
        vector_importance = {'СБ': 0, 'ТФ': 0, 'УБ': 0, 'ЧВ': 0}
        
        for news in news_items:
            if news.vector in vector_scores:
                # Взвешенный сентимент с учётом важности
                weighted_sentiment = news.sentiment * news.importance
                vector_scores[news.vector].append(weighted_sentiment)
                vector_importance[news.vector] += news.importance
        
        # Вычисляем новые значения метрик
        new_metrics = {}
        for vector in vector_scores:
            if vector_scores[vector]:
                # Средний сентимент
                avg_sentiment = sum(vector_scores[vector]) / len(vector_scores[vector])
                # Изменение метрики (от -1 до 1)
                delta = avg_sentiment * 0.3  # плавное изменение
                # Обновляем
                old_value = self.current_metrics.get(vector, 3.0)
                new_value = max(1.0, min(6.0, old_value + delta))
                new_metrics[vector] = new_value
            else:
                new_metrics[vector] = self.current_metrics.get(vector, 3.0)
        
        # Сохраняем историю
        self.metrics_history.append({
            'timestamp': datetime.now(),
            'metrics': self.current_metrics.copy()
        })
        
        # Обновляем текущие метрики
        self.current_metrics = new_metrics
        
        # Оставляем только последние 100 записей
        if len(self.metrics_history) > 100:
            self.metrics_history = self.metrics_history[-100:]
        
        return new_metrics
    
    def get_trend(self, vector: str, days: int = 7) -> Dict[str, Any]:
        """Анализ тренда по вектору"""
        relevant_history = self.metrics_history[-days:]
        if not relevant_history:
            return {'trend': 'stable', 'change': 0}
        
        values = [h['metrics'].get(vector, 3.0) for h in relevant_history]
        change = values[-1] - values[0] if values else 0
        
        if change > 0.3:
            trend = 'improving'
        elif change < -0.3:
            trend = 'declining'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'change': change,
            'current': values[-1] if values else 3.0,
            'history': values
        }

# ==================== ГЕНЕРАТОР ПОВЕСТОК ====================

class AgendaGenerator:
    """Генерация городских повесток на основе анализа"""
    
    def __init__(self, model: ConfinementModel9, news_analyzer: NewsAnalyzer):
        self.model = model
        self.news_analyzer = news_analyzer
        
    def generate_daily_agenda(self) -> CityAgenda:
        """Генерация ежедневной повестки"""
        # Находим самый проблемный вектор
        weakest_vector = min(self.news_analyzer.current_metrics.items(), 
                            key=lambda x: x[1])
        vector, score = weakest_vector
        
        # Получаем тренд
        trend = self.news_analyzer.get_trend(vector)
        
        # Формируем повестку
        agenda = CityAgenda(
            date=datetime.now(),
            title=self._generate_title(vector, trend),
            description=self._generate_description(vector, score, trend),
            priority=self._calculate_priority(score, trend),
            vector=vector,
            related_news=self._get_relevant_news(vector),
            suggested_actions=self._suggest_actions(vector),
            expected_impact=self._calculate_expected_impact(score),
            deadline=datetime.now() + timedelta(days=7)
        )
        
        return agenda
    
    def generate_weekly_agenda(self) -> List[CityAgenda]:
        """Генерация недельной повестки"""
        agendas = []
        for day in range(7):
            agenda = self.generate_daily_agenda()
            agenda.date = datetime.now() + timedelta(days=day)
            agendas.append(agenda)
        return agendas
    
    def _generate_title(self, vector: str, trend: Dict) -> str:
        """Генерация заголовка повестки"""
        titles = {
            'СБ': {
                'improving': "Укрепление городской безопасности",
                'declining': "Критическая ситуация с безопасностью",
                'stable': "Поддержание безопасной среды"
            },
            'ТФ': {
                'improving': "Развитие экономики и привлечение инвестиций",
                'declining': "Антикризисные меры для экономики",
                'stable': "Стабилизация экономической ситуации"
            },
            'УБ': {
                'improving': "Повышение качества жизни горожан",
                'declining': "Срочное благоустройство города",
                'stable': "Плановое развитие городской среды"
            },
            'ЧВ': {
                'improving': "Укрепление социальных связей",
                'declining': "Преодоление социальной напряжённости",
                'stable': "Поддержка общественных инициатив"
            }
        }
        return titles.get(vector, {}).get(trend['trend'], "План развития города")
    
    def _generate_description(self, vector: str, score: float, trend: Dict) -> str:
        """Генерация описания повестки"""
        vector_name = VECTORS.get(vector, {}).get('name', vector)
        
        if trend['trend'] == 'declining':
            return f"Показатель {vector_name} снизился до {score:.1f}/6. Требуются срочные меры для стабилизации ситуации."
        elif trend['trend'] == 'improving':
            return f"Показатель {vector_name} улучшается ({score:.1f}/6). Необходимо закрепить положительную динамику."
        else:
            return f"Показатель {vector_name} стабилен ({score:.1f}/6). Плановые мероприятия для дальнейшего развития."
    
    def _calculate_priority(self, score: float, trend: Dict) -> Priority:
        """Расчёт приоритета"""
        if score <= 2.0 or (trend['trend'] == 'declining' and trend['change'] < -0.5):
            return Priority.CRITICAL
        elif score <= 2.5 or (trend['trend'] == 'declining' and trend['change'] < -0.2):
            return Priority.HIGH
        elif score <= 3.5:
            return Priority.MEDIUM
        else:
            return Priority.LOW
    
    def _get_relevant_news(self, vector: str) -> List[NewsItem]:
        """Получение релевантных новостей"""
        # Здесь нужно получить из кэша новостей
        return []
    
    def _suggest_actions(self, vector: str) -> List[Dict]:
        """Предложение действий"""
        actions = {
            'СБ': [
                {"action": "Усиление патрулирования", "cost": "medium", "time": "1 неделя"},
                {"action": "Установка камер наблюдения", "cost": "high", "time": "1 месяц"},
                {"action": "Программа 'Соседский дозор'", "cost": "low", "time": "2 недели"}
            ],
            'ТФ': [
                {"action": "Встреча с инвесторами", "cost": "low", "time": "1 неделя"},
                {"action": "Создание ТОР", "cost": "medium", "time": "3 месяца"},
                {"action": "Поддержка МСП", "cost": "medium", "time": "1 месяц"}
            ],
            'УБ': [
                {"action": "Благоустройство парка", "cost": "medium", "time": "2 месяца"},
                {"action": "Ремонт дорог", "cost": "high", "time": "3 месяца"},
                {"action": "Установка скамеек и урн", "cost": "low", "time": "1 неделя"}
            ],
            'ЧВ': [
                {"action": "Городской фестиваль", "cost": "medium", "time": "1 месяц"},
                {"action": "Конкурс ТОС", "cost": "low", "time": "2 недели"},
                {"action": "Открытые слушания", "cost": "low", "time": "1 неделя"}
            ]
        }
        return actions.get(vector, [])
    
    def _calculate_expected_impact(self, current_score: float) -> float:
        """Расчёт ожидаемого эффекта"""
        # Чем хуже ситуация, тем выше потенциальный эффект
        return (6.0 - current_score) / 6.0

# ==================== ПЛАНИРОВЩИК МЕРОПРИЯТИЙ ====================

class EventPlanner:
    """Планирование мероприятий для достижения желаемых целей"""
    
    def __init__(self, model: ConfinementModel9, intervention_lib: CityInterventionLibrary):
        self.model = model
        self.intervention_lib = intervention_lib
        
    def plan_for_desired_event(self, desired: DesiredEvent) -> EventRoadmap:
        """Планирование для достижения желаемого события"""
        
        # Рассчитываем необходимый сдвиг
        required_shift = desired.target_level - desired.current_level
        
        # Подбираем интервенции
        interventions = self._select_interventions(desired.target_vector, required_shift)
        
        # Строим дорожную карту
        roadmap = EventRoadmap(
            event=desired,
            required_actions=interventions,
            timeline=self._build_timeline(interventions, desired.target_date),
            resources_needed=self._calculate_resources(interventions),
            risks=self._identify_risks(desired),
            success_probability=self._calculate_success_probability(desired, interventions),
            alternative_scenarios=self._generate_alternatives(desired)
        )
        
        return roadmap
    
    def _select_interventions(self, target_vector: str, required_shift: float) -> List[Dict]:
        """Выбор интервенций для достижения цели"""
        interventions = []
        
        # Карта интервенций по векторам
        intervention_map = {
            'СБ': [
                {"name": "Программа 'Безопасный город'", "impact": 1.5, "duration": 90, "cost": 10000000},
                {"name": "Установка освещения", "impact": 1.0, "duration": 30, "cost": 5000000},
                {"name": "Патрулирование", "impact": 0.8, "duration": 7, "cost": 2000000},
                {"name": "Соседский дозор", "impact": 0.5, "duration": 14, "cost": 500000}
            ],
            'ТФ': [
                {"name": "Привлечение инвесторов", "impact": 1.5, "duration": 180, "cost": 5000000},
                {"name": "Поддержка МСП", "impact": 1.0, "duration": 60, "cost": 3000000},
                {"name": "Создание ТОР", "impact": 2.0, "duration": 365, "cost": 50000000},
                {"name": "Бизнес-акселератор", "impact": 0.8, "duration": 90, "cost": 2000000}
            ],
            'УБ': [
                {"name": "Благоустройство парков", "impact": 1.2, "duration": 120, "cost": 15000000},
                {"name": "Ремонт дорог", "impact": 1.0, "duration": 180, "cost": 30000000},
                {"name": "Спортивные площадки", "impact": 0.8, "duration": 60, "cost": 5000000},
                {"name": "Детские площадки", "impact": 0.6, "duration": 45, "cost": 3000000}
            ],
            'ЧВ': [
                {"name": "Городские фестивали", "impact": 1.0, "duration": 60, "cost": 5000000},
                {"name": "Поддержка НКО", "impact": 0.8, "duration": 30, "cost": 2000000},
                {"name": "Общественные центры", "impact": 1.2, "duration": 180, "cost": 15000000},
                {"name": "Конкурс инициатив", "impact": 0.7, "duration": 45, "cost": 1000000}
            ]
        }
        
        available = intervention_map.get(target_vector, [])
        remaining_shift = required_shift
        
        # Жадный алгоритм выбора интервенций
        for intervention in sorted(available, key=lambda x: x['impact']/x['cost'], reverse=True):
            if remaining_shift <= 0:
                break
            interventions.append(intervention)
            remaining_shift -= intervention['impact']
        
        return interventions
    
    def _build_timeline(self, interventions: List[Dict], target_date: datetime) -> Dict[str, List[Dict]]:
        """Построение временной шкалы"""
        timeline = {
            'immediate': [],  # 1-2 недели
            'short': [],      # 1-2 месяца
            'medium': [],     # 3-6 месяцев
            'long': []        # 6+ месяцев
        }
        
        now = datetime.now()
        
        for inv in interventions:
            if inv['duration'] <= 14:
                timeline['immediate'].append(inv)
            elif inv['duration'] <= 60:
                timeline['short'].append(inv)
            elif inv['duration'] <= 180:
                timeline['medium'].append(inv)
            else:
                timeline['long'].append(inv)
        
        return timeline
    
    def _calculate_resources(self, interventions: List[Dict]) -> Dict[str, float]:
        """Расчёт необходимых ресурсов"""
        total_budget = sum(inv.get('cost', 0) for inv in interventions)
        
        return {
            'budget': total_budget,
            'time_days': max(inv.get('duration', 0) for inv in interventions) if interventions else 0,
            'personnel': len(interventions) * 5,  # примерная оценка
            'materials': total_budget * 0.3
        }
    
    def _identify_risks(self, desired: DesiredEvent) -> List[Dict]:
        """Идентификация рисков"""
        risks = [
            {
                "risk": "Недостаточное финансирование",
                "probability": 0.4,
                "impact": 0.8,
                "mitigation": "Поиск внебюджетных источников"
            },
            {
                "risk": "Сопротивление жителей",
                "probability": 0.3,
                "impact": 0.6,
                "mitigation": "Широкая коммуникационная кампания"
            },
            {
                "risk": "Бюрократические барьеры",
                "probability": 0.5,
                "impact": 0.7,
                "mitigation": "Создание проектного офиса"
            },
            {
                "risk": "Нехватка времени",
                "probability": 0.4,
                "impact": 0.9,
                "mitigation": "Аутсорсинг части работ"
            }
        ]
        return risks
    
    def _calculate_success_probability(self, desired: DesiredEvent, interventions: List[Dict]) -> float:
        """Расчёт вероятности успеха"""
        # Базовые факторы
        base_probability = 0.5
        
        # Корректировка на сдвиг
        shift = desired.target_level - desired.current_level
        if shift > 2:
            base_probability -= 0.3
        elif shift < 1:
            base_probability += 0.2
        
        # Корректировка на количество интервенций
        if len(interventions) > 5:
            base_probability -= 0.2
        elif len(interventions) <= 3:
            base_probability += 0.1
        
        # Корректировка на бюджет
        if desired.budget:
            required_budget = sum(inv.get('cost', 0) for inv in interventions)
            if desired.budget >= required_budget:
                base_probability += 0.2
            elif desired.budget < required_budget * 0.5:
                base_probability -= 0.3
        
        return max(0.1, min(0.95, base_probability))
    
    def _generate_alternatives(self, desired: DesiredEvent) -> List[Dict]:
        """Генерация альтернативных сценариев"""
        return [
            {
                "name": "Оптимистичный",
                "description": "При полном финансировании и поддержке",
                "success_probability": 0.8,
                "timeline_reduction": 0.7
            },
            {
                "name": "Пессимистичный",
                "description": "При ограниченном бюджете и сопротивлении",
                "success_probability": 0.3,
                "timeline_increase": 1.5
            },
            {
                "name": "Поэтапный",
                "description": "Разбивка на 3 этапа с промежуточными целями",
                "success_probability": 0.6,
                "stages": 3
            }
        ]

# ==================== API ДЛЯ ПРИЛОЖЕНИЯ ====================

app = FastAPI(title="CityMind - Умный город для мэров")

# Модели для API
class CityRequest(BaseModel):
    city_name: str
    region: Optional[str] = None
    population: Optional[int] = None

class DesiredEventRequest(BaseModel):
    name: str
    target_date: datetime
    target_vector: str
    target_level: int
    budget: Optional[float] = None

class QuestionRequest(BaseModel):
    question: str

# Глобальные объекты
city_contexts = {}

@app.on_event("startup")
async def startup_event():
    """Инициализация приложения"""
    logger.info("CityMind запущен")

@app.post("/api/city/init")
async def init_city(city: CityRequest):
    """Инициализация города"""
    from confinement_model import ConfinementModel9
    
    # Создаём модель города
    model = ConfinementModel9(city_name=city.city_name, city_id=hash(city.city_name))
    
    # Инициализируем сборщик новостей
    collector = NewsCollector(city.city_name, str(hash(city.city_name)))
    
    # Инициализируем анализатор новостей
    analyzer = NewsAnalyzer(city.city_name)
    
    # Сохраняем контекст
    city_contexts[city.city_name] = {
        'model': model,
        'collector': collector,
        'analyzer': analyzer,
        'agenda_generator': None,  # будет создан после первого анализа
        'event_planner': None
    }
    
    return {"status": "success", "city": city.city_name}

@app.post("/api/city/analyze")
async def analyze_city(city_name: str, background_tasks: BackgroundTasks):
    """Запуск анализа города"""
    if city_name not in city_contexts:
        return {"error": "City not initialized"}
    
    context = city_contexts[city_name]
    
    # Запускаем сбор новостей в фоне
    background_tasks.add_task(collect_news_background, city_name)
    
    return {"status": "analyzing", "city": city_name}

async def collect_news_background(city_name: str):
    """Фоновая задача сбора новостей"""
    context = city_contexts[city_name]
    
    # Собираем новости
    news = await context['collector'].collect_from_all_sources(24)
    
    # Анализируем
    new_metrics = context['analyzer'].analyze_news_batch(news)
    
    # Обновляем модель
    context['model'].build_from_city_data(new_metrics, [n.__dict__ for n in news])
    
    # Создаём генератор повесток
    context['agenda_generator'] = AgendaGenerator(context['model'], context['analyzer'])
    
    # Создаём планировщик
    lib = CityInterventionLibrary()
    context['event_planner'] = EventPlanner(context['model'], lib)
    
    logger.info(f"Analysis complete for {city_name}")

@app.get("/api/city/agenda")
async def get_agenda(city_name: str):
    """Получение текущей повестки"""
    if city_name not in city_contexts:
        return {"error": "City not initialized"}
    
    context = city_contexts[city_name]
    
    if not context['agenda_generator']:
        return {"error": "Analysis not completed yet"}
    
    agenda = context['agenda_generator'].generate_daily_agenda()
    
    return {
        "city": city_name,
        "agenda": {
            "date": agenda.date.isoformat(),
            "title": agenda.title,
            "description": agenda.description,
            "priority": agenda.priority.value,
            "vector": agenda.vector,
            "suggested_actions": agenda.suggested_actions,
            "deadline": agenda.deadline.isoformat()
        }
    }

@app.post("/api/city/plan")
async def plan_event(city_name: str, event: DesiredEventRequest):
    """Планирование желаемого события"""
    if city_name not in city_contexts:
        return {"error": "City not initialized"}
    
    context = city_contexts[city_name]
    
    if not context['event_planner']:
        return {"error": "Analysis not completed yet"}
    
    # Получаем текущие метрики
    current_metrics = context['analyzer'].current_metrics
    
    desired = DesiredEvent(
        name=event.name,
        description="",  # можно добавить из запроса
        target_date=event.target_date,
        target_vector=event.target_vector,
        target_level=event.target_level,
        current_level=current_metrics.get(event.target_vector, 3.0),
        budget=event.budget
    )
    
    roadmap = context['event_planner'].plan_for_desired_event(desired)
    
    return {
        "city": city_name,
        "desired_event": {
            "name": roadmap.event.name,
            "target_level": roadmap.event.target_level,
            "current_level": roadmap.event.current_level,
            "required_shift": roadmap.event.target_level - roadmap.event.current_level
        },
        "roadmap": {
            "required_actions": roadmap.required_actions,
            "timeline": {
                "immediate": len(roadmap.timeline['immediate']),
                "short": len(roadmap.timeline['short']),
                "medium": len(roadmap.timeline['medium']),
                "long": len(roadmap.timeline['long'])
            },
            "resources_needed": roadmap.resources_needed,
            "success_probability": roadmap.success_probability,
            "risks": roadmap.risks,
            "alternative_scenarios": roadmap.alternative_scenarios
        }
    }

@app.post("/api/city/ask")
async def ask_question(city_name: str, question_req: QuestionRequest):
    """Задать вопрос о городе"""
    if city_name not in city_contexts:
        return {"error": "City not initialized"}
    
    context = city_contexts[city_name]
    
    if not context['model']:
        return {"error": "Model not ready"}
    
    analyzer = CityQuestionContextAnalyzer(context['model'], city_name)
    analysis = analyzer.analyze(question_req.question)
    
    return {
        "city": city_name,
        "question": question_req.question,
        "reflection": analysis['reflection'],
        "vectors": analysis['vectors'][:3] if analysis['vectors'] else [],
        "depth": analysis['depth']['type'],
        "touches_key_confinement": analysis['key_confinement'].get('is_related', False) if analysis['key_confinement'] else False
    }

@app.get("/api/city/dashboard")
async def get_dashboard(city_name: str):
    """Получение дашборда города"""
    if city_name not in city_contexts:
        return {"error": "City not initialized"}
    
    context = city_contexts[city_name]
    
    metrics = context['analyzer'].current_metrics
    
    # Получаем тренды
    trends = {}
    for vector in ['СБ', 'ТФ', 'УБ', 'ЧВ']:
        trends[vector] = context['analyzer'].get_trend(vector)
    
    return {
        "city": city_name,
        "metrics": {
            "safety": {"value": metrics.get('СБ', 3.0), "trend": trends.get('СБ', {}).get('trend', 'stable')},
            "economy": {"value": metrics.get('ТФ', 3.0), "trend": trends.get('ТФ', {}).get('trend', 'stable')},
            "quality": {"value": metrics.get('УБ', 3.0), "trend": trends.get('УБ', {}).get('trend', 'stable')},
            "social": {"value": metrics.get('ЧВ', 3.0), "trend": trends.get('ЧВ', {}).get('trend', 'stable')}
        },
        "status": "active"
    }

# ==================== ВЕБ-ИНТЕРФЕЙС ====================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CityMind - Умный город для мэров</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        /* Header */
        .header {
            background: white;
            border-radius: 20px;
            padding: 20px 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .logo-icon {
            font-size: 40px;
        }
        
        .logo-text {
            font-size: 24px;
            font-weight: bold;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .city-selector {
            display: flex;
            gap: 10px;
        }
        
        .city-selector input {
            padding: 10px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            width: 250px;
        }
        
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102,126,234,0.4);
        }
        
        /* Metrics Cards */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .metric-card {
            background: white;
            border-radius: 20px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }
        
        .metric-card:hover {
            transform: translateY(-5px);
        }
        
        .metric-emoji {
            font-size: 48px;
            margin-bottom: 10px;
        }
        
        .metric-name {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 10px;
        }
        
        .metric-value {
            font-size: 36px;
            font-weight: bold;
            margin: 10px 0;
        }
        
        .metric-trend {
            font-size: 14px;
            padding: 5px 10px;
            border-radius: 20px;
            display: inline-block;
        }
        
        .trend-up { background: #d4edda; color: #155724; }
        .trend-down { background: #f8d7da; color: #721c24; }
        .trend-stable { background: #e2e3e5; color: #383d41; }
        
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 15px;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            border-radius: 10px;
            transition: width 0.5s;
        }
        
        /* Main Content */
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }
        
        .card {
            background: white;
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        
        .card-title {
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .agenda-item {
            padding: 15px;
            border-left: 4px solid;
            margin-bottom: 15px;
            background: #f8f9fa;
            border-radius: 10px;
        }
        
        .priority-critical { border-left-color: #dc3545; }
        .priority-high { border-left-color: #fd7e14; }
        .priority-medium { border-left-color: #ffc107; }
        .priority-low { border-left-color: #28a745; }
        
        .agenda-title {
            font-weight: 600;
            margin-bottom: 8px;
        }
        
        .agenda-description {
            font-size: 14px;
            color: #666;
            margin-bottom: 10px;
        }
        
        .action-buttons {
            display: flex;
            gap: 10px;
            margin-top: 10px;
        }
        
        .action-badge {
            background: #e9ecef;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 12px;
        }
        
        /* Chat Section */
        .chat-container {
            background: white;
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            height: 500px;
            display: flex;
            flex-direction: column;
        }
        
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            margin-bottom: 20px;
        }
        
        .message {
            margin-bottom: 15px;
            display: flex;
        }
        
        .message.user {
            justify-content: flex-end;
        }
        
        .message-content {
            max-width: 70%;
            padding: 12px 18px;
            border-radius: 20px;
        }
        
        .message.user .message-content {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .message.assistant .message-content {
            background: #f1f3f4;
            color: #333;
        }
        
        .chat-input-container {
            display: flex;
            gap: 10px;
        }
        
        .chat-input {
            flex: 1;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 14px;
        }
        
        /* Planning Section */
        .planning-section {
            background: white;
            border-radius: 20px;
            padding: 25px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        
        .target-inputs {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin: 20px 0;
        }
        
        .target-input {
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
        }
        
        .roadmap {
            margin-top: 20px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 15px;
        }
        
        .probability-bar {
            height: 30px;
            background: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
            margin: 10px 0;
        }
        
        .probability-fill {
            height: 100%;
            background: linear-gradient(90deg, #28a745, #20c997);
            border-radius: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .metrics-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            .main-grid {
                grid-template-columns: 1fr;
            }
        }
        
        .loading {
            text-align: center;
            padding: 20px;
        }
        
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="logo">
                <div class="logo-icon">🏙️</div>
                <div class="logo-text">CityMind — Умный город для мэров</div>
            </div>
            <div class="city-selector">
                <input type="text" id="cityInput" placeholder="Название города">
                <button class="btn btn-primary" onclick="initCity()">Загрузить</button>
            </div>
        </div>
        
        <div id="dashboardContent" style="display: none;">
            <!-- Metrics -->
            <div class="metrics-grid" id="metricsGrid">
                <!-- динамически заполняется -->
            </div>
            
            <!-- Main Content -->
            <div class="main-grid">
                <!-- Agenda -->
                <div class="card">
                    <div class="card-title">
                        <span>📋</span>
                        <span>Повестка дня</span>
                    </div>
                    <div id="agendaList">
                        <div class="loading">Загрузка повестки...</div>
                    </div>
                </div>
                
                <!-- AI Assistant -->
                <div class="chat-container">
                    <div class="card-title">
                        <span>🤖</span>
                        <span>AI-ассистент мэра</span>
                    </div>
                    <div class="chat-messages" id="chatMessages">
                        <div class="message assistant">
                            <div class="message-content">
                                Здравствуйте! Я анализирую городские новости и готов помогать с управленческими решениями. Задайте любой вопрос о городе.
                            </div>
                        </div>
                    </div>
                    <div class="chat-input-container">
                        <input type="text" class="chat-input" id="chatInput" placeholder="Спросите о городе...">
                        <button class="btn btn-primary" onclick="sendQuestion()">Отправить</button>
                    </div>
                </div>
            </div>
            
            <!-- Planning -->
            <div class="planning-section">
                <div class="card-title">
                    <span>🎯</span>
                    <span>Планирование желаемых событий</span>
                </div>
                <div class="target-inputs">
                    <select id="targetVector" class="target-input">
                        <option value="СБ">Безопасность</option>
                        <option value="ТФ">Экономика</option>
                        <option value="УБ">Качество жизни</option>
                        <option value="ЧВ">Социальный капитал</option>
                    </select>
                    <select id="targetLevel" class="target-input">
                        <option value="1">Уровень 1 (Кризис)</option>
                        <option value="2">Уровень 2 (Плохо)</option>
                        <option value="3">Уровень 3 (Средне)</option>
                        <option value="4">Уровень 4 (Хорошо)</option>
                        <option value="5">Уровень 5 (Отлично)</option>
                        <option value="6">Уровень 6 (Идеал)</option>
                    </select>
                    <input type="date" id="targetDate" class="target-input">
                </div>
                <button class="btn btn-primary" onclick="planEvent()" style="width: 100%;">Рассчитать roadmap</button>
                <div id="roadmapResult"></div>
            </div>
        </div>
    </div>
    
    <script>
        let currentCity = '';
        
        async function initCity() {
            const cityName = document.getElementById('cityInput').value;
            if (!cityName) {
                alert('Введите название города');
                return;
            }
            
            currentCity = cityName;
            showLoading();
            
            try {
                // Инициализация города
                const initRes = await fetch('/api/city/init', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({city_name: cityName})
                });
                
                if (!initRes.ok) throw new Error('Init failed');
                
                // Запуск анализа
                const analyzeRes = await fetch(`/api/city/analyze?city_name=${encodeURIComponent(cityName)}`, {
                    method: 'POST'
                });
                
                if (!analyzeRes.ok) throw new Error('Analysis failed');
                
                // Ждём немного для завершения анализа
                setTimeout(async () => {
                    await loadDashboard();
                    document.getElementById('dashboardContent').style.display = 'block';
                    hideLoading();
                }, 2000);
                
            } catch (error) {
                console.error('Error:', error);
                alert('Ошибка загрузки города');
                hideLoading();
            }
        }
        
        async function loadDashboard() {
            await loadMetrics();
            await loadAgenda();
        }
        
        async function loadMetrics() {
            try {
                const res = await fetch(`/api/city/dashboard?city_name=${encodeURIComponent(currentCity)}`);
                const data = await res.json();
                
                const metrics = data.metrics;
                const metricsGrid = document.getElementById('metricsGrid');
                
                metricsGrid.innerHTML = `
                    <div class="metric-card">
                        <div class="metric-emoji">🛡️</div>
                        <div class="metric-name">Безопасность</div>
                        <div class="metric-value">${metrics.safety.value.toFixed(1)}/6</div>
                        <div class="metric-trend trend-${metrics.safety.trend}">
                            ${metrics.safety.trend === 'improving' ? '📈 Растёт' : metrics.safety.trend === 'declining' ? '📉 Падает' : '➡️ Стабильно'}
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${(metrics.safety.value / 6) * 100}%"></div>
                        </div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-emoji">💰</div>
                        <div class="metric-name">Экономика</div>
                        <div class="metric-value">${metrics.economy.value.toFixed(1)}/6</div>
                        <div class="metric-trend trend-${metrics.economy.trend}">
                            ${metrics.economy.trend === 'improving' ? '📈 Растёт' : metrics.economy.trend === 'declining' ? '📉 Падает' : '➡️ Стабильно'}
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${(metrics.economy.value / 6) * 100}%"></div>
                        </div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-emoji">😊</div>
                        <div class="metric-name">Качество жизни</div>
                        <div class="metric-value">${metrics.quality.value.toFixed(1)}/6</div>
                        <div class="metric-trend trend-${metrics.quality.trend}">
                            ${metrics.quality.trend === 'improving' ? '📈 Растёт' : metrics.quality.trend === 'declining' ? '📉 Падает' : '➡️ Стабильно'}
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${(metrics.quality.value / 6) * 100}%"></div>
                        </div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-emoji">🤝</div>
                        <div class="metric-name">Соц. капитал</div>
                        <div class="metric-value">${metrics.social.value.toFixed(1)}/6</div>
                        <div class="metric-trend trend-${metrics.social.trend}">
                            ${metrics.social.trend === 'improving' ? '📈 Растёт' : metrics.social.trend === 'declining' ? '📉 Падает' : '➡️ Стабильно'}
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${(metrics.social.value / 6) * 100}%"></div>
                        </div>
                    </div>
                `;
            } catch (error) {
                console.error('Error loading metrics:', error);
            }
        }
        
        async function loadAgenda() {
            try {
                const res = await fetch(`/api/city/agenda?city_name=${encodeURIComponent(currentCity)}`);
                const data = await res.json();
                
                if (data.error) {
                    document.getElementById('agendaList').innerHTML = `<div class="loading">${data.error}</div>`;
                    return;
                }
                
                const agenda = data.agenda;
                const priorityClass = `priority-${agenda.priority}`;
                
                document.getElementById('agendaList').innerHTML = `
                    <div class="agenda-item ${priorityClass}">
                        <div class="agenda-title">${agenda.title}</div>
                        <div class="agenda-description">${agenda.description}</div>
                        <div class="action-buttons">
                            ${agenda.suggested_actions.map(action => 
                                `<span class="action-badge">${action.action}</span>`
                            ).join('')}
                        </div>
                        <div style="margin-top: 10px; font-size: 12px; color: #999;">
                            📅 Срок: ${new Date(agenda.deadline).toLocaleDateString()}
                        </div>
                    </div>
                `;
            } catch (error) {
                console.error('Error loading agenda:', error);
            }
        }
        
        async function sendQuestion() {
            const input = document.getElementById('chatInput');
            const question = input.value.trim();
            if (!question) return;
            
            // Добавляем сообщение пользователя
            addMessage(question, 'user');
            input.value = '';
            
            // Показываем индикатор загрузки
            addMessage('...', 'assistant', true);
            
            try {
                const res = await fetch(`/api/city/ask?city_name=${encodeURIComponent(currentCity)}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({question: question})
                });
                
                const data = await res.json();
                
                // Удаляем индикатор загрузки
                removeLoadingMessage();
                
                // Формируем ответ
                let response = data.reflection;
                if (data.vectors && data.vectors.length > 0) {
                    response += `\n\n📊 Затронутые сферы: ${data.vectors.map(v => v.emoji + ' ' + v.name).join(', ')}`;
                }
                if (data.touches_key_confinement) {
                    response += `\n\n⚠️ Этот вопрос затрагивает ключевое ограничение города.`;
                }
                
                addMessage(response, 'assistant');
            } catch (error) {
                console.error('Error:', error);
                removeLoadingMessage();
                addMessage('Извините, произошла ошибка. Попробуйте позже.', 'assistant');
            }
        }
        
        async function planEvent() {
            const targetVector = document.getElementById('targetVector').value;
            const targetLevel = parseInt(document.getElementById('targetLevel').value);
            const targetDate = document.getElementById('targetDate').value;
            
            if (!targetDate) {
                alert('Выберите дату цели');
                return;
            }
            
            showRoadmapLoading();
            
            try {
                const res = await fetch(`/api/city/plan?city_name=${encodeURIComponent(currentCity)}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        name: `Достижение уровня ${targetLevel} по ${targetVector}`,
                        target_date: targetDate,
                        target_vector: targetVector,
                        target_level: targetLevel
                    })
                });
                
                const data = await res.json();
                
                if (data.error) {
                    document.getElementById('roadmapResult').innerHTML = `<div class="roadmap">❌ ${data.error}</div>`;
                    return;
                }
                
                const roadmap = data.roadmap;
                const probPercent = Math.round(roadmap.success_probability * 100);
                
                document.getElementById('roadmapResult').innerHTML = `
                    <div class="roadmap">
                        <h3>📋 Дорожная карта</h3>
                        <p><strong>Требуемый сдвиг:</strong> ${data.desired_event.required_shift.toFixed(1)} уровня</p>
                        <p><strong>Вероятность успеха:</strong></p>
                        <div class="probability-bar">
                            <div class="probability-fill" style="width: ${probPercent}%">${probPercent}%</div>
                        </div>
                        <p><strong>Необходимые ресурсы:</strong></p>
                        <ul>
                            <li>💰 Бюджет: ${(roadmap.resources_needed.budget / 1000000).toFixed(1)} млн ₽</li>
                            <li>⏱️ Время: ${roadmap.resources_needed.time_days} дней</li>
                            <li>👥 Персонал: ${roadmap.resources_needed.personnel} чел.</li>
                        </ul>
                        <p><strong>Необходимые мероприятия:</strong></p>
                        <ul>
                            ${roadmap.required_actions.map(a => `<li>${a.name} (${a.duration} дней, ${(a.cost/1000000).toFixed(1)} млн ₽)</li>`).join('')}
                        </ul>
                        <p><strong>Риски:</strong></p>
                        <ul>
                            ${roadmap.risks.map(r => `<li>⚠️ ${r.risk} — ${r.mitigation}</li>`).join('')}
                        </ul>
                        <p><strong>Альтернативные сценарии:</strong></p>
                        <ul>
                            ${roadmap.alternative_scenarios.map(s => `<li>${s.name}: ${s.description}</li>`).join('')}
                        </ul>
                    </div>
                `;
            } catch (error) {
                console.error('Error:', error);
                document.getElementById('roadmapResult').innerHTML = `<div class="roadmap">❌ Ошибка расчёта</div>`;
            }
        }
        
        function addMessage(text, sender, isLoading = false) {
            const messagesDiv = document.getElementById('chatMessages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${sender}`;
            if (isLoading) {
                messageDiv.id = 'loadingMessage';
                messageDiv.innerHTML = `<div class="message-content"><div class="spinner"></div></div>`;
            } else {
                messageDiv.innerHTML = `<div class="message-content">${text.replace(/\n/g, '<br>')}</div>`;
            }
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
        
        function removeLoadingMessage() {
            const loadingMsg = document.getElementById('loadingMessage');
            if (loadingMsg) loadingMsg.remove();
        }
        
        function showLoading() {
            // Можно добавить индикатор загрузки
        }
        
        function hideLoading() {
            // Убрать индикатор загрузки
        }
        
        function showRoadmapLoading() {
            document.getElementById('roadmapResult').innerHTML = '<div class="roadmap"><div class="spinner"></div><div style="text-align:center">Расчёт roadmap...</div></div>';
        }
        
        // Enter key for chat
        document.getElementById('chatInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendQuestion();
            }
        });
    </script>
</body>
</html>
"""

@app.get("/")
async def web_interface():
    """Веб-интерфейс"""
    return HTMLResponse(HTML_TEMPLATE)

@app.get("/dashboard")
async def dashboard():
    """Альтернативный дашборд"""
    return HTMLResponse(HTML_TEMPLATE)

# ==================== ЗАПУСК ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
