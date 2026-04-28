#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 9: ТРАБЛШУТЕР ГОРОДА (CITY TROUBLESHOOTER)
Инструмент стратегического и тактического управления кризисами

Основан на методологиях:
- DMAIC (Define, Measure, Analyze, Improve, Control)
- 5 Почему (5 Whys)
- Дерево проблем (Issue Tree)
- Матрица срочности/важности (Эйзенхауэр)
- Анализ первопричин (RCA - Root Cause Analysis)
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import hashlib
from collections import Counter

logger = logging.getLogger(__name__)


# ==================== МОДЕЛИ ДАННЫХ ====================

class ProblemSeverity(Enum):
    """Серьёзность проблемы"""
    CRITICAL = "critical"      # Чрезвычайная ситуация, требуется немедленное вмешательство
    HIGH = "high"              # Высокая, решение в течение 24 часов
    MEDIUM = "medium"          # Средняя, решение в течение недели
    LOW = "low"                # Низкая, плановое решение


class ProblemDomain(Enum):
    """Домен проблемы"""
    SAFETY = "safety"           # Безопасность
    ECONOMY = "economy"         # Экономика
    INFRASTRUCTURE = "infra"    # Инфраструктура
    SOCIAL = "social"           # Социальная сфера
    ECOLOGY = "ecology"         # Экология
    ADMIN = "admin"             # Административные процессы
    FINANCE = "finance"         # Финансы/бюджет
    REPUTATION = "reputation"   # Репутационные риски


class TroubleshootingPhase(Enum):
    """Этапы траблшутинга"""
    DETECT = "detect"       # Обнаружение проблемы
    DEFINE = "define"       # Определение и границы
    MEASURE = "measure"     # Сбор данных и измерение
    ANALYZE = "analyze"     # Анализ первопричин
    SOLVE = "solve"         # Выбор решения
    ACT = "act"             # Реализация
    CONTROL = "control"     # Контроль и предотвращение


@dataclass
class CityProblem:
    """Городская проблема для траблшутинга"""
    id: str
    title: str
    description: str
    severity: ProblemSeverity
    domain: ProblemDomain
    detected_at: datetime
    source: str  # откуда узнали: новости, обращения, метрики, ЛОМ
    symptoms: List[str]  # внешние проявления
    affected_vectors: List[str]  # какие векторы Мейстера затронуты
    current_score: float  # текущая оценка (0-1, где 1 - критично)
    
    # Статус
    status: str = "open"  # open/in_progress/resolved/closed
    assigned_to: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_summary: Optional[str] = None


@dataclass
class RootCause:
    """Первопричина проблемы"""
    id: str
    description: str
    depth: int  # глубина (1-5, где 5 - корень)
    evidence: List[str]  # доказательства
    confidence: float  # уверенность 0-1
    chain: List[str]  # цепочка "почему"


@dataclass
class SolutionOption:
    """Вариант решения проблемы"""
    id: str
    name: str
    description: str
    estimated_cost: float  # в млн ₽
    estimated_time: int  # в днях
    effectiveness: float  # 0-1, ожидаемая эффективность
    difficulty: float  # 0-1, сложность реализации
    risks: List[str]  # риски
    stakeholders: List[str]  # ответственные
    resources_needed: List[str]  # ресурсы
    expected_impact_on_metrics: Dict[str, float]  # влияние на метрики


@dataclass
class TroubleshootingSession:
    """Сессия траблшутинга по проблеме"""
    id: str
    problem: CityProblem
    phase: TroubleshootingPhase
    started_at: datetime
    updated_at: datetime
    
    # Данные анализа
    symptoms_list: List[str] = field(default_factory=list)
    data_collected: List[Dict] = field(default_factory=list)
    why_chain: List[str] = field(default_factory=list)  # цепочка 5 почему
    root_causes: List[RootCause] = field(default_factory=list)
    solution_options: List[SolutionOption] = field(default_factory=list)
    selected_solution: Optional[SolutionOption] = None
    
    # Реализация
    action_plan: List[Dict] = field(default_factory=list)  # пошаговый план
    control_metrics: List[Dict] = field(default_factory=list)  # метрики контроля
    status: str = "active"  # active/completed/abandoned


# ==================== ОСНОВНОЙ КЛАСС ====================

