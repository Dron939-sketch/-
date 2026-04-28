#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 19: БАНК ЗНАНИЙ ГОРОДОВ (Knowledge Bank)
Централизованное хранилище кейсов, решений, причинно-следственных связей
и лучших практик из опыта других городов

Основан на методах:
- База знаний с графовыми связями
- Векторный поиск семантически похожих ситуаций
- Система оценки эффективности решений
- Извлечение уроков из успехов и ошибок
- Рекомендательная система на основе прецедентов (CBR)
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
import pickle
from pathlib import Path

# Для векторного поиска
try:
    from sentence_transformers import SentenceTransformer
    import faiss
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logging.warning("sentence-transformers или faiss не установлены. Векторный поиск отключён.")

logger = logging.getLogger(__name__)


# ==================== МОДЕЛИ ДАННЫХ ====================

class SolutionOutcome(Enum):
    """Исход решения"""
    SUCCESS = "success"           # Успешное
    PARTIAL = "partial"           # Частично успешное
    NEUTRAL = "neutral"           # Нейтральное
    FAILURE = "failure"           # Провальное
    CATASTROPHIC = "catastrophic" # Катастрофическое (ухудшило ситуацию)


class KnowledgeDomain(Enum):
    """Домены знаний"""
    SAFETY = "safety"                 # Безопасность
    ECONOMY = "economy"               # Экономика
    INFRASTRUCTURE = "infrastructure" # Инфраструктура
    SOCIAL = "social"                 # Социальная сфера
    ECOLOGY = "ecology"               # Экология
    TRANSPORT = "transport"           # Транспорт
    HEALTHCARE = "healthcare"         # Здравоохранение
    EDUCATION = "education"           # Образование
    HOUSING = "housing"               # ЖКХ
    CULTURE = "culture"               # Культура
    GOVERNANCE = "governance"         # Управление
    REPUTATION = "reputation"         # Репутация


@dataclass
class CityCase:
    """Кейс города — проблема + решение + результат"""
    id: str
    city_name: str
    region: str
    population: int
    year: int
    domain: KnowledgeDomain
    problem_description: str
    problem_severity: str              # low/medium/high/critical
    problem_vectors: List[str]         # затронутые векторы Мейстера
    solution_description: str
    solution_actions: List[str]        # конкретные шаги
    solution_cost_million_rub: float
    solution_duration_months: int
    outcome: SolutionOutcome
    outcome_metrics: Dict[str, float]  # изменение метрик (СБ, ТФ, УБ, ЧВ)
    lessons_learned: List[str]
    pitfalls: List[str]                # ошибки, которых стоит избегать
    success_factors: List[str]         # ключевые факторы успеха
    source_url: str
    verified: bool = True
    verification_source: str = "экспертная оценка"
    created_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)


@dataclass
class CauseEffectChain:
    """Причинно-следственная цепочка"""
    id: str
    name: str
    description: str
    domain: KnowledgeDomain
    trigger: str                       # что запускает цепочку
    chain: List[Dict]                  # последовательность "причина → следствие"
    reinforcing_factors: List[str]     # усиливающие факторы
    breaking_points: List[str]         # точки разрыва
    examples: List[str]                # города, где наблюдалось
    confidence: float                  # 0-1, уверенность в цепочке


@dataclass
class BestPractice:
    """Лучшая практика"""
    id: str
    name: str
    description: str
    domain: KnowledgeDomain
    target_vectors: List[str]
    implementation_steps: List[str]
    prerequisites: List[str]           # что нужно иметь для внедрения
    estimated_cost: str                # низкий/средний/высокий
    estimated_time_months: int
    expected_impact: Dict[str, float]  # ожидаемое влияние на метрики
    success_rate: float                # 0-1, процент успешных внедрений
    cities_implemented: List[str]      # города, где внедрено
    pitfalls: List[str]
    tags: List[str]


# ==================== БАЗА ЗНАНИЙ ====================