class CityTroubleshooter:
    """
    Траблшутер города — инструмент стратегии и тактики
    Помогает мэру быстро находить и устранять корневые причины проблем
    """
    
    def __init__(self, city_name: str, model=None, opinion_analyzer=None):
        self.city_name = city_name
        self.model = model  # ConfinementModel9
        self.opinion_analyzer = opinion_analyzer  # OpinionIntelligenceAnalyzer
        
        # Хранилище
        self.problems: Dict[str, CityProblem] = {}
        self.sessions: Dict[str, TroubleshootingSession] = {}
        self.resolved_problems_history: List[CityProblem] = []
        
        # База знаний решений
        self.solution_patterns = self._init_solution_patterns()
        
        # Шаблоны для быстрого траблшутинга
        self.problem_templates = self._init_problem_templates()
        
        logger.info(f"CityTroubleshooter инициализирован для города {city_name}")
    
    def _init_solution_patterns(self) -> Dict[str, List[Dict]]:
        """Инициализация базы знаний решений по типам проблем"""
        return {
            'safety_crime': [
                {
                    'name': 'Усиление патрулирования',
                    'description': 'Увеличение количества патрулей в проблемных районах',
                    'cost': 2.0,
                    'time_days': 3,
                    'effectiveness': 0.6,
                    'difficulty': 0.3,
                    'risks': ['Нехватка персонала', 'Высокие затраты на overtime']
                },
                {
                    'name': 'Установка камер видеонаблюдения',
                    'description': 'Монтаж системы видеонаблюдения в местах с высокой преступностью',
                    'cost': 10.0,
                    'time_days': 30,
                    'effectiveness': 0.8,
                    'difficulty': 0.5,
                    'risks': ['Вандализм', 'Технические неполадки']
                },
                {
                    'name': 'Программа "Соседский дозор"',
                    'description': 'Вовлечение жителей в обеспечение безопасности',
                    'cost': 0.5,
                    'time_days': 14,
                    'effectiveness': 0.7,
                    'difficulty': 0.4,
                    'risks': ['Низкая активность жителей', 'Ложные вызовы']
                }
            ],
            'economy_business_exodus': [
                {
                    'name': 'Налоговые каникулы для МСП',
                    'description': 'Временное освобождение от налогов для малого бизнеса',
                    'cost': 15.0,
                    'time_days': 7,
                    'effectiveness': 0.7,
                    'difficulty': 0.6,
                    'risks': ['Потеря бюджетных доходов', 'Недовольство крупного бизнеса']
                },
                {
                    'name': 'Создание ТОР (территория опережающего развития)',
                    'description': 'Особая экономическая зона с льготами для инвесторов',
                    'cost': 50.0,
                    'time_days': 180,
                    'effectiveness': 0.9,
                    'difficulty': 0.8,
                    'risks': ['Сложность согласования', 'Долгий запуск']
                },
                {
                    'name': 'Бизнес-акселератор и гранты',
                    'description': 'Программа поддержки стартапов и малого бизнеса',
                    'cost': 5.0,
                    'time_days': 60,
                    'effectiveness': 0.6,
                    'difficulty': 0.4,
                    'risks': ['Неэффективное использование средств']
                }
            ],
            'infrastructure_roads': [
                {
                    'name': 'Ямочный ремонт',
                    'description': 'Экстренный ремонт самых проблемных участков',
                    'cost': 3.0,
                    'time_days': 7,
                    'effectiveness': 0.5,
                    'difficulty': 0.2,
                    'risks': ['Временное решение, проблема вернётся']
                },
                {
                    'name': 'Капитальный ремонт дорог',
                    'description': 'Полная замена дорожного покрытия',
                    'cost': 50.0,
                    'time_days': 180,
                    'effectiveness': 0.9,
                    'difficulty': 0.7,
                    'risks': ['Перекрытие движения', 'Затягивание сроков']
                },
                {
                    'name': 'Программа "Наши дворы"',
                    'description': 'Комплексное благоустройство дворовых территорий',
                    'cost': 20.0,
                    'time_days': 90,
                    'effectiveness': 0.8,
                    'difficulty': 0.5,
                    'risks': ['Несогласованность с жителями']
                }
            ],
            'social_protests': [
                {
                    'name': 'Открытые встречи с жителями',
                    'description': 'Серия встреч администрации с активными гражданами',
                    'cost': 0.2,
                    'time_days': 3,
                    'effectiveness': 0.7,
                    'difficulty': 0.2,
                    'risks': ['Эскалация конфликта при плохой подготовке']
                },
                {
                    'name': 'Создание общественного совета',
                    'description': 'Постоянный орган для диалога с жителями',
                    'cost': 1.0,
                    'time_days': 30,
                    'effectiveness': 0.8,
                    'difficulty': 0.5,
                    'risks': ['Радикализация совета']
                },
                {
                    'name': 'Быстрые победы (quick wins)',
                    'description': 'Немедленное решение мелких проблем для снятия напряжения',
                    'cost': 0.5,
                    'time_days': 2,
                    'effectiveness': 0.6,
                    'difficulty': 0.1,
                    'risks': ['Может быть воспринято как подачка']
                }
            ],
            'reputation_crisis': [
                {
                    'name': 'Официальное опровержение',
                    'description': 'Публичное заявление с фактами и доказательствами',
                    'cost': 0.1,
                    'time_days': 1,
                    'effectiveness': 0.5,
                    'difficulty': 0.2,
                    'risks': ['Может усилить негатив']
                },
                {
                    'name': 'Привлечение лояльных ЛОМ',
                    'description': 'Работа с лидерами общественного мнения для контрпропаганды',
                    'cost': 0.5,
                    'time_days': 3,
                    'effectiveness': 0.7,
                    'difficulty': 0.4,
                    'risks': ['ЛОМ могут отказаться']
                },
                {
                    'name': 'Информационная кампания',
                    'description': 'Системная работа по улучшению имиджа',
                    'cost': 5.0,
                    'time_days': 60,
                    'effectiveness': 0.8,
                    'difficulty': 0.6,
                    'risks': ['Может не дать быстрого эффекта']
                }
            ]
        }
    
    def _init_problem_templates(self) -> Dict[str, Dict]:
        """Шаблоны проблем для быстрого распознавания"""
        return {
            'crime_spike': {
                'title': 'Рост преступности',
                'domain': ProblemDomain.SAFETY,
                'vectors': ['СБ'],
                'symptoms': ['жалобы на безопасность', 'новости о преступлениях', 'страх жителей'],
                'severity': ProblemSeverity.HIGH,
                'suggested_actions': ['Усилить патрулирование', 'Установить камеры']
            },
            'business_closing': {
                'title': 'Закрытие предприятий',
                'domain': ProblemDomain.ECONOMY,
                'vectors': ['ТФ'],
                'symptoms': ['рост безработицы', 'снижение налогов', 'отток населения'],
                'severity': ProblemSeverity.HIGH,
                'suggested_actions': ['Встреча с бизнесом', 'Налоговые льготы']
            },
            'road_crisis': {
                'title': 'Критическое состояние дорог',
                'domain': ProblemDomain.INFRASTRUCTURE,
                'vectors': ['УБ', 'СБ'],
                'symptoms': ['жалобы на ямы', 'ДТП из-за дорог', 'аварии'],
                'severity': ProblemSeverity.MEDIUM,
                'suggested_actions': ['Ямочный ремонт', 'План капремонта']
            },
            'protest_risk': {
                'title': 'Риск протестной активности',
                'domain': ProblemDomain.SOCIAL,
                'vectors': ['ЧВ'],
                'symptoms': ['негатив в соцсетях', 'призывы к митингам', 'радикальные ЛОМ'],
                'severity': ProblemSeverity.HIGH,
                'suggested_actions': ['Встречи с активистами', 'Быстрые решения']
            },
            'budget_deficit': {
                'title': 'Дефицит бюджета',
                'domain': ProblemDomain.FINANCE,
                'vectors': ['ТФ'],
                'symptoms': ['нехватка средств', 'секвестр', 'долги'],
                'severity': ProblemSeverity.CRITICAL,
                'suggested_actions': ['Оптимизация расходов', 'Поиск допдоходов']
            },
            'reputation_attack': {
                'title': 'Информационная атака',
                'domain': ProblemDomain.REPUTATION,
                'vectors': ['ЧВ'],
                'symptoms': ['скоординированный негатив', 'фейки', 'радикальные нарративы'],
                'severity': ProblemSeverity.HIGH,
                'suggested_actions': ['Опровержение', 'Работа с ЛОМ', 'Инфокампания']
            }
        }
    
    # ==================== 1. ОБНАРУЖЕНИЕ ПРОБЛЕМ ====================
    
    async def detect_problems(self, metrics: Dict, social_data: List[Dict], 
                              opinion_results: Dict = None) -> List[CityProblem]:
        """
        Автоматическое обнаружение проблем на основе метрик и соцсетей
        """
        logger.info("Начинаю автоматическое обнаружение проблем...")
        detected_problems = []
        
        # 1. Анализ метрик (отклонения)
        for vector, score in metrics.items():
            if score <= 2.0:  # уровень 1-2 - критично
                problem = await self._create_problem_from_metric(vector, score)
                if problem:
                    detected_problems.append(problem)
        
        # 2. Анализ соцсетей (всплески негатива)
        social_problems = await self._detect_problems_from_social(social_data)
        detected_problems.extend(social_problems)
        
        # 3. Анализ результатов opinion intelligence
        if opinion_results:
            opinion_problems = self._detect_problems_from_opinion(opinion_results)
            detected_problems.extend(opinion_problems)
        
        # 4. Детекция аномалий во временных рядах
        anomaly_problems = await self._detect_anomalies()
        detected_problems.extend(anomaly_problems)
        
        # Дедупликация и сортировка по серьёзности
        detected_problems = self._deduplicate_problems(detected_problems)
        detected_problems.sort(key=lambda x: x.current_score, reverse=True)
        
        # Сохраняем в хранилище
        for problem in detected_problems:
            if problem.id not in self.problems:
                self.problems[problem.id] = problem
        
        logger.info(f"Обнаружено {len(detected_problems)} проблем")
        return detected_problems
    
    async def _create_problem_from_metric(self, vector: str, score: float) -> Optional[CityProblem]:
        """Создание проблемы на основе метрики"""
        vector_names = {'СБ': 'безопасности', 'ТФ': 'экономики', 'УБ': 'качества жизни', 'ЧВ': 'социального капитала'}
        
        severity = ProblemSeverity.CRITICAL if score <= 1.5 else ProblemSeverity.HIGH
        
        problem = CityProblem(
            id=f"prob_{vector}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            title=f"Критическое падение {vector_names.get(vector, vector)}",
            description=f"Показатель {vector_names.get(vector, vector)} упал до {score}/6",
            severity=severity,
            domain=self._map_vector_to_domain(vector),
            detected_at=datetime.now(),
            source="metrics_auto",
            symptoms=[f"Значение {vector} = {score}"],
            affected_vectors=[vector],
            current_score=1.0 - (score / 6)
        )
        
        return problem
    
    def _map_vector_to_domain(self, vector: str) -> ProblemDomain:
        """Маппинг вектора Мейстера на домен проблемы"""
        mapping = {
            'СБ': ProblemDomain.SAFETY,
            'ТФ': ProblemDomain.ECONOMY,
            'УБ': ProblemDomain.INFRASTRUCTURE,
            'ЧВ': ProblemDomain.SOCIAL
        }
        return mapping.get(vector, ProblemDomain.ADMIN)
    
    async def _detect_problems_from_social(self, social_data: List[Dict]) -> List[CityProblem]:
        """Обнаружение проблем из соцсетей"""
        problems = []
        
        # Группировка по времени (последние 2 часа)
        recent_posts = []
        cutoff = datetime.now() - timedelta(hours=2)
        
        for post in social_data:
            post_date = post.get('date', datetime.now())
            if isinstance(post_date, str):
                post_date = datetime.fromisoformat(post_date)
            if post_date >= cutoff:
                recent_posts.append(post)
        
        if len(recent_posts) < 10:
            return problems
        
        # Анализ частоты негатива
        negative_posts = [p for p in recent_posts if self._is_negative_post(p.get('text', ''))]
        
        if len(negative_posts) > 20:  # всплеск негатива
            # Кластеризация по темам
            themes = self._extract_negative_themes(negative_posts)
            
            for theme, count in themes.items():
                if count > 5:  # значимая тема
                    problem = CityProblem(
                        id=f"prob_social_{theme}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        title=f"Всплеск негатива: {theme}",
                        description=f"За последние 2 часа зафиксировано {count} негативных сообщений на тему '{theme}'",
                        severity=ProblemSeverity.HIGH,
                        domain=self._map_theme_to_domain(theme),
                        detected_at=datetime.now(),
                        source="social_auto",
                        symptoms=[f"{count} негативных постов о {theme}"],
                        affected_vectors=self._map_theme_to_vectors(theme),
                        current_score=min(1.0, count / 50)
                    )
                    problems.append(problem)
        
        return problems
    
    def _is_negative_post(self, text: str) -> bool:
        """Проверка на негативный пост"""
        negative_words = ['плохо', 'ужасно', 'возмутительно', 'позор', 'безобразие', 
                         'недоволен', 'кризис', 'проблема', 'авария', 'преступление']
        text_lower = text.lower()
        return any(word in text_lower for word in negative_words)
    
    def _extract_negative_themes(self, posts: List[Dict]) -> Dict[str, int]:
        """Извлечение тем негативных постов"""
        themes = Counter()
        
        theme_keywords = {
            'дороги': ['дорог', 'яма', 'асфальт', 'тротуар'],
            'жкх': ['жкх', 'коммуналк', 'отопление', 'вода'],
            'безопасность': ['преступ', 'ограблен', 'нападен', 'страх'],
            'транспорт': ['транспорт', 'автобус', 'маршрутк', 'пробк'],
            'мусор': ['мусор', 'свалк', 'гряз'],
            'власть': ['мэр', 'администрац', 'чиновник', 'власть'],
            'экология': ['экологи', 'завод', 'выброс', 'дым']
        }
        
        for post in posts:
            text = post.get('text', '').lower()
            for theme, keywords in theme_keywords.items():
                if any(kw in text for kw in keywords):
                    themes[theme] += 1
                    break
        
        return dict(themes)
    
    def _map_theme_to_domain(self, theme: str) -> ProblemDomain:
        """Маппинг темы на домен"""
        theme_domain = {
            'дороги': ProblemDomain.INFRASTRUCTURE,
            'жкх': ProblemDomain.INFRASTRUCTURE,
            'безопасность': ProblemDomain.SAFETY,
            'транспорт': ProblemDomain.INFRASTRUCTURE,
            'мусор': ProblemDomain.ECOLOGY,
            'власть': ProblemDomain.ADMIN,
            'экология': ProblemDomain.ECOLOGY
        }
        return theme_domain.get(theme, ProblemDomain.SOCIAL)
    
    def _map_theme_to_vectors(self, theme: str) -> List[str]:
        """Маппинг темы на векторы Мейстера"""
        theme_vectors = {
            'дороги': ['УБ', 'СБ'],
            'жкх': ['УБ'],
            'безопасность': ['СБ'],
            'транспорт': ['УБ', 'ТФ'],
            'мусор': ['УБ', 'ЭКОЛОГИЯ'],
            'власть': ['ЧВ'],
            'экология': ['УБ']
        }
        return theme_vectors.get(theme, ['УБ'])
    
    def _detect_problems_from_opinion(self, opinion_results: Dict) -> List[CityProblem]:
        """Обнаружение проблем из результатов opinion intelligence"""
        problems = []
        
        # Критические лидеры мнений
        critical_leaders = [l for l in opinion_results.get('opinion_leaders', []) 
                           if l.get('risk_level') == 'critical']
        
        if critical_leaders:
            problems.append(CityProblem(
                id=f"prob_leader_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                title="Критический лидер мнения с анти-административной позицией",
                description=f"Выявлен лидер мнения с высоким уровнем влияния и негативным отношением к администрации",
                severity=ProblemSeverity.HIGH,
                domain=ProblemDomain.REPUTATION,
                detected_at=datetime.now(),
                source="opinion_intelligence",
                symptoms=[f"Лидер: {critical_leaders[0].get('username', 'unknown')}"],
                affected_vectors=['ЧВ'],
                current_score=0.7
            ))
        
        # Информационные кампании
        campaigns = opinion_results.get('disinformation_campaigns', [])
        for campaign in campaigns:
            if campaign.get('threat_level') == 'critical':
                problems.append(CityProblem(
                    id=f"prob_campaign_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    title="Критическая информационная кампания",
                    description=campaign.get('name', 'Обнаружена скоординированная информационная атака'),
                    severity=ProblemSeverity.CRITICAL,
                    domain=ProblemDomain.REPUTATION,
                    detected_at=datetime.now(),
                    source="opinion_intelligence",
                    symptoms=[f"Кампания против {campaign.get('target', 'администрации')}"],
                    affected_vectors=['ЧВ'],
                    current_score=campaign.get('impact_score', 0.7)
                ))
        
        return problems
    
    async def _detect_anomalies(self) -> List[CityProblem]:
        """Детекция аномалий во временных рядах метрик"""
        # Здесь можно добавить более сложные алгоритмы
        # Например, обнаружение резких скачков или падений
        return []
    
    def _deduplicate_problems(self, problems: List[CityProblem]) -> List[CityProblem]:
        """Дедупликация похожих проблем"""
        unique = {}
        for p in problems:
            key = f"{p.title}_{p.domain.value}"
            if key not in unique or p.current_score > unique[key].current_score:
                unique[key] = p
        return list(unique.values())
    
    # ==================== 2. ДИАГНОСТИКА (5 ПОЧЕМУ) ====================
    
    async def diagnose_problem(self, problem_id: str) -> TroubleshootingSession:
        """
        Диагностика проблемы с использованием метода "5 почему"
        """
        problem = self.problems.get(problem_id)
        if not problem:
            raise ValueError(f"Проблема {problem_id} не найдена")
        
        # Создаём сессию траблшутинга
        session = TroubleshootingSession(
            id=f"ts_{problem_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            problem=problem,
            phase=TroubleshootingPhase.DEFINE,
            started_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Шаг 1: Уточняем симптомы
        session.symptoms_list = await self._expand_symptoms(problem)
        
        # Шаг 2: Метод "5 почему"
        session.why_chain = await self._five_whys(problem)
        
        # Шаг 3: Поиск первопричин
        session.root_causes = await self._find_root_causes(problem, session.why_chain)
        
        # Шаг 4: Генерация вариантов решений
        session.solution_options = await self._generate_solutions(problem, session.root_causes)
        
        session.phase = TroubleshootingPhase.ANALYZE
        session.updated_at = datetime.now()
        
        self.sessions[session.id] = session
        
        logger.info(f"Диагностика завершена для проблемы {problem.title}, найдено {len(session.root_causes)} первопричин")
        
        return session
    
    async def _expand_symptoms(self, problem: CityProblem) -> List[str]:
        """Расширение симптомов проблемы"""
        symptoms = problem.symptoms.copy()
        
        # Добавляем симптомы из связанных векторов
        for vector in problem.affected_vectors:
            vector_symptoms = self._get_vector_symptoms(vector)
            symptoms.extend(vector_symptoms)
        
        # Добавляем симптомы из мнения жителей
        if self.opinion_analyzer:
            # Здесь можно получить реальные жалобы из opinion analyzer
            pass
        
        return list(set(symptoms))
    
    def _get_vector_symptoms(self, vector: str) -> List[str]:
        """Симптомы по вектору Мейстера"""
        vector_symptoms = {
            'СБ': ['страх жителей', 'рост преступности', 'жалобы на безопасность'],
            'ТФ': ['падение доходов', 'рост безработицы', 'закрытие предприятий'],
            'УБ': ['ухудшение инфраструктуры', 'проблемы с экологией', 'недовольство качеством жизни'],
            'ЧВ': ['социальная напряжённость', 'снижение доверия к власти', 'конфликты']
        }
        return vector_symptoms.get(vector, ['общее ухудшение ситуации'])
    
    async def _five_whys(self, problem: CityProblem) -> List[str]:
        """
        Метод "5 почему" для поиска корневой причины
        """
        why_chain = []
        current_question = f"Почему {problem.description.lower()}?"
        
        # Базовые ответы для демо (в реальности - из базы знаний)
        demo_answers = {
            1: "Потому что есть системные проблемы в этой сфере",
            2: "Потому что не хватает ресурсов и внимания",
            3: "Потому что нет чёткой стратегии и приоритетов",
            4: "Потому что отсутствует системный анализ проблем",
            5: "Потому что нет культуры управления, основанной на данных"
        }
        
        for i in range(1, 6):
            why_chain.append(current_question)
            
            # В реальной системе здесь должен быть поиск в базе знаний
            # или анализ данных для получения ответа
            answer = demo_answers.get(i, "Требуется дополнительный анализ")
            why_chain.append(answer)
            
            current_question = f"Почему {answer.lower()[:-1]}?" if answer.endswith('?') else f"Почему {answer.lower()}?"
        
        return why_chain
    
    async def _find_root_causes(self, problem: CityProblem, why_chain: List[str]) -> List[RootCause]:
        """
        Поиск первопричин на основе цепочки "почему"
        """
        root_causes = []
        
        # Извлекаем последний ответ как потенциальную первопричину
        if len(why_chain) >= 2:
            last_answer = why_chain[-1]
            
            # Поиск доказательств
            evidence = await self._find_evidence_for_root_cause(problem, last_answer)
            
            root_cause = RootCause(
                id=f"rc_{problem.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                description=last_answer,
                depth=5,
                evidence=evidence,
                confidence=0.7 if evidence else 0.5,
                chain=why_chain
            )
            root_causes.append(root_cause)
        
        # Дополнительные первопричины из анализа связей Мейстера
        if self.model:
            model_causes = await self._find_model_root_causes(problem)
            root_causes.extend(model_causes)
        
        return root_causes
    
    async def _find_evidence_for_root_cause(self, problem: CityProblem, root_cause: str) -> List[str]:
        """Поиск доказательств для первопричины"""
        evidence = []
        
        # Проверка по метрикам
        if self.model and self.model.source_scores:
            for vector, score in self.model.source_scores.items():
                if vector in problem.affected_vectors and score < 3:
                    evidence.append(f"Метрика {vector} находится на низком уровне ({score}/6)")
        
        # Проверка по новостям (в реальности - из базы)
        evidence.append("Анализ данных подтверждает наличие системной проблемы")
        
        return evidence
    
    async def _find_model_root_causes(self, problem: CityProblem) -> List[RootCause]:
        """
        Поиск первопричин через конфайнт-модель Мейстера
        """
        root_causes = []
        
        if not self.model or not self.model.elements:
            return root_causes
        
        # Анализ петель, в которые вовлечены проблемные векторы
        for vector in problem.affected_vectors:
            # Находим элемент, соответствующий вектору
            element_id = {'СБ': 2, 'ТФ': 3, 'УБ': 4, 'ЧВ': 5}.get(vector, 2)
            element = self.model.elements.get(element_id)
            
            if element:
                # Причины, влияющие на этот элемент
                for cause_id in element.caused_by:
                    cause_elem = self.model.elements.get(cause_id)
                    if cause_elem:
                        root_causes.append(RootCause(
                            id=f"rc_model_{problem.id}_{cause_id}",
                            description=f"Системная проблема в элементе {cause_elem.name}: {cause_elem.description[:100]}",
                            depth=4,
                            evidence=["Выявлено конфайнт-моделью Мейстера"],
                            confidence=0.8,
                            chain=[f"Элемент {cause_elem.name} влияет на {element.name}"]
                        ))
        
        return root_causes
    
    # ==================== 3. ГЕНЕРАЦИЯ РЕШЕНИЙ ====================
    
    async def _generate_solutions(self, problem: CityProblem, root_causes: List[RootCause]) -> List[SolutionOption]:
        """
        Генерация вариантов решений на основе первопричин
        """
        solutions = []
        
        # 1. Решения из базы знаний по типу проблемы
        pattern_solutions = self._get_solutions_from_patterns(problem)
        solutions.extend(pattern_solutions)
        
        # 2. Решения, специфичные для первопричин
        for root_cause in root_causes:
            cause_solutions = await self._generate_solutions_for_root_cause(problem, root_cause)
            solutions.extend(cause_solutions)
        
        # 3. Решения на основе успешных кейсов других городов
        benchmark_solutions = await self._get_benchmark_solutions(problem)
        solutions.extend(benchmark_solutions)
        
        # Дедупликация и сортировка по эффективности
        solutions = self._deduplicate_solutions(solutions)
        solutions.sort(key=lambda x: x.effectiveness, reverse=True)
        
        return solutions[:5]  # топ-5
    
    def _get_solutions_from_patterns(self, problem: CityProblem) -> List[SolutionOption]:
        """Получение решений из базы знаний по шаблонам проблем"""
        solutions = []
        
        # Определяем тип проблемы по заголовку и симптомам
        problem_type = self._classify_problem_type(problem)
        
        patterns = self.solution_patterns.get(problem_type, [])
        
        for i, pattern in enumerate(patterns):
            solution = SolutionOption(
                id=f"sol_{problem.id}_{i}",
                name=pattern['name'],
                description=pattern['description'],
                estimated_cost=pattern['cost'],
                estimated_time=pattern['time_days'],
                effectiveness=pattern['effectiveness'],
                difficulty=pattern['difficulty'],
                risks=pattern['risks'],
                stakeholders=['Администрация', 'Профильный департамент'],
                resources_needed=['Бюджет', 'Персонал', 'Подрядчики'],
                expected_impact_on_metrics=self._estimate_metric_impact(problem, pattern)
            )
            solutions.append(solution)
        
        return solutions
    
    def _classify_problem_type(self, problem: CityProblem) -> str:
        """Классификация типа проблемы для выбора решения"""
        title_lower = problem.title.lower()
        
        if 'безопасн' in title_lower or 'преступ' in title_lower:
            return 'safety_crime'
        elif 'экономик' in title_lower or 'бизнес' in title_lower or 'предприят' in title_lower:
            return 'economy_business_exodus'
        elif 'дорог' in title_lower or 'инфраструктур' in title_lower:
            return 'infrastructure_roads'
        elif 'протест' in title_lower or 'митинг' in title_lower:
            return 'social_protests'
        elif 'репутац' in title_lower or 'информац' in title_lower or 'кампани' in title_lower:
            return 'reputation_crisis'
        else:
            return 'safety_crime'  # по умолчанию
    
    def _estimate_metric_impact(self, problem: CityProblem, pattern: Dict) -> Dict[str, float]:
        """Оценка влияния решения на метрики"""
        impact = {}
        for vector in problem.affected_vectors:
            impact[vector] = pattern['effectiveness'] * 0.5  # базовое влияние
        return impact
    
    async def _generate_solutions_for_root_cause(self, problem: CityProblem, root_cause: RootCause) -> List[SolutionOption]:
        """Генерация решений для конкретной первопричины"""
        # В реальной системе — более сложная логика
        # Здесь упрощённый вариант
        return []
    
    async def _get_benchmark_solutions(self, problem: CityProblem) -> List[SolutionOption]:
        """Получение решений из успешных кейсов других городов"""
        # В реальной системе — запрос к базе лучших практик
        return []
    
    def _deduplicate_solutions(self, solutions: List[SolutionOption]) -> List[SolutionOption]:
        """Дедупликация похожих решений"""
        unique = {}
        for s in solutions:
            key = s.name
            if key not in unique or s.effectiveness > unique[key].effectiveness:
                unique[key] = s
        return list(unique.values())
    
    # ==================== 4. ВЫБОР И РЕАЛИЗАЦИЯ РЕШЕНИЯ ====================
    
    async def select_solution(self, session_id: str, solution_id: str) -> TroubleshootingSession:
        """
        Выбор решения и создание плана реализации
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Сессия {session_id} не найдена")
        
        solution = next((s for s in session.solution_options if s.id == solution_id), None)
        if not solution:
            raise ValueError(f"Решение {solution_id} не найдено")
        
        session.selected_solution = solution
        session.phase = TroubleshootingPhase.SOLVE
        
        # Создаём пошаговый план реализации
        session.action_plan = await self._create_action_plan(session.problem, solution)
        
        # Создаём метрики контроля
        session.control_metrics = await self._create_control_metrics(session.problem, solution)
        
        session.updated_at = datetime.now()
        session.status = "active"
        
        logger.info(f"Выбрано решение '{solution.name}' для проблемы {session.problem.title}")
        
        return session
    
    async def _create_action_plan(self, problem: CityProblem, solution: SolutionOption) -> List[Dict]:
        """
        Создание детального пошагового плана реализации
        """
        action_plan = []
        
        # Типовой план для большинства решений
        phases = [
            {
                'phase': 'Подготовка',
                'steps': [
                    'Сформировать рабочую группу',
                    'Определить ответственных',
                    'Утвердить бюджет',
                    'Подготовить нормативную базу'
                ],
                'duration_days': max(1, int(solution.estimated_time * 0.1))
            },
            {
                'phase': 'Реализация',
                'steps': [
                    'Запустить пилотный проект',
                    'Провести обучение персонала',
                    'Начать основные работы',
                    'Мониторинг промежуточных результатов'
                ],
                'duration_days': int(solution.estimated_time * 0.7)
            },
            {
                'phase': 'Завершение',
                'steps': [
                    'Завершить основные работы',
                    'Провести приёмку',
                    'Подготовить отчёт',
                    'Информировать жителей'
                ],
                'duration_days': int(solution.estimated_time * 0.2)
            }
        ]
        
        for phase_info in phases:
            for step in phase_info['steps']:
                action_plan.append({
                    'step': step,
                    'phase': phase_info['phase'],
                    'duration_days': phase_info['duration_days'],
                    'responsible': solution.stakeholders[0] if solution.stakeholders else 'Администрация',
                    'status': 'pending',
                    'dependencies': []
                })
        
        return action_plan
    
    async def _create_control_metrics(self, problem: CityProblem, solution: SolutionOption) -> List[Dict]:
        """
        Создание метрик для контроля эффективности решения
        """
        control_metrics = []
        
        for vector in problem.affected_vectors:
            control_metrics.append({
                'metric': f"Уровень {vector}",
                'target': 5.0,  # целевое значение
                'current': problem.current_score,
                'measurement_frequency': 'daily',
                'threshold_warning': 4.0,
                'threshold_critical': 3.0
            })
        
        # Добавляем специфические метрики
        if problem.domain == ProblemDomain.SAFETY:
            control_metrics.append({
                'metric': 'Количество преступлений',
                'target': 'снижение на 30%',
                'current': 'базовый уровень',
                'measurement_frequency': 'weekly'
            })
        elif problem.domain == ProblemDomain.REPUTATION:
            control_metrics.append({
                'metric': 'Индекс доверия к администрации',
                'target': 'повышение на 15%',
                'current': 'текущий уровень',
                'measurement_frequency': 'daily'
            })
        
        return control_metrics
    
    # ==================== 5. КОНТРОЛЬ И ОТЧЁТНОСТЬ ====================
    
    async def get_problem_status(self, problem_id: str) -> Dict[str, Any]:
        """Получение статуса проблемы"""
        problem = self.problems.get(problem_id)
        if not problem:
            return {'error': 'Problem not found'}
        
        sessions = [s for s in self.sessions.values() if s.problem.id == problem_id]
        active_session = sessions[0] if sessions else None
        
        return {
            'problem': {
                'id': problem.id,
                'title': problem.title,
                'severity': problem.severity.value,
                'status': problem.status,
                'detected_at': problem.detected_at.isoformat(),
                'resolved_at': problem.resolved_at.isoformat() if problem.resolved_at else None
            },
            'active_session': {
                'id': active_session.id if active_session else None,
                'phase': active_session.phase.value if active_session else None,
                'root_causes': [rc.description for rc in active_session.root_causes] if active_session else [],
                'selected_solution': active_session.selected_solution.name if active_session and active_session.selected_solution else None,
                'progress': self._calculate_progress(active_session) if active_session else 0
            } if active_session else None
        }
    
    def _calculate_progress(self, session: TroubleshootingSession) -> float:
        """Расчёт прогресса по сессии"""
        phase_progress = {
            TroubleshootingPhase.DETECT: 0.1,
            TroubleshootingPhase.DEFINE: 0.2,
            TroubleshootingPhase.MEASURE: 0.3,
            TroubleshootingPhase.ANALYZE: 0.5,
            TroubleshootingPhase.SOLVE: 0.7,
            TroubleshootingPhase.ACT: 0.9,
            TroubleshootingPhase.CONTROL: 1.0
        }
        return phase_progress.get(session.phase, 0.0)
    
    async def generate_troubleshooting_report(self, problem_id: str) -> Dict[str, Any]:
        """
        Генерация полного отчёта по траблшутингу проблемы
        """
        problem = self.problems.get(problem_id)
        if not problem:
            return {'error': 'Problem not found'}
        
        sessions = [s for s in self.sessions.values() if s.problem.id == problem_id]
        session = sessions[0] if sessions else None
        
        if not session:
            return {'error': 'No troubleshooting session found'}
        
        return {
            'problem_summary': {
                'id': problem.id,
                'title': problem.title,
                'description': problem.description,
                'severity': problem.severity.value,
                'detected_at': problem.detected_at.isoformat(),
                'source': problem.source,
                'affected_vectors': problem.affected_vectors
            },
            'diagnosis': {
                'symptoms': session.symptoms_list,
                'five_whys': session.why_chain,
                'root_causes': [
                    {
                        'description': rc.description,
                        'confidence': rc.confidence,
                        'evidence': rc.evidence
                    }
                    for rc in session.root_causes
                ]
            },
            'solutions': [
                {
                    'name': s.name,
                    'description': s.description,
                    'cost_million_rub': s.estimated_cost,
                    'time_days': s.estimated_time,
                    'effectiveness': s.effectiveness,
                    'difficulty': s.difficulty,
                    'risks': s.risks,
                    'is_selected': session.selected_solution and session.selected_solution.id == s.id
                }
                for s in session.solution_options
            ],
            'action_plan': session.action_plan,
            'control_metrics': session.control_metrics,
            'recommendations': self._generate_recommendations(session)
        }
    
    def _generate_recommendations(self, session: TroubleshootingSession) -> List[str]:
        """Генерация рекомендаций на основе анализа"""
        recommendations = []
        
        if session.root_causes:
            recommendations.append(f"🔍 Основная первопричина: {session.root_causes[0].description}")
        
        if session.selected_solution:
            recommendations.append(f"✅ Рекомендуемое решение: {session.selected_solution.name}")
            recommendations.append(f"📅 Ожидаемый срок реализации: {session.selected_solution.estimated_time} дней")
            recommendations.append(f"💰 Ориентировочный бюджет: {session.selected_solution.estimated_cost} млн ₽")
        
        recommendations.append("📊 Контрольные метрики: отслеживайте изменения ежедневно")
        recommendations.append("🔄 При отсутствии улучшений через 30 дней — пересмотрите решение")
        
        return recommendations
    
    # ==================== 6. ПРИОРИТЕТИЗАЦИЯ ПРОБЛЕМ ====================
    
    async def prioritize_problems(self) -> List[Dict[str, Any]]:
        """
        Приоритизация всех активных проблем по матрице Эйзенхауэра
        (срочность × важность)
        """
        priorities = []
        
        for problem in self.problems.values():
            if problem.status != 'open':
                continue
            
            # Оценка срочности (на основе метрик и времени)
            urgency = problem.current_score * 0.6
            
            # Время с момента обнаружения (чем дольше, тем срочнее)
            hours_since = (datetime.now() - problem.detected_at).total_seconds() / 3600
            urgency += min(0.3, hours_since / 168)  # максимум +0.3 за неделю
            
            # Оценка важности
            importance = 0
            if problem.severity == ProblemSeverity.CRITICAL:
                importance = 0.9
            elif problem.severity == ProblemSeverity.HIGH:
                importance = 0.7
            elif problem.severity == ProblemSeverity.MEDIUM:
                importance = 0.4
            else:
                importance = 0.2
            
            # Матрица Эйзенхауэра
            if urgency > 0.6 and importance > 0.6:
                quadrant = "Срочно и важно (делать сейчас)"
                priority_score = 4
            elif urgency > 0.6 and importance <= 0.6:
                quadrant = "Срочно, но не важно (делегировать)"
                priority_score = 3
            elif urgency <= 0.6 and importance > 0.6:
                quadrant = "Важно, но не срочно (запланировать)"
                priority_score = 2
            else:
                quadrant = "Не срочно и не важно (отложить)"
                priority_score = 1
            
            priorities.append({
                'problem_id': problem.id,
                'title': problem.title,
                'severity': problem.severity.value,
                'urgency_score': urgency,
                'importance_score': importance,
                'quadrant': quadrant,
                'priority_score': priority_score,
                'recommended_action': self._get_quadrant_action(quadrant)
            })
        
        # Сортировка по приоритету
        priorities.sort(key=lambda x: x['priority_score'], reverse=True)
        
        return priorities
    
    def _get_quadrant_action(self, quadrant: str) -> str:
        """Действие для квадранта Эйзенхауэра"""
        actions = {
            "Срочно и важно (делать сейчас)": "Немедленно приступить к решению, личный контроль мэра",
            "Срочно, но не важно (делегировать)": "Делегировать профильному заместителю, установить дедлайн 24 часа",
            "Важно, но не срочно (запланировать)": "Включить в план работ на неделю, назначить ответственного",
            "Не срочно и не важно (отложить)": "Отложить, вернуться через месяц"
        }
        return actions.get(quadrant, "Требуется анализ")
    
    # ==================== 7. DASHBOARD ДЛЯ МЭРА ====================
    
    async def get_troubleshooter_dashboard(self) -> Dict[str, Any]:
        """
        Получение дашборда траблшутера для мэра
        """
        active_problems = [p for p in self.problems.values() if p.status == 'open']
        active_sessions = [s for s in self.sessions.values() if s.status == 'active']
        
        # Приоритизация
        priorities = await self.prioritize_problems()
        
        # Статистика
        stats = {
            'total_problems': len(self.problems),
            'active_problems': len(active_problems),
            'resolved_problems': len([p for p in self.problems.values() if p.status == 'resolved']),
            'critical_problems': sum(1 for p in active_problems if p.severity == ProblemSeverity.CRITICAL),
            'avg_resolution_time_days': self._calculate_avg_resolution_time(),
            'most_affected_domain': self._get_most_affected_domain()
        }
        
        # Топ-3 проблемы для немедленного решения
        urgent_problems = [p for p in priorities if 'Срочно и важно' in p['quadrant']][:3]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'city': self.city_name,
            'statistics': stats,
            'priorities': priorities[:10],  # топ-10
            'urgent_problems': urgent_problems,
            'active_sessions': [
                {
                    'id': s.id,
                    'problem_title': s.problem.title,
                    'phase': s.phase.value,
                    'progress': self._calculate_progress(s),
                    'has_solution': s.selected_solution is not None
                }
                for s in active_sessions
            ],
            'recently_resolved': [
                {
                    'title': p.title,
                    'resolved_at': p.resolved_at.isoformat() if p.resolved_at else None,
                    'summary': p.resolution_summary
                }
                for p in self.resolved_problems_history[-5:]
            ]
        }
    
    def _calculate_avg_resolution_time(self) -> float:
        """Расчёт среднего времени решения проблем"""
        resolved = [p for p in self.problems.values() if p.resolved_at]
        if not resolved:
            return 0.0
        
        total_seconds = sum((p.resolved_at - p.detected_at).total_seconds() for p in resolved)
        avg_days = total_seconds / len(resolved) / 86400
        return round(avg_days, 1)
    
    def _get_most_affected_domain(self) -> str:
        """Определение самого проблемного домена"""
        domain_count = Counter()
        for p in self.problems.values():
            domain_count[p.domain.value] += 1
        return domain_count.most_common(1)[0][0] if domain_count else "none"
    
    # ==================== 8. ЗАКРЫТИЕ ПРОБЛЕМЫ ====================
    
    async def resolve_problem(self, problem_id: str, resolution_summary: str) -> CityProblem:
        """
        Закрытие проблемы после решения
        """
        problem = self.problems.get(problem_id)
        if not problem:
            raise ValueError(f"Проблема {problem_id} не найдена")
        
        problem.status = 'resolved'
        problem.resolved_at = datetime.now()
        problem.resolution_summary = resolution_summary
        
        # Перемещаем в историю
        self.resolved_problems_history.append(problem)
        
        # Обновляем сессию
        for session in self.sessions.values():
            if session.problem.id == problem_id:
                session.status = 'completed'
                session.phase = TroubleshootingPhase.CONTROL
        
        logger.info(f"Проблема '{problem.title}' решена. Сводка: {resolution_summary[:100]}")
        
        return problem


# ==================== ИНТЕГРАЦИЯ С ОСНОВНЫМ ПРИЛОЖЕНИЕМ ====================

async def create_city_troubleshooter(city_name: str, model=None, opinion_analyzer=None) -> CityTroubleshooter:
    """Фабричная функция для создания траблшутера"""
    return CityTroubleshooter(city_name, model, opinion_analyzer)


# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("🧪 Тестирование CityTroubleshooter...")
        
        # Создаём траблшутер
        troubleshooter = CityTroubleshooter("Коломна")
        
        # Симулируем метрики города
        test_metrics = {'СБ': 2.8, 'ТФ': 3.5, 'УБ': 4.0, 'ЧВ': 3.2}
        
        # Обнаруживаем проблемы
        problems = await troubleshooter.detect_problems(test_metrics, [])
        
        print(f"\n📊 ОБНАРУЖЕННЫЕ ПРОБЛЕМЫ:")
        for p in problems:
            print(f"  • {p.title} (серьёзность: {p.severity.value})")
        
        if problems:
            # Диагностируем первую проблему
            session = await troubleshooter.diagnose_problem(problems[0].id)
            
            print(f"\n🔍 ДИАГНОСТИКА ПРОБЛЕМЫ:")
            print(f"  Симптомы: {', '.join(session.symptoms_list[:3])}")
            print(f"  Первопричины: {session.root_causes[0].description if session.root_causes else 'не определены'}")
            
            if session.solution_options:
                print(f"\n💡 ВАРИАНТЫ РЕШЕНИЙ:")
                for sol in session.solution_options[:3]:
                    print(f"  • {sol.name} — эффективность {sol.effectiveness:.0%}, {sol.estimated_time} дней, {sol.estimated_cost} млн ₽")
        
        # Приоритизация
        priorities = await troubleshooter.prioritize_problems()
        
        print(f"\n🎯 ПРИОРИТЕТЫ:")
        for p in priorities[:3]:
            print(f"  • {p['title']} — {p['quadrant']}")
        
        print("\n✅ Тест завершен")
    
    asyncio.run(demo())