class KnowledgeBank:
    """
    Банк знаний городов — хранилище кейсов, причинно-следственных связей
    и лучших практик для принятия оптимальных решений
    """
    
    def __init__(self, city_name: str, data_dir: str = "./knowledge_bank"):
        self.city_name = city_name
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Хранилища
        self.cases: Dict[str, CityCase] = {}
        self.cause_effect_chains: Dict[str, CauseEffectChain] = {}
        self.best_practices: Dict[str, BestPractice] = {}
        
        # Для векторного поиска
        self.embedding_model = None
        self.case_embeddings = None
        self.case_index = None
        self.case_ids = []
        
        # Инициализация
        self._load_initial_data()
        self._init_embeddings()
        
        logger.info(f"KnowledgeBank инициализирован для города {city_name}")
        logger.info(f"Загружено: {len(self.cases)} кейсов, {len(self.cause_effect_chains)} цепочек, {len(self.best_practices)} практик")
    
    def _init_embeddings(self):
        """Инициализация модели для векторного поиска"""
        if EMBEDDINGS_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                logger.info("Модель эмбеддингов загружена")
            except Exception as e:
                logger.warning(f"Не удалось загрузить модель эмбеддингов: {e}")
    
    def _load_initial_data(self):
        """Загрузка начальных данных (в реальности — из БД)"""
        
        # ========== КЕЙСЫ ГОРОДОВ ==========
        
        # 1. Серпухов — программа "Соседский дозор"
        self.cases["serpukhov_safety"] = CityCase(
            id="serpukhov_safety",
            city_name="Серпухов",
            region="Московская область",
            population=125000,
            year=2024,
            domain=KnowledgeDomain.SAFETY,
            problem_description="Рост уличной преступности, грабежи в тёмное время суток",
            problem_severity="high",
            problem_vectors=["СБ"],
            solution_description="Программа «Соседский дозор» — вовлечение жителей в обеспечение безопасности",
            solution_actions=[
                "Создание чатов домов и районов",
                "Обучение активистов",
                "Установка камер с доступом для жителей",
                "Патрулирование силами жителей"
            ],
            solution_cost_million_rub=2.5,
            solution_duration_months=6,
            outcome=SolutionOutcome.SUCCESS,
            outcome_metrics={"СБ": 0.8, "ЧВ": 0.3},
            lessons_learned=[
                "Жители активно включаются, когда видят результат",
                "Важно обучение и поддержка активистов",
                "Быстрые победы (первые камеры) мотивируют"
            ],
            pitfalls=[
                "Без поддержки администрации быстро затухает",
                "Нужен постоянный координатор"
            ],
            success_factors=[
                "Сильная инициативная группа",
                "Видимые результаты в первые 2 месяца",
                "Прозрачность и обратная связь"
            ],
            source_url="https://serpukhov.ru/safety/druzhina",
            tags=["безопасность", "сообщества", "малый бюджет"]
        )
        
        # 2. Подольск — цифровизация госуслуг
        self.cases["podolsk_digital"] = CityCase(
            id="podolsk_digital",
            city_name="Подольск",
            region="Московская область",
            population=312000,
            year=2024,
            domain=KnowledgeDomain.GOVERNANCE,
            problem_description="Долгое ожидание в очереди, бюрократия, низкое доверие",
            problem_severity="medium",
            problem_vectors=["ЧВ", "УБ"],
            solution_description="Цифровизация госуслуг и МФЦ",
            solution_actions=[
                "Перевод 90% услуг в электронный вид",
                "Внедрение системы электронной очереди",
                "Обучение сотрудников",
                "Портал обратной связи"
            ],
            solution_cost_million_rub=45,
            solution_duration_months=18,
            outcome=SolutionOutcome.SUCCESS,
            outcome_metrics={"ЧВ": 0.25, "УБ": 0.15},
            lessons_learned=[
                "Цифровизация сильно повышает доверие",
                "Важно обучение персонала",
                "Нужна простая и понятная система"
            ],
            pitfalls=[
                "Сопротивление сотрудников",
                "Проблемы с интеграцией систем"
            ],
            success_factors=[
                "Политическая воля главы",
                "Хороший IT-подрядчик",
                "Обратная связь от жителей"
            ],
            source_url="https://podolsk.ru/digital",
            tags=["цифровизация", "доверие", "госуслуги"]
        )
        
        # 3. Зарайск — налоговые льготы
        self.cases["zaraysk_tax"] = CityCase(
            id="zaraysk_tax",
            city_name="Зарайск",
            region="Московская область",
            population=42000,
            year=2023,
            domain=KnowledgeDomain.ECONOMY,
            problem_description="Отток бизнеса, закрытие предприятий, безработица",
            problem_severity="critical",
            problem_vectors=["ТФ", "УБ"],
            solution_description="Налоговые каникулы для МСП и льготы для новых инвесторов",
            solution_actions=[
                "Освобождение от налога на имущество на 3 года",
                "Снижение ставки УСН до 5%",
                "Создание инвестиционного портала",
                "Сопровождение инвесторов"
            ],
            solution_cost_million_rub=8.0,
            solution_duration_months=12,
            outcome=SolutionOutcome.SUCCESS,
            outcome_metrics={"ТФ": 0.6, "УБ": 0.2},
            lessons_learned=[
                "Налоговые льготы работают даже в малых городах",
                "Важно не только дать льготы, но и сопровождать",
                "Эффект виден через 6-9 месяцев"
            ],
            pitfalls=[
                "Временное снижение налоговых поступлений",
                "Нужен контроль, чтобы льготы не уходили 'мимо'"
            ],
            success_factors=[
                "Личное участие главы",
                "Быстрое принятие решений",
                "Прозрачность для бизнеса"
            ],
            source_url="https://zaraysk.ru/economy",
            tags=["экономика", "бизнес", "налоги", "инвестиции"]
        )
        
        # 4. Воскресенск — инициативное бюджетирование
        self.cases["voskresensk_budget"] = CityCase(
            id="voskresensk_budget",
            city_name="Воскресенск",
            region="Московская область",
            population=95000,
            year=2024,
            domain=KnowledgeDomain.GOVERNANCE,
            problem_description="Низкое доверие к власти, жалобы на благоустройство",
            problem_severity="medium",
            problem_vectors=["ЧВ", "УБ"],
            solution_description="Программа инициативного бюджетирования «Наш двор»",
            solution_actions=[
                "Конкурс проектов благоустройства от жителей",
                "Софинансирование (город 70%, жители 30%)",
                "Обучение ТОСов",
                "Публичное голосование"
            ],
            solution_cost_million_rub=15,
            solution_duration_months=12,
            outcome=SolutionOutcome.SUCCESS,
            outcome_metrics={"ЧВ": 0.35, "УБ": 0.25},
            lessons_learned=[
                "Жители готовы софинансировать, когда видят контроль",
                "Конкурс создаёт здоровую конкуренцию",
                "Прозрачность голосования — ключ к доверию"
            ],
            pitfalls=[
                "Сложно вовлечь пассивных жителей",
                "Нужна качественная модерация проектов"
            ],
            success_factors=[
                "Пилот в 5 дворах для демонстрации",
                "Активная информационная кампания",
                "Быстрая реализация проектов-победителей"
            ],
            source_url="https://voskresensk.ru/budget",
            tags=["бюджет", "благоустройство", "сообщества"]
        )
        
        # 5. Коломна — фестиваль (успех)
        self.cases["kolomna_festival"] = CityCase(
            id="kolomna_festival",
            city_name="Коломна",
            region="Московская область",
            population=144589,
            year=2024,
            domain=KnowledgeDomain.CULTURE,
            problem_description="Низкая туристическая привлекательность, отток молодёжи",
            problem_severity="medium",
            problem_vectors=["УБ", "ЧВ", "ТФ"],
            solution_description="Фестиваль «Ледовая Коломна» и развитие туристического бренда",
            solution_actions=[
                "Создание фестиваля ледовых скульптур",
                "Информационная кампания в соцсетях",
                "Сотрудничество с туроператорами",
                "Развитие городской навигации"
            ],
            solution_cost_million_rub=12,
            solution_duration_months=8,
            outcome=SolutionOutcome.SUCCESS,
            outcome_metrics={"УБ": 0.3, "ТФ": 0.2, "ЧВ": 0.2},
            lessons_learned=[
                "Уникальное событие создаёт идентичность",
                "Соцсети — главный канал для молодёжи",
                "Важно вовлекать местный бизнес"
            ],
            pitfalls=[
                "Зависимость от погоды",
                "Нужно ежегодное обновление формата"
            ],
            success_factors=[
                "Уникальная концепция",
                "Поддержка губернатора",
                "Волонтёры и сообщества"
            ],
            source_url="https://kolomna.ru/festival",
            tags=["культура", "туризм", "бренд", "события"]
        )
        
        # 6. Озёры — провал с вывозом мусора
        self.cases["ozery_garbage"] = CityCase(
            id="ozery_garbage",
            city_name="Озёры",
            region="Московская область",
            population=25000,
            year=2023,
            domain=KnowledgeDomain.ECOLOGY,
            problem_description="Жалобы на вывоз мусора, переполненные контейнеры",
            problem_severity="medium",
            problem_vectors=["УБ", "ЧВ"],
            solution_description="Смена подрядчика без конкурса (попытка быстрого решения)",
            solution_actions=[
                "Расторжение контракта с текущим подрядчиком",
                "Назначение нового без конкурса",
                "Повышение тарифа для жителей"
            ],
            solution_cost_million_rub=0.5,
            solution_duration_months=3,
            outcome=SolutionOutcome.FAILURE,
            outcome_metrics={"УБ": -0.3, "ЧВ": -0.4},
            lessons_learned=[
                "Смена подрядчика без конкурса — коррупционные риски",
                "Повышение тарифа без улучшений — падение доверия",
                "Нужна прозрачная система"
            ],
            pitfalls=[
                "Нарушение законодательства",
                "Протесты жителей",
                "Ухудшение качества услуг"
            ],
            success_factors=[],
            source_url="https://ozery.ru/garbage",
            tags=["жкх", "мусор", "провал", "уроки"]
        )
        
        # 7. Кашира — камеры видеонаблюдения
        self.cases["kashira_cameras"] = CityCase(
            id="kashira_cameras",
            city_name="Кашира",
            region="Московская область",
            population=58000,
            year=2024,
            domain=KnowledgeDomain.SAFETY,
            problem_description="Рост краж, страх жителей",
            problem_severity="high",
            problem_vectors=["СБ"],
            solution_description="Установка 200 камер видеонаблюдения в проблемных районах",
            solution_actions=[
                "Установка камер на входах в подъезды",
                "Подключение к системе «Безопасный регион»",
                "Информирование жителей"
            ],
            solution_cost_million_rub=18,
            solution_duration_months=9,
            outcome=SolutionOutcome.SUCCESS,
            outcome_metrics={"СБ": 0.5, "ЧВ": 0.2},
            lessons_learned=[
                "Камеры работают, но не решают всё",
                "Важно информировать жителей о работе системы",
                "Нужно сопровождение и обслуживание"
            ],
            pitfalls=[
                "Ложное чувство безопасности",
                "Вандализм в отношении камер"
            ],
            success_factors=[
                "Интеграция с областной системой",
                "Видимые результаты (раскрытые преступления)"
            ],
            source_url="https://kashira.ru/safety",
            tags=["безопасность", "камеры", "технологии"]
        )
        
        # 8. Егорьевск — школа лидеров (социальный капитал)
        self.cases["egorievsk_leaders"] = CityCase(
            id="egorievsk_leaders",
            city_name="Егорьевск",
            region="Московская область",
            population=85000,
            year=2024,
            domain=KnowledgeDomain.SOCIAL,
            problem_description="Низкая гражданская активность, пассивные ТОСы",
            problem_severity="low",
            problem_vectors=["ЧВ"],
            solution_description="Школа городских лидеров — обучение активистов",
            solution_actions=[
                "Бесплатные курсы по проектному управлению",
                "Конкурс микрогрантов для выпускников",
                "Наставничество от депутатов",
                "Создание ассоциации ТОС"
            ],
            solution_cost_million_rub=3.0,
            solution_duration_months=12,
            outcome=SolutionOutcome.SUCCESS,
            outcome_metrics={"ЧВ": 0.4},
            lessons_learned=[
                "Обучение + гранты = рост активности",
                "Важно, чтобы выпускники видели реальные проекты",
                "Наставничество критически важно"
            ],
            pitfalls=[
                "Без финансирования проектов обучение бесполезно",
                "Высокий отсев"
            ],
            success_factors=[
                "Сильный координатор",
                "Реальные проекты выпускников",
                "Публичное признание"
            ],
            source_url="https://egorievsk.ru/leaders",
            tags=["сообщества", "обучение", "активисты"]
        )
        
        # ========== ПРИЧИННО-СЛЕДСТВЕННЫЕ ЦЕПОЧКИ ==========
        
        self.cause_effect_chains["poverty_to_crime"] = CauseEffectChain(
            id="poverty_to_crime",
            name="Бедность → Преступность",
            description="Экономическая депрессия ведёт к росту преступности, которая усугубляет экономику",
            domain=KnowledgeDomain.SAFETY,
            trigger="Рост безработицы > 10% за 6 месяцев",
            chain=[
                {"cause": "Закрытие предприятий", "effect": "Рост безработицы"},
                {"cause": "Рост безработицы", "effect": "Падение доходов населения"},
                {"cause": "Падение доходов", "effect": "Рост бытовой преступности"},
                {"cause": "Рост преступности", "effect": "Отток бизнеса"},
                {"cause": "Отток бизнеса", "effect": "Дальнейший рост безработицы (петля)"}
            ],
            reinforcing_factors=[
                "Слабая работа полиции",
                "Отсутствие соцподдержки",
                "Наркомания"
            ],
            breaking_points=[
                "Создание рабочих мест (экономика)",
                "Усиление патрулирования (безопасность)",
                "Социальная поддержка"
            ],
            examples=["Зарайск (до льгот)", "Воскресенск (пик кризиса)"],
            confidence=0.85
        )
        
        self.cause_effect_chains["mistrust_to_apathy"] = CauseEffectChain(
            id="mistrust_to_apathy",
            name="Недоверие → Апатия",
            description="Низкое доверие к власти приводит к пассивности, что закрепляет недоверие",
            domain=KnowledgeDomain.GOVERNANCE,
            trigger="Падение доверия ниже 40%",
            chain=[
                {"cause": "Непрозрачность решений", "effect": "Недоверие к власти"},
                {"cause": "Недоверие", "effect": "Низкая гражданская активность"},
                {"cause": "Низкая активность", "effect": "Отсутствие обратной связи"},
                {"cause": "Отсутствие обратной связи", "effect": "Ещё более непрозрачные решения"}
            ],
            reinforcing_factors=[
                "Коррупционные скандалы",
                "Игнорирование жалоб",
                "Формальные отписки"
            ],
            breaking_points=[
                "Прозрачность (открытые данные)",
                "Быстрая реакция на жалобы",
                "Инициативное бюджетирование"
            ],
            examples=["Воскресенск (до инициативного бюджета)", "Озёры (после провала с мусором)"],
            confidence=0.9
        )
        
        self.cause_effect_chains["good_roads_to_happiness"] = CauseEffectChain(
            id="good_roads_to_happiness",
            name="Хорошие дороги → Счастье",
            description="Качественная инфраструктура напрямую влияет на удовлетворённость жизнью",
            domain=KnowledgeDomain.INFRASTRUCTURE,
            trigger="Качество дорог < 3.0/6",
            chain=[
                {"cause": "Плохие дороги", "effect": "ДТП, пробки"},
                {"cause": "ДТП и пробки", "effect": "Стресс, опоздания"},
                {"cause": "Стресс", "effect": "Недовольство жизнью"},
                {"cause": "Недовольство", "effect": "Жалобы, отток жителей"}
            ],
            reinforcing_factors=[
                "Недофинансирование ремонта",
                "Неэффективные подрядчики",
                "Климат (частые заморозки-оттепели)"
            ],
            breaking_points=[
                "Капитальный ремонт (не ямочный)",
                "Долгосрочный план на 3-5 лет",
                "Общественный контроль качества"
            ],
            examples=["Подольск (после ремонта)", "Коломна (федеральная трасса)"],
            confidence=0.8
        )
        
        # ========== ЛУЧШИЕ ПРАКТИКИ ==========
        
        self.best_practices["safety_patrol_community"] = BestPractice(
            id="safety_patrol_community",
            name="Программа «Соседский дозор»",
            description="Вовлечение жителей в обеспечение безопасности через обучение и координацию",
            domain=KnowledgeDomain.SAFETY,
            target_vectors=["СБ", "ЧВ"],
            implementation_steps=[
                "1. Создать инициативную группу (5-10 активных жителей)",
                "2. Провести обучение (1-2 дня)",
                "3. Создать чаты домов/районов",
                "4. Установить камеры с доступом для жителей",
                "5. Запустить программу патрулирования",
                "6. Еженедельные отчёты и награды активистам"
            ],
            prerequisites=[
                "Готовность жителей участвовать",
                "Бюджет на камеры (от 500 тыс. ₽)",
                "Координатор от администрации"
            ],
            estimated_cost="Низкий",
            estimated_time_months=3,
            expected_impact={"СБ": 0.3, "ЧВ": 0.2},
            success_rate=0.85,
            cities_implemented=["Серпухов", "Коломна", "Кашира"],
            pitfalls=[
                "Без поддержки администрации быстро затухает",
                "Нужен постоянный координатор",
                "Важно не перегружать активистов"
            ],
            tags=["безопасность", "сообщества", "малый бюджет"]
        )
        
        self.best_practices["digital_services"] = BestPractice(
            id="digital_services",
            name="Цифровизация госуслуг",
            description="Перевод массовых услуг в электронный вид для экономии времени жителей",
            domain=KnowledgeDomain.GOVERNANCE,
            target_vectors=["ЧВ", "УБ"],
            implementation_steps=[
                "1. Аудит текущих услуг (100+ шт)",
                "2. Приоритизация по частоте обращения",
                "3. Разработка портала (3-6 месяцев)",
                "4. Обучение сотрудников МФЦ",
                "5. Информационная кампания",
                "6. Постоянная обратная связь"
            ],
            prerequisites=[
                "Бюджет от 20 млн ₽",
                "IT-подрядчик с опытом",
                "Политическая воля руководства"
            ],
            estimated_cost="Высокий",
            estimated_time_months=12,
            expected_impact={"ЧВ": 0.25, "УБ": 0.1},
            success_rate=0.75,
            cities_implemented=["Подольск", "Коломна", "Серпухов"],
            pitfalls=[
                "Сопротивление сотрудников",
                "Низкая цифровая грамотность пожилых",
                "Проблемы с интеграцией систем"
            ],
            tags=["цифровизация", "госуслуги", "доверие"]
        )
        
        self.best_practices["initiative_budgeting"] = BestPractice(
            id="initiative_budgeting",
            name="Инициативное бюджетирование",
            description="Жители выбирают проекты для благоустройства и софинансируют их",
            domain=KnowledgeDomain.GOVERNANCE,
            target_vectors=["ЧВ", "УБ"],
            implementation_steps=[
                "1. Утвердить положение (1 месяц)",
                "2. Выделить бюджет (от 5 млн ₽)",
                "3. Обучение ТОСов и активистов",
                "4. Приём заявок (2 месяца)",
                "5. Экспертиза проектов",
                "6. Голосование жителей",
                "7. Реализация проектов-победителей"
            ],
            prerequisites=[
                "Бюджет от 5 млн ₽",
                "Активные ТОСы",
                "Готовность к софинансированию"
            ],
            estimated_cost="Средний",
            estimated_time_months=9,
            expected_impact={"ЧВ": 0.35, "УБ": 0.2},
            success_rate=0.9,
            cities_implemented=["Воскресенск", "Коломна", "Зарайск"],
            pitfalls=[
                "Низкая явка на голосование",
                "Нереалистичные проекты",
                "Затягивание сроков"
            ],
            tags=["бюджет", "благоустройство", "сообщества"]
        )
        
        self.best_practices["tax_incentives_small_business"] = BestPractice(
            id="tax_incentives_small_business",
            name="Налоговые льготы для МСП",
            description="Снижение налоговой нагрузки для привлечения и удержания бизнеса",
            domain=KnowledgeDomain.ECONOMY,
            target_vectors=["ТФ", "УБ"],
            implementation_steps=[
                "1. Анализ текущей ситуации с бизнесом",
                "2. Разработка пакета льгот",
                "3. Согласование с областным минфином",
                "4. Принятие решения",
                "5. Информационная кампания",
                "6. Сопровождение инвесторов"
            ],
            prerequisites=[
                "Поддержка области",
                "Бюджетный резерв на выпадающие доходы",
                "Готовность быстро принимать решения"
            ],
            estimated_cost="Средний (выпадающие доходы)",
            estimated_time_months=6,
            expected_impact={"ТФ": 0.4, "УБ": 0.15},
            success_rate=0.8,
            cities_implemented=["Зарайск", "Серпухов"],
            pitfalls=[
                "Временное снижение налогов",
                "Риск злоупотреблений",
                "Неравенство с крупным бизнесом"
            ],
            tags=["экономика", "бизнес", "налоги", "инвестиции"]
        )
        
        self.best_practices["school_of_leaders"] = BestPractice(
            id="school_of_leaders",
            name="Школа городских лидеров",
            description="Обучение активистов проектному управлению с последующим грантовым конкурсом",
            domain=KnowledgeDomain.SOCIAL,
            target_vectors=["ЧВ"],
            implementation_steps=[
                "1. Разработка программы (1 месяц)",
                "2. Поиск преподавателей",
                "3. Набор 30-50 участников",
                "4. Проведение курса (2-3 месяца)",
                "5. Конкурс микрогрантов (до 100 тыс. ₽)",
                "6. Сопровождение проектов",
                "7. Церемония награждения"
            ],
            prerequisites=[
                "Бюджет от 2 млн ₽",
                "Преподаватели-практики",
                "Помещение для занятий"
            ],
            estimated_cost="Низкий",
            estimated_time_months=6,
            expected_impact={"ЧВ": 0.3},
            success_rate=0.85,
            cities_implemented=["Егорьевск", "Коломна"],
            pitfalls=[
                "Без грантов обучение бесполезно",
                "Высокий отсев (50%)",
                "Сложно измерить эффект"
            ],
            tags=["сообщества", "обучение", "активисты"]
        )
        
        self.best_practices["city_branding_festival"] = BestPractice(
            id="city_branding_festival",
            name="Фестиваль как драйвер туризма",
            description="Создание уникального ежегодного события для привлечения туристов и развития идентичности",
            domain=KnowledgeDomain.CULTURE,
            target_vectors=["УБ", "ТФ", "ЧВ"],
            implementation_steps=[
                "1. Поиск уникальной концепции",
                "2. Формирование оргкомитета",
                "3. Поиск спонсоров",
                "4. Информационная кампания (за 3 месяца)",
                "5. Проведение фестиваля",
                "6. Пост-релизы и анализ"
            ],
            prerequisites=[
                "Уникальная идея (связана с историей города)",
                "Бюджет от 5 млн ₽",
                "Поддержка губернатора"
            ],
            estimated_cost="Средний",
            estimated_time_months=8,
            expected_impact={"УБ": 0.25, "ТФ": 0.2, "ЧВ": 0.15},
            success_rate=0.7,
            cities_implemented=["Коломна", "Зарайск", "Серпухов"],
            pitfalls=[
                "Зависимость от погоды",
                "Быстрое выгорание формата",
                "Перекос в развлечения без пользы для жителей"
            ],
            tags=["культура", "туризм", "бренд", "события"]
        )
    
    # ==================== 1. ПОИСК ПОХОЖИХ КЕЙСОВ ====================
    
    async def find_similar_cases(self, 
                                   problem_description: str,
                                   domain: KnowledgeDomain = None,
                                   limit: int = 5) -> List[CityCase]:
        """
        Поиск похожих кейсов по описанию проблемы (семантический поиск)
        """
        if EMBEDDINGS_AVAILABLE and self.embedding_model and self.case_embeddings is not None:
            # Векторный поиск
            query_embedding = self.embedding_model.encode(problem_description)
            distances, indices = self.case_index.search(query_embedding.reshape(1, -1), limit)
            
            similar_cases = []
            for idx in indices[0]:
                if idx < len(self.case_ids):
                    case_id = self.case_ids[idx]
                    similar_cases.append(self.cases[case_id])
            return similar_cases
        else:
            # Fallback: поиск по ключевым словам
            return await self._keyword_search(problem_description, domain, limit)
    
    async def _keyword_search(self, text: str, domain: KnowledgeDomain, limit: int) -> List[CityCase]:
        """Поиск по ключевым словам (fallback)"""
        text_lower = text.lower()
        scored_cases = []
        
        for case in self.cases.values():
            if domain and case.domain != domain:
                continue
            
            score = 0
            # Поиск в описании проблемы
            if case.problem_description.lower() in text_lower or text_lower in case.problem_description.lower():
                score += 3
            
            # Поиск в тегах
            for tag in case.tags:
                if tag in text_lower:
                    score += 2
            
            # Поиск в решении
            if any(action.lower() in text_lower for action in case.solution_actions):
                score += 1
            
            if score > 0:
                scored_cases.append((score, case))
        
        scored_cases.sort(key=lambda x: x[0], reverse=True)
        return [case for _, case in scored_cases[:limit]]
    
    # ==================== 2. ПОИСК РЕШЕНИЙ ПО ПРОБЛЕМЕ ====================
    
    async def find_solutions_for_problem(self,
                                          problem_vectors: List[str],
                                          current_metrics: Dict[str, float],
                                          budget_million_rub: float = None) -> List[Dict]:
        """
        Поиск решений для текущей проблемы города
        """
        solutions = []
        
        for case in self.cases.values():
            # Проверяем, относится ли кейс к проблемным векторам
            if not any(v in case.problem_vectors for v in problem_vectors):
                continue
            
            # Проверяем, не слишком ли дорого
            if budget_million_rub and case.solution_cost_million_rub > budget_million_rub:
                continue
            
            # Оценка применимости
            applicability_score = await self._calculate_applicability(case, current_metrics)
            
            solutions.append({
                'case': case,
                'applicability_score': applicability_score,
                'expected_impact': case.outcome_metrics,
                'cost': case.solution_cost_million_rub,
                'duration_months': case.solution_duration_months,
                'success_rate': 1 if case.outcome == SolutionOutcome.SUCCESS else 0.5 if case.outcome == SolutionOutcome.PARTIAL else 0.2
            })
        
        # Сортируем по применимости
        solutions.sort(key=lambda x: x['applicability_score'], reverse=True)
        
        return solutions[:10]
    
    async def _calculate_applicability(self, case: CityCase, current_metrics: Dict[str, float]) -> float:
        """Расчёт применимости кейса к текущей ситуации"""
        score = 0.5  # база
        
        # Похожесть проблемных векторов
        common_vectors = set(case.problem_vectors) & set(current_metrics.keys())
        if common_vectors:
            score += 0.2 * len(common_vectors)
        
        # Успешность кейса
        if case.outcome == SolutionOutcome.SUCCESS:
            score += 0.2
        elif case.outcome == SolutionOutcome.PARTIAL:
            score += 0.1
        
        # Свежесть (более новые кейсы предпочтительнее)
        years_ago = datetime.now().year - case.year
        if years_ago <= 1:
            score += 0.1
        elif years_ago <= 3:
            score += 0.05
        
        return min(1.0, score)
    
    # ==================== 3. АНАЛИЗ ПРИЧИННО-СЛЕДСТВЕННЫХ ЦЕПОЧЕК ====================
    
    async def analyze_cause_effect(self, 
                                     trigger_event: str,
                                     domain: KnowledgeDomain = None) -> List[CauseEffectChain]:
        """
        Анализ причинно-следственных цепочек, которые могут запуститься
        """
        matching_chains = []
        
        for chain in self.cause_effect_chains.values():
            if domain and chain.domain != domain:
                continue
            
            # Проверяем, соответствует ли триггер
            if chain.trigger.lower() in trigger_event.lower() or trigger_event.lower() in chain.trigger.lower():
                matching_chains.append(chain)
        
        return matching_chains
    
    async def predict_consequences(self, 
                                    decision_description: str,
                                    affected_vectors: List[str]) -> List[Dict]:
        """
        Предсказание возможных последствий решения на основе похожих кейсов
        """
        consequences = []
        
        # Ищем похожие решения в кейсах
        for case in self.cases.values():
            # Проверяем пересечение векторов
            if not set(case.problem_vectors) & set(affected_vectors):
                continue
            
            # Проверяем схожесть описания
            similarity = await self._text_similarity(decision_description, case.solution_description)
            
            if similarity > 0.3:
                consequences.append({
                    'case': case,
                    'similarity': similarity,
                    'predicted_outcome': case.outcome.value,
                    'expected_metrics_change': case.outcome_metrics,
                    'lessons': case.lessons_learned,
                    'pitfalls': case.pitfalls
                })
        
        consequences.sort(key=lambda x: x['similarity'], reverse=True)
        return consequences[:5]
    
    async def _text_similarity(self, text1: str, text2: str) -> float:
        """Вычисление схожести текстов"""
        if EMBEDDINGS_AVAILABLE and self.embedding_model:
            emb1 = self.embedding_model.encode(text1)
            emb2 = self.embedding_model.encode(text2)
            from numpy.linalg import norm
            return float(np.dot(emb1, emb2) / (norm(emb1) * norm(emb2)))
        else:
            # Упрощённая версия — общие слова
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            if not words1 or not words2:
                return 0
            return len(words1 & words2) / len(words1 | words2)
    
    # ==================== 4. ЛУЧШИЕ ПРАКТИКИ ====================
    
    async def get_best_practices(self, 
                                   target_vector: str,
                                   budget: str = None) -> List[BestPractice]:
        """
        Получение лучших практик для целевого вектора
        """
        practices = []
        
        for practice in self.best_practices.values():
            if target_vector in practice.target_vectors:
                if budget and practice.estimated_cost != budget:
                    continue
                practices.append(practice)
        
        # Сортируем по успешности
        practices.sort(key=lambda x: x.success_rate, reverse=True)
        
        return practices
    
    async def get_practice_details(self, practice_id: str) -> Optional[BestPractice]:
        """Детальная информация о практике"""
        return self.best_practices.get(practice_id)
    
    # ==================== 5. ДОБАВЛЕНИЕ НОВЫХ ЗНАНИЙ ====================
    
    async def add_case(self, case: CityCase):
        """Добавление нового кейса в банк знаний"""
        self.cases[case.id] = case
        logger.info(f"Добавлен кейс: {case.city_name} - {case.problem_description[:50]}")
        
        # Обновляем векторный индекс
        if EMBEDDINGS_AVAILABLE and self.embedding_model:
            self._rebuild_index()
    
    async def add_best_practice(self, practice: BestPractice):
        """Добавление новой лучшей практики"""
        self.best_practices[practice.id] = practice
        logger.info(f"Добавлена практика: {practice.name}")
    
    def _rebuild_index(self):
        """Перестроение векторного индекса"""
        if not EMBEDDINGS_AVAILABLE or not self.embedding_model:
            return
        
        texts = []
        self.case_ids = []
        
        for case_id, case in self.cases.items():
            text = f"{case.problem_description} {case.solution_description} {' '.join(case.tags)}"
            texts.append(text)
            self.case_ids.append(case_id)
        
        if texts:
            self.case_embeddings = self.embedding_model.encode(texts)
            dimension = self.case_embeddings.shape[1]
            self.case_index = faiss.IndexFlatL2(dimension)
            self.case_index.add(self.case_embeddings)
    
    # ==================== 6. СТАТИСТИКА ====================
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Статистика банка знаний"""
        return {
            'total_cases': len(self.cases),
            'by_outcome': {
                outcome.value: sum(1 for c in self.cases.values() if c.outcome == outcome)
                for outcome in SolutionOutcome
            },
            'by_domain': {
                domain.value: sum(1 for c in self.cases.values() if c.domain == domain)
                for domain in KnowledgeDomain
            },
            'total_practices': len(self.best_practices),
            'total_chains': len(self.cause_effect_chains),
            'avg_success_rate': sum(1 for c in self.cases.values() if c.outcome == SolutionOutcome.SUCCESS) / len(self.cases) if self.cases else 0,
            'cities_represented': list(set(c.city_name for c in self.cases.values()))
        }
    
    # ==================== 7. ДАШБОРД ====================
    
    async def get_knowledge_dashboard(self) -> Dict[str, Any]:
        """Дашборд банка знаний для мэра"""
        
        # Самые успешные практики
        top_practices = sorted(
            self.best_practices.values(),
            key=lambda x: x.success_rate,
            reverse=True
        )[:5]
        
        # Самые провальные кейсы (для уроков)
        failed_cases = [c for c in self.cases.values() if c.outcome == SolutionOutcome.FAILURE]
        
        # Популярные теги
        all_tags = []
        for case in self.cases.values():
            all_tags.extend(case.tags)
        from collections import Counter
        popular_tags = Counter(all_tags).most_common(10)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'city': self.city_name,
            'statistics': await self.get_statistics(),
            'top_practices': [
                {
                    'name': p.name,
                    'domain': p.domain.value,
                    'success_rate': f"{p.success_rate:.0%}",
                    'cities': p.cities_implemented[:3]
                }
                for p in top_practices
            ],
            'lessons_from_failures': [
                {
                    'city': c.city_name,
                    'problem': c.problem_description[:80],
                    'pitfalls': c.pitfalls[:2]
                }
                for c in failed_cases[:5]
            ],
            'popular_tags': [{'tag': tag, 'count': count} for tag, count in popular_tags],
            'recommended_practices': [
                {
                    'name': p.name,
                    'impact': p.expected_impact,
                    'cost': p.estimated_cost,
                    'time_months': p.estimated_time_months
                }
                for p in top_practices[:3]
            ]
        }


# ==================== ИНТЕГРАЦИЯ ====================

async def create_knowledge_bank(city_name: str) -> KnowledgeBank:
    """Фабричная функция"""
    return KnowledgeBank(city_name)


# ==================== ПРИМЕР ====================

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("🧪 Тестирование KnowledgeBank...")
        
        bank = KnowledgeBank("Коломна")
        
        # 1. Поиск похожих кейсов
        print("\n🔍 ПОИСК ПОХОЖИХ КЕЙСОВ:")
        print("  Проблема: 'Рост преступности, жители боятся гулять вечером'")
        
        similar = await bank.find_similar_cases("Рост преступности, жители боятся гулять вечером")
        for case in similar[:3]:
            print(f"    • {case.city_name}: {case.solution_description[:60]}...")
            print(f"      Результат: {case.outcome.value}, бюджет: {case.solution_cost_million_rub} млн ₽")
        
        # 2. Поиск решений
        print("\n💡 ПОИСК РЕШЕНИЙ ДЛЯ ТЕКУЩЕЙ СИТУАЦИИ:")
        print("  Векторы: ['СБ', 'ЧВ'], бюджет: 10 млн ₽")
        
        solutions = await bank.find_solutions_for_problem(
            problem_vectors=['СБ', 'ЧВ'],
            current_metrics={'СБ': 3.2, 'ЧВ': 3.0},
            budget_million_rub=10
        )
        
        for sol in solutions[:3]:
            case = sol['case']
            print(f"    • {case.city_name}: {case.solution_description[:60]}...")
            print(f"      Применимость: {sol['applicability_score']:.0%}, бюджет: {case.solution_cost_million_rub} млн ₽")
        
        # 3. Лучшие практики
        print("\n🏆 ЛУЧШИЕ ПРАКТИКИ ДЛЯ ВЕКТОРА 'ЧВ':")
        
        practices = await bank.get_best_practices(target_vector="ЧВ")
        for p in practices[:3]:
            print(f"    • {p.name}")
            print(f"      Ожидаемый эффект: {p.expected_impact}")
            print(f"      Успешность: {p.success_rate:.0%}, города: {', '.join(p.cities_implemented[:2])}")
        
        # 4. Анализ последствий
        print("\n🔮 ПРЕДСКАЗАНИЕ ПОСЛЕДСТВИЙ:")
        print("  Решение: 'Повысить налоги для бизнеса'")
        
        consequences = await bank.predict_consequences(
            decision_description="Повысить налоги для бизнеса",
            affected_vectors=['ТФ', 'ЧВ']
        )
        
        for cons in consequences[:3]:
            case = cons['case']
            print(f"    • Похоже на {case.city_name} (схожесть {cons['similarity']:.0%})")
            print(f"      Исход: {cons['predicted_outcome']}")
            if cons['pitfalls']:
                print(f"      Риски: {cons['pitfalls'][0][:60]}...")
        
        # 5. Дашборд
        print("\n📊 ДАШБОРД БАНКА ЗНАНИЙ:")
        dashboard = await bank.get_knowledge_dashboard()
        print(f"  Всего кейсов: {dashboard['statistics']['total_cases']}")
        print(f"  Успешных: {dashboard['statistics']['by_outcome']['success']}")
        print(f"  Провальных: {dashboard['statistics']['by_outcome']['failure']}")
        print(f"  Лучшая практика: {dashboard['top_practices'][0]['name'] if dashboard['top_practices'] else 'Нет'}")
        
        print("\n✅ Тест завершен")
    
    asyncio.run(demo())
