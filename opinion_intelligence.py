#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 8: АНАЛИЗ ОБЩЕСТВЕННОГО МНЕНИЯ И ИНФОРМАЦИОННЫХ УГРОЗ
Выявляет лидеров общественного мнения (ЛОМ), радикальных пользователей,
отслеживает формирование нарративов и обнаруживает информационные диверсии

Основано на методах:
- Анализ социальных графов для выявления ЛОМ [citation:1]
- NLP для детекции радикального и экстремистского контента [citation:2][citation:5][citation:7]
- Обнаружение скоординированных информационных кампаний [citation:3][citation:10]
- Анализ тональности и сдвигов в общественных настроениях [citation:5][citation:8]
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import logging
import json
import hashlib
import networkx as nx
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Настройка логирования
logger = logging.getLogger(__name__)


# ==================== МОДЕЛИ ДАННЫХ ====================

@dataclass
class OpinionLeader:
    """Лидер общественного мнения (ЛОМ)"""
    user_id: str
    username: str
    name: str
    influence_score: float          # 0-1, общий индекс влияния
    reach: int                      # охват (подписчики/друзья)
    engagement_rate: float          # вовлечённость (лайки/комментарии на пост)
    trust_score: float              # 0-1, уровень доверия к пользователю
    sentiment_towards_admin: float  # -1 (негатив) до +1 (позитив)
    main_topics: List[str]          # основные темы, которые поднимает
    community_id: int               # ID сообщества, в котором активен
    posts_count: int
    first_seen: datetime
    last_active: datetime
    risk_level: str = "low"         # low/medium/high/critical
    is_radical: bool = False        # радикально настроен против администрации


@dataclass
class RadicalUser:
    """Радикально настроенный пользователь"""
    user_id: str
    username: str
    radical_score: float            # 0-1, степень радикальности
    sentiment_score: float          # -1 до +1 (отрицательный = против власти)
    hate_speech_score: float        # 0-1, уровень агрессии/ненависти
    call_to_action_score: float     # 0-1, призывы к действиям
    threat_level: str               # low/medium/high/critical
    target_entities: List[str]      # против кого направлена агрессия
    keywords: List[str]             # характерные ключевые слова
    posts: List[Dict]               # подозрительные посты
    networks: List[str]             # связи с другими радикалами


@dataclass
class Narrative:
    """Общественный нарратив (мнение, тренд)"""
    id: str
    title: str
    description: str
    keywords: List[str]
    sentiment: float                # -1 до +1
    volume: int                     # количество упоминаний
    velocity: float                 # скорость распространения (упоминаний/час)
    trend: str                      # rising/stable/declining
    dominant_vector: str            # СБ/ТФ/УБ/ЧВ
    main_actors: List[str]          # ключевые авторы
    timeline: List[Dict]            # хронология
    first_seen: datetime
    last_seen: datetime
    is_artificial: bool = False     # искусственно созданный (инфоатака)


@dataclass
class DisinformationCampaign:
    """Информационная диверсия/кампания"""
    id: str
    name: str
    start_date: datetime
    end_date: Optional[datetime]
    target: str                     # против чего направлена
    narratives: List[Narrative]     # используемые нарративы
    actors: List[Dict]              # участники (боты/координаторы)
    scale: int                      # количество участников
    reach_estimate: int             # оценочный охват
    impact_score: float             # 0-1, оценка влияния
    coordination_level: float       # 0-1, уровень скоординированности
    threat_level: str               # low/medium/high/critical
    evidence: List[Dict]            # доказательства
    detected_at: datetime
    status: str = "active"          # active/mitigated/ended


# ==================== КОНФИГУРАЦИЯ ====================

class OpinionIntelligenceConfig:
    """Конфигурация модуля анализа общественного мнения"""
    
    # Ключевые слова для детекции радикального контента
    RADICAL_KEYWORDS = {
        'high': [
            'свергнуть', 'революция', 'бунт', 'восстание', 'сопротивление',
            'террор', 'насилие', 'оружие', 'убить', 'сжечь', 'разрушить',
            'захватить', 'ликвидировать', 'снести', 'уничтожить'
        ],
        'medium': [
            'протест', 'митинг', 'забастовка', 'блокировать', 'перекрыть',
            'импичмент', 'отставка', 'коррупция', 'воруют', 'преступление',
            'беспредел', 'произвол', 'беззаконие'
        ],
        'low': [
            'недоволен', 'возмущен', 'позор', 'безобразие', 'хамство',
            'несправедливость', 'обман', 'лгут', 'бездарно'
        ]
    }
    
    # Таргет-сущности (против кого направлен негатив)
    TARGET_ENTITIES = {
        'mayor': ['мэр', 'глава', 'градоначальник', 'администрация'],
        'administration': ['администрация', 'власть', 'чиновник', 'мэрия'],
        'police': ['полиция', 'мвд', 'полицейский', 'овд'],
        'deputies': ['депутат', 'гордума', 'совет'],
        'specific_person': []  # заполняется динамически
    }
    
    # Признаки скоординированной кампании
    COORDINATION_SIGNALS = {
        'same_text': 0.8,          # одинаковый текст в разных аккаунтах
        'burst_activity': 0.7,     # всплеск активности в одно время
        'hashtag_coordination': 0.6, # скоординированные хештеги
        'network_similarity': 0.75,  # похожая сетевая структура
        'reply_chain': 0.65         # цепочки согласованных ответов
    }


# ==================== ОСНОВНОЙ КЛАСС ====================

class OpinionIntelligenceAnalyzer:
    """
    Анализатор общественного мнения для городской администрации
    Выявляет ЛОМ, радикалов, нарративы и информационные атаки
    """
    
    def __init__(self, city_name: str, config: OpinionIntelligenceConfig = None):
        self.city_name = city_name
        self.config = config or OpinionIntelligenceConfig()
        
        # Хранилища данных
        self.opinion_leaders: Dict[str, OpinionLeader] = {}
        self.radical_users: Dict[str, RadicalUser] = {}
        self.narratives: Dict[str, Narrative] = {}
        self.campaigns: Dict[str, DisinformationCampaign] = {}
        
        # Кэши для анализа
        self._user_activity_cache = {}
        self._network_graph = nx.DiGraph()
        self._post_hashes = set()  # для детекции одинаковых постов
        
        # Временные метки последних анализов
        self.last_leaders_update = None
        self.last_radical_update = None
        self.last_narratives_update = None
        
        # Компараторы для детекции координации
        self.vectorizer = TfidfVectorizer(max_features=100, stop_words='russian')
        
        logger.info(f"OpinionIntelligenceAnalyzer инициализирован для города {city_name}")
    
    # ==================== 1. ВЫЯВЛЕНИЕ ЛИДЕРОВ ОБЩЕСТВЕННОГО МНЕНИЯ ====================
    
    async def detect_opinion_leaders(self, social_data: List[Dict]) -> List[OpinionLeader]:
        """
        Выявление лидеров общественного мнения на основе анализа социального графа
        и метрик влияния [citation:1][citation:5]
        
        Args:
            social_data: список постов/комментариев с метаданными
            
        Returns:
            список лидеров общественного мнения
        """
        logger.info("Начинаю выявление лидеров общественного мнения...")
        
        # 1. Строим социальный граф (кто кому отвечает/репостит)
        self._build_social_graph(social_data)
        
        # 2. Вычисляем метрики PageRank для определения влиятельности
        pagerank = nx.pagerank(self._network_graph, alpha=0.85)
        
        # 3. Анализируем активность и вовлечённость пользователей
        user_metrics = self._calculate_user_metrics(social_data)
        
        # 4. Определяем лидеров
        leaders = []
        
        for user_id, metrics in user_metrics.items():
            # Комбинированный индекс влияния
            influence_score = (
                pagerank.get(user_id, 0) * 0.35 +
                metrics.get('engagement_rate', 0) * 0.25 +
                (metrics.get('reach', 0) / max(1000, metrics.get('reach', 1))) * 0.20 +
                metrics.get('activity_score', 0) * 0.20
            )
            
            # Фильтруем только значимых (top 5%)
            if influence_score > 0.05 and metrics.get('posts_count', 0) > 5:
                # Определяем отношение к администрации
                sentiment = await self._analyze_sentiment_towards_admin(user_id, social_data)
                
                # Анализируем основные темы
                topics = self._extract_user_topics(user_id, social_data)
                
                leader = OpinionLeader(
                    user_id=user_id,
                    username=metrics.get('username', user_id),
                    name=metrics.get('name', ''),
                    influence_score=influence_score,
                    reach=metrics.get('reach', 0),
                    engagement_rate=metrics.get('engagement_rate', 0),
                    trust_score=self._calculate_trust_score(user_id, social_data),
                    sentiment_towards_admin=sentiment,
                    main_topics=topics[:5],
                    community_id=metrics.get('community_id', 0),
                    posts_count=metrics.get('posts_count', 0),
                    first_seen=metrics.get('first_seen', datetime.now()),
                    last_active=metrics.get('last_active', datetime.now()),
                    risk_level=self._assess_leader_risk(sentiment, influence_score),
                    is_radical=sentiment < -0.6 or metrics.get('radical_signals', 0) > 3
                )
                
                leaders.append(leader)
                self.opinion_leaders[user_id] = leader
        
        # Сортируем по влиянию
        leaders.sort(key=lambda x: x.influence_score, reverse=True)
        
        logger.info(f"Выявлено {len(leaders)} лидеров общественного мнения")
        self.last_leaders_update = datetime.now()
        
        return leaders
    
    def _build_social_graph(self, social_data: List[Dict]):
        """Построение социального графа на основе взаимодействий [citation:1]"""
        self._network_graph = nx.DiGraph()
        
        for post in social_data:
            author = post.get('author_id')
            if not author:
                continue
            
            # Добавляем узел автора
            self._network_graph.add_node(author)
            
            # Добавляем связи через репосты
            if post.get('repost_of'):
                repost_of = post['repost_of']
                self._network_graph.add_node(repost_of)
                self._network_graph.add_edge(repost_of, author, weight=0.8, type='repost')
            
            # Добавляем связи через упоминания
            mentions = self._extract_mentions(post.get('text', ''))
            for mentioned in mentions:
                self._network_graph.add_node(mentioned)
                self._network_graph.add_edge(author, mentioned, weight=0.6, type='mention')
            
            # Добавляем связи через ответы
            if post.get('reply_to'):
                reply_to = post['reply_to']
                self._network_graph.add_node(reply_to)
                self._network_graph.add_edge(reply_to, author, weight=0.9, type='reply')
    
    def _extract_mentions(self, text: str) -> List[str]:
        """Извлечение упоминаний (@username) из текста"""
        pattern = r'@(\w+)'
        return re.findall(pattern, text)
    
    def _calculate_user_metrics(self, social_data: List[Dict]) -> Dict[str, Dict]:
        """Расчёт метрик пользователей"""
        metrics = defaultdict(lambda: {
            'posts_count': 0,
            'likes_received': 0,
            'comments_received': 0,
            'reposts_received': 0,
            'reach': 0,
            'first_seen': datetime.now(),
            'last_active': None,
            'engagement_rate': 0,
            'activity_score': 0
        })
        
        for post in social_data:
            author = post.get('author_id')
            if not author:
                continue
            
            metrics[author]['posts_count'] += 1
            metrics[author]['likes_received'] += post.get('likes', 0)
            metrics[author]['comments_received'] += post.get('comments', 0)
            metrics[author]['reposts_received'] += post.get('reposts', 0)
            
            # Охват = подписчики (если есть в данных)
            metrics[author]['reach'] = max(metrics[author]['reach'], post.get('followers', 0))
            
            # Временные метки
            post_date = post.get('date', datetime.now())
            if isinstance(post_date, str):
                post_date = datetime.fromisoformat(post_date)
            
            if post_date < metrics[author]['first_seen']:
                metrics[author]['first_seen'] = post_date
            if not metrics[author]['last_active'] or post_date > metrics[author]['last_active']:
                metrics[author]['last_active'] = post_date
            
            metrics[author]['username'] = post.get('author_username', author)
            metrics[author]['name'] = post.get('author_name', '')
        
        # Расчёт производных метрик
        for user_id, data in metrics.items():
            if data['posts_count'] > 0:
                total_engagement = data['likes_received'] + data['comments_received'] * 2 + data['reposts_received'] * 3
                data['engagement_rate'] = min(1.0, total_engagement / (data['posts_count'] * 100))
                data['activity_score'] = min(1.0, data['posts_count'] / 50)  # 50 постов = 1.0
        
        return dict(metrics)
    
    async def _analyze_sentiment_towards_admin(self, user_id: str, social_data: List[Dict]) -> float:
        """
        Анализ отношения пользователя к администрации
        Возвращает -1 (крайне негативно) до +1 (крайне позитивно)
        """
        user_posts = [p for p in social_data if p.get('author_id') == user_id]
        
        if not user_posts:
            return 0.0
        
        # Ключевые слова для детекции отношения к власти
        negative_keywords = self.config.RADICAL_KEYWORDS['low'] + \
                           self.config.RADICAL_KEYWORDS['medium'] + \
                           ['мэр', 'власть', 'администрация', 'чиновник']
        
        positive_keywords = ['спасибо', 'молодец', 'отлично', 'хорошо', 'доволен', 'помогли']
        
        negative_count = 0
        positive_count = 0
        
        for post in user_posts:
            text = post.get('text', '').lower()
            
            # Проверяем, относится ли пост к администрации
            if not any(kw in text for kw in ['мэр', 'власть', 'админ', 'город', self.city_name.lower()]):
                continue
            
            if any(kw in text for kw in negative_keywords):
                negative_count += 1
            if any(kw in text for kw in positive_keywords):
                positive_count += 1
        
        total = negative_count + positive_count
        if total == 0:
            return 0.0
        
        return (positive_count - negative_count) / total
    
    def _calculate_trust_score(self, user_id: str, social_data: List[Dict]) -> float:
        """Расчёт индекса доверия к пользователю"""
        user_posts = [p for p in social_data if p.get('author_id') == user_id]
        
        if not user_posts:
            return 0.5
        
        # Факторы доверия
        factors = {
            'account_age': min(1.0, len(user_posts) / 100),  # чем больше постов, тем старше аккаунт
            'verification': 0.2 if any(p.get('verified', False) for p in user_posts) else 0,
            'consistency': self._check_consistency(user_posts),  # последовательность позиции
            'fact_check_ratio': 0.3  # можно добавить интеграцию с факт-чекингом
        }
        
        trust_score = sum(factors.values()) / len(factors)
        return min(1.0, max(0.0, trust_score))
    
    def _check_consistency(self, posts: List[Dict]) -> float:
        """Проверка последовательности мнений пользователя"""
        if len(posts) < 3:
            return 0.5
        
        # Простой метод: проверка смены тональности
        sentiments = []
        for post in posts:
            text = post.get('text', '')
            # Упрощённая тональность
            pos = sum(1 for w in ['хорошо', 'отлично', 'нравится'] if w in text.lower())
            neg = sum(1 for w in ['плохо', 'ужасно', 'не нравится'] if w in text.lower())
            sentiments.append(1 if pos > neg else -1 if neg > pos else 0)
        
        # Вычисляем количество смен
        changes = sum(1 for i in range(1, len(sentiments)) if sentiments[i] != sentiments[i-1])
        consistency = 1 - (changes / len(sentiments))
        
        return max(0.0, min(1.0, consistency))
    
    def _extract_user_topics(self, user_id: str, social_data: List[Dict]) -> List[str]:
        """Извлечение основных тем пользователя"""
        user_posts = [p.get('text', '') for p in social_data if p.get('author_id') == user_id]
        
        if not user_posts:
            return []
        
        # Простая кластеризация ключевых слов
        all_words = ' '.join(user_posts).lower().split()
        word_freq = Counter([w for w in all_words if len(w) > 4])
        
        # Фильтруем стоп-слова
        stop_words = {'этот', 'также', 'который', 'находиться', 'является', 'можно', 'нужно'}
        
        topics = []
        for word, count in word_freq.most_common(10):
            if word not in stop_words and count > 2:
                topics.append(word)
        
        return topics
    
    def _assess_leader_risk(self, sentiment: float, influence: float) -> str:
        """Оценка уровня риска от лидера мнения"""
        if sentiment < -0.7 and influence > 0.3:
            return "critical"
        elif sentiment < -0.5 and influence > 0.2:
            return "high"
        elif sentiment < -0.3 and influence > 0.15:
            return "medium"
        else:
            return "low"
    
    # ==================== 2. ВЫЯВЛЕНИЕ РАДИКАЛЬНЫХ ПОЛЬЗОВАТЕЛЕЙ ====================
    
    async def detect_radical_users(self, social_data: List[Dict]) -> List[RadicalUser]:
        """
        Выявление радикально настроенных пользователей
        на основе NLP-анализа контента и поведенческих паттернов [citation:2][citation:5][citation:6]
        
        Args:
            social_data: список постов/комментариев
            
        Returns:
            список радикальных пользователей
        """
        logger.info("Начинаю выявление радикальных пользователей...")
        
        radical_users = []
        
        # Группируем посты по пользователям
        user_posts = defaultdict(list)
        for post in social_data:
            author = post.get('author_id')
            if author:
                user_posts[author].append(post)
        
        for user_id, posts in user_posts.items():
            radical_score = 0.0
            hate_speech_score = 0.0
            call_to_action_score = 0.0
            target_entities = []
            keywords = []
            suspicious_posts = []
            
            for post in posts:
                text = post.get('text', '')
                
                # Анализ радикальности текста
                text_radical_score, text_keywords = self._analyze_radical_text(text)
                radical_score += text_radical_score
                keywords.extend(text_keywords)
                
                # Анализ призывов к действию
                cta_score, cta_text = self._detect_call_to_action(text)
                call_to_action_score += cta_score
                if cta_score > 0.5:
                    suspicious_posts.append({'text': cta_text, 'type': 'call_to_action', 'score': cta_score})
                
                # Анализ ненавистнических высказываний
                hate_score, hate_targets = self._detect_hate_speech(text)
                hate_speech_score += hate_score
                target_entities.extend(hate_targets)
                if hate_score > 0.5:
                    suspicious_posts.append({'text': text[:200], 'type': 'hate_speech', 'score': hate_score})
            
            # Нормализация
            post_count = len(posts)
            if post_count > 0:
                radical_score = min(1.0, radical_score / post_count)
                call_to_action_score = min(1.0, call_to_action_score / post_count)
                hate_speech_score = min(1.0, hate_speech_score / post_count)
            
            # Сентимент анализ по отношению к администрации
            sentiment = await self._analyze_sentiment_towards_admin(user_id, social_data)
            
            # Определяем уровень угрозы
            threat_level = self._determine_threat_level(
                radical_score, call_to_action_score, hate_speech_score, sentiment
            )
            
            # Если пользователь достаточно радикален
            if radical_score > 0.3 or call_to_action_score > 0.2 or hate_speech_score > 0.4:
                radical_user = RadicalUser(
                    user_id=user_id,
                    username=posts[0].get('author_username', user_id),
                    radical_score=radical_score,
                    sentiment_score=sentiment,
                    hate_speech_score=hate_speech_score,
                    call_to_action_score=call_to_action_score,
                    threat_level=threat_level,
                    target_entities=list(set(target_entities)),
                    keywords=list(set(keywords))[:10],
                    posts=suspicious_posts[:10],
                    networks=self._find_radical_networks(user_id, social_data)
                )
                
                radical_users.append(radical_user)
                self.radical_users[user_id] = radical_user
        
        # Сортируем по степени радикальности
        radical_users.sort(key=lambda x: x.radical_score + x.call_to_action_score, reverse=True)
        
        logger.info(f"Выявлено {len(radical_users)} радикальных пользователей, "
                   f"из них критических: {sum(1 for u in radical_users if u.threat_level == 'critical')}")
        
        self.last_radical_update = datetime.now()
        
        return radical_users
    
    def _analyze_radical_text(self, text: str) -> Tuple[float, List[str]]:
        """
        Анализ текста на радикальность
        Возвращает (оценка радикальности, список ключевых слов)
        """
        text_lower = text.lower()
        found_keywords = []
        score = 0.0
        
        # Проверка по уровням радикальности
        for level, keywords in self.config.RADICAL_KEYWORDS.items():
            level_weight = {'high': 1.0, 'medium': 0.6, 'low': 0.3}[level]
            
            for kw in keywords:
                if kw in text_lower:
                    found_keywords.append(kw)
                    score += level_weight
        
        # Нормализация (макс 1.0)
        score = min(1.0, score / 3)
        
        return score, list(set(found_keywords))
    
    def _detect_call_to_action(self, text: str) -> Tuple[float, str]:
        """
        Детекция призывов к действию
        Возвращает (оценка, текст призыва)
        """
        text_lower = text.lower()
        
        # Паттерны призывов
        cta_patterns = [
            (r'(?:давайте|пора|нужно|должны|обязаны)\s+(\w+)', 0.7),
            (r'(?:выйти|пойти|собраться|организовать)\s+(\w+)', 0.8),
            (r'(?:требуем|требуется|необходимо)\s+(\w+)', 0.6),
            (r'(?:перепост|репост|распространить|расшарить)', 0.5),
            (r'(?:блокировать|перекрыть|захватить|занять)', 0.9)
        ]
        
        score = 0.0
        matched_text = ""
        
        for pattern, weight in cta_patterns:
            match = re.search(pattern, text_lower)
            if match:
                score = max(score, weight)
                matched_text = match.group(0) if match.groups() else text[:100]
        
        return score, matched_text
    
    def _detect_hate_speech(self, text: str) -> Tuple[float, List[str]]:
        """
        Детекция ненавистнических высказываний
        Возвращает (оценка, список таргетов)
        """
        text_lower = text.lower()
        targets = []
        score = 0.0
        
        # Проверка по таргет-сущностям
        for target, keywords in self.config.TARGET_ENTITIES.items():
            for kw in keywords:
                if kw in text_lower:
                    targets.append(target)
                    score += 0.5
        
        # Проверка агрессивной лексики
        aggressive_words = ['сволочь', 'тварь', 'ублюдок', 'мразь', 'предатель']
        for word in aggressive_words:
            if word in text_lower:
                score += 0.3
        
        # Проверка дегуманизации
        dehumanization = ['эти люди', 'они', 'их', 'такие как они']
        for phrase in dehumanization:
            if phrase in text_lower and ('власть' in text_lower or 'чиновник' in text_lower):
                score += 0.4
        
        score = min(1.0, score)
        
        return score, list(set(targets))
    
    def _determine_threat_level(self, radical: float, cta: float, hate: float, sentiment: float) -> str:
        """Определение уровня угрозы"""
        if radical > 0.7 or cta > 0.6 or (hate > 0.7 and sentiment < -0.5):
            return "critical"
        elif radical > 0.5 or cta > 0.4 or hate > 0.5:
            return "high"
        elif radical > 0.3 or cta > 0.2 or hate > 0.3:
            return "medium"
        else:
            return "low"
    
    def _find_radical_networks(self, user_id: str, social_data: List[Dict]) -> List[str]:
        """Поиск связей радикального пользователя с другими радикалами"""
        connections = []
        
        # Ищем взаимодействия с другими пользователями
        for post in social_data:
            if post.get('author_id') == user_id:
                # Репосты радикального контента
                if post.get('repost_of'):
                    connections.append(f"reposted_from_{post['repost_of']}")
                
                # Ответы радикалам
                if post.get('reply_to'):
                    connections.append(f"replied_to_{post['reply_to']}")
                
                # Упоминания
                mentions = self._extract_mentions(post.get('text', ''))
                for mention in mentions:
                    connections.append(f"mentioned_{mention}")
        
        return list(set(connections))
    
    # ==================== 3. ВЫЯВЛЕНИЕ НАРРАТИВОВ И ОБЩЕСТВЕННЫХ МНЕНИЙ ====================
    
    async def detect_narratives(self, social_data: List[Dict], hours_back: int = 24) -> List[Narrative]:
        """
        Выявление формирующихся общественных нарративов и трендов
        на основе кластеризации текстов и анализа частоты [citation:5][citation:8]
        
        Args:
            social_data: список постов/комментариев
            hours_back: временной горизонт анализа
            
        Returns:
            список активных нарративов
        """
        logger.info("Начинаю выявление общественных нарративов...")
        
        # Фильтруем данные за указанный период
        cutoff = datetime.now() - timedelta(hours=hours_back)
        recent_posts = []
        
        for post in social_data:
            post_date = post.get('date', datetime.now())
            if isinstance(post_date, str):
                post_date = datetime.fromisoformat(post_date)
            if post_date >= cutoff:
                recent_posts.append(post)
        
        if len(recent_posts) < 10:
            logger.warning("Недостаточно данных для анализа нарративов")
            return []
        
        # Извлекаем тексты
        texts = [p.get('text', '') for p in recent_posts if p.get('text')]
        
        # Векторизация и кластеризация
        try:
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            
            # Кластеризация DBSCAN
            clustering = DBSCAN(eps=0.5, min_samples=3, metric='cosine')
            clusters = clustering.fit_predict(tfidf_matrix.toarray())
            
            # Анализ каждого кластера (нарратива)
            narratives = []
            
            for cluster_id in set(clusters):
                if cluster_id == -1:  # шум
                    continue
                
                # Посты в этом кластере
                cluster_indices = [i for i, c in enumerate(clusters) if c == cluster_id]
                cluster_texts = [texts[i] for i in cluster_indices]
                cluster_posts = [recent_posts[i] for i in cluster_indices]
                
                # Извлекаем ключевые слова
                keywords = self._extract_keywords_from_texts(cluster_texts)
                
                # Анализ тональности нарратива
                sentiment = await self._analyze_narrative_sentiment(cluster_posts)
                
                # Определяем доминирующий вектор Мейстера
                dominant_vector = self._classify_narrative_vector(cluster_texts)
                
                # Анализ скорости распространения
                velocity = self._calculate_velocity(cluster_posts)
                
                # Тренд
                trend = self._determine_trend(velocity, len(cluster_posts))
                
                # Основные авторы
                main_actors = self._get_main_actors(cluster_posts, limit=5)
                
                # Проверка на искусственность (инфоатака)
                is_artificial = await self._detect_artificial_narrative(cluster_posts)
                
                narrative = Narrative(
                    id=f"narr_{hashlib.md5(''.join(keywords).encode()).hexdigest()[:8]}",
                    title=self._generate_narrative_title(keywords, sentiment),
                    description=' '.join(keywords[:10]),
                    keywords=keywords[:10],
                    sentiment=sentiment,
                    volume=len(cluster_posts),
                    velocity=velocity,
                    trend=trend,
                    dominant_vector=dominant_vector,
                    main_actors=main_actors,
                    timeline=self._build_timeline(cluster_posts),
                    first_seen=min(p.get('date', datetime.now()) for p in cluster_posts),
                    last_seen=max(p.get('date', datetime.now()) for p in cluster_posts),
                    is_artificial=is_artificial
                )
                
                narratives.append(narrative)
                self.narratives[narrative.id] = narrative
            
            # Сортируем по объёму
            narratives.sort(key=lambda x: x.volume, reverse=True)
            
            logger.info(f"Выявлено {len(narratives)} активных нарративов")
            self.last_narratives_update = datetime.now()
            
            return narratives
            
        except Exception as e:
            logger.error(f"Ошибка при кластеризации нарративов: {e}")
            return []
    
    def _extract_keywords_from_texts(self, texts: List[str]) -> List[str]:
        """Извлечение ключевых слов из набора текстов"""
        # Простой метод: частотный анализ
        all_words = ' '.join(texts).lower().split()
        word_freq = Counter([w for w in all_words if len(w) > 4])
        
        # Фильтруем стоп-слова
        stop_words = {'этот', 'также', 'который', 'находиться', 'является', 'можно', 'нужно', 'очень', 'всегда'}
        
        keywords = []
        for word, count in word_freq.most_common(20):
            if word not in stop_words and count > 2:
                keywords.append(word)
        
        return keywords
    
    async def _analyze_narrative_sentiment(self, posts: List[Dict]) -> float:
        """Анализ общей тональности нарратива"""
        sentiments = []
        
        for post in posts:
            text = post.get('text', '')
            # Упрощённая тональность
            pos_count = sum(1 for w in ['хорошо', 'отлично', 'нравится', 'спасибо', 'здорово'] if w in text.lower())
            neg_count = sum(1 for w in ['плохо', 'ужасно', 'возмутительно', 'недоволен', 'позор'] if w in text.lower())
            
            if pos_count + neg_count > 0:
                sentiments.append((pos_count - neg_count) / (pos_count + neg_count))
            else:
                sentiments.append(0)
        
        if not sentiments:
            return 0.0
        
        return sum(sentiments) / len(sentiments)
    
    def _classify_narrative_vector(self, texts: List[str]) -> str:
        """Классификация нарратива по векторам Мейстера"""
        # Ключевые слова для каждого вектора
        vector_keywords = {
            'СБ': ['безопасн', 'страх', 'преступн', 'авария', 'опасн', 'дтп', 'чс'],
            'ТФ': ['деньг', 'бюджет', 'зарплат', 'работ', 'бизнес', 'экономик', 'налог'],
            'УБ': ['парк', 'благоустр', 'ремонт', 'дорог', 'школ', 'экологи', 'комфорт'],
            'ЧВ': ['сосед', 'сообщест', 'тос', 'волонтер', 'фестивал', 'праздник']
        }
        
        scores = defaultdict(int)
        all_text = ' '.join(texts).lower()
        
        for vector, keywords in vector_keywords.items():
            for kw in keywords:
                if kw in all_text:
                    scores[vector] += 1
        
        if not scores:
            return 'УБ'  # по умолчанию качество жизни
        
        return max(scores, key=scores.get)
    
    def _calculate_velocity(self, posts: List[Dict]) -> float:
        """Расчёт скорости распространения (упоминаний в час)"""
        if len(posts) < 2:
            return 0.0
        
        dates = []
        for p in posts:
            date = p.get('date', datetime.now())
            if isinstance(date, str):
                date = datetime.fromisoformat(date)
            dates.append(date)
        
        min_date = min(dates)
        max_date = max(dates)
        hours = (max_date - min_date).total_seconds() / 3600
        
        if hours < 0.1:
            return 0.0
        
        return len(posts) / hours
    
    def _determine_trend(self, velocity: float, volume: int) -> str:
        """Определение тренда нарратива"""
        if velocity > 10:
            return "rising"
        elif velocity > 2:
            return "stable"
        else:
            return "declining"
    
    def _get_main_actors(self, posts: List[Dict], limit: int = 5) -> List[str]:
        """Извлечение основных авторов нарратива"""
        authors = Counter()
        for post in posts:
            author = post.get('author_username') or post.get('author_id')
            if author:
                authors[author] += 1
        
        return [author for author, _ in authors.most_common(limit)]
    
    def _build_timeline(self, posts: List[Dict]) -> List[Dict]:
        """Построение временной шкалы нарратива"""
        timeline = defaultdict(int)
        
        for post in posts:
            date = post.get('date', datetime.now())
            if isinstance(date, str):
                date = datetime.fromisoformat(date)
            hour_key = date.strftime('%Y-%m-%d %H:00')
            timeline[hour_key] += 1
        
        return [{'time': k, 'count': v} for k, v in sorted(timeline.items())]
    
    async def _detect_artificial_narrative(self, posts: List[Dict]) -> bool:
        """Детекция искусственно созданного нарратива (инфоатака) [citation:3]"""
        if len(posts) < 5:
            return False
        
        # Признаки искусственности
        signals = []
        
        # 1. Слишком похожие тексты
        texts = [p.get('text', '') for p in posts]
        if len(texts) > 1:
            similarity = self._calculate_text_similarity(texts)
            if similarity > 0.7:
                signals.append(('high_similarity', 0.8))
        
        # 2. Всплеск активности в короткий промежуток
        dates = [p.get('date', datetime.now()) for p in posts]
        if len(dates) > 2:
            max_gap = max(dates) - min(dates)
            if max_gap.total_seconds() < 3600:  # менее часа
                signals.append(('burst_activity', 0.7))
        
        # 3. Много новых/недавно созданных аккаунтов
        new_accounts = sum(1 for p in posts if p.get('account_age_days', 999) < 30)
        if new_accounts > len(posts) * 0.5:
            signals.append(('new_accounts', 0.6))
        
        # 4. Отсутствие органических реакций (лайков/комментариев)
        avg_likes = sum(p.get('likes', 0) for p in posts) / len(posts)
        if avg_likes < 5:
            signals.append(('low_engagement', 0.5))
        
        # Вычисляем итоговый балл
        total_score = sum(score for _, score in signals)
        
        return total_score > 1.5
    
    def _calculate_text_similarity(self, texts: List[str]) -> float:
        """Расчёт средней схожести текстов"""
        if len(texts) < 2:
            return 0.0
        
        try:
            vectors = self.vectorizer.fit_transform(texts)
            similarities = cosine_similarity(vectors)
            
            # Берём среднее верхнетреугольной матрицы
            n = len(texts)
            total = 0
            count = 0
            for i in range(n):
                for j in range(i+1, n):
                    total += similarities[i, j]
                    count += 1
            
            return total / count if count > 0 else 0.0
        except:
            return 0.0
    
    def _generate_narrative_title(self, keywords: List[str], sentiment: float) -> str:
        """Генерация заголовка нарратива"""
        sentiment_word = "позитивный" if sentiment > 0.2 else "негативный" if sentiment < -0.2 else "нейтральный"
        
        if keywords:
            return f"{sentiment_word.capitalize()} нарратив: {keywords[0].capitalize()}"
        else:
            return f"{sentiment_word.capitalize()} общественный нарратив"
    
    # ==================== 4. ОБНАРУЖЕНИЕ ИНФОРМАЦИОННЫХ ДИВЕРСИЙ ====================
    
    async def detect_disinformation_campaigns(self, social_data: List[Dict]) -> List[DisinformationCampaign]:
        """
        Обнаружение скоординированных информационных кампаний (диверсий)
        на основе анализа паттернов координации [citation:3][citation:10]
        
        Args:
            social_data: список постов/комментариев
            
        Returns:
            список обнаруженных кампаний
        """
        logger.info("Начинаю обнаружение информационных диверсий...")
        
        campaigns = []
        
        # 1. Ищем скоординированные группы пользователей
        coordinated_groups = await self._find_coordinated_groups(social_data)
        
        # 2. Анализируем каждую группу
        for group_id, group_data in coordinated_groups.items():
            users = group_data['users']
            posts = group_data['posts']
            
            # Оцениваем уровень координации
            coordination_score = await self._assess_coordination_level(posts)
            
            # Выявляем используемые нарративы
            group_narratives = await self._extract_group_narratives(posts)
            
            # Определяем цель атаки
            target = self._identify_campaign_target(posts)
            
            # Оцениваем охват и влияние
            reach = sum(p.get('views', 0) for p in posts)
            impact_score = self._calculate_impact_score(posts, coordination_score)
            
            # Определяем уровень угрозы
            threat_level = self._assess_campaign_threat(impact_score, coordination_score, group_narratives)
            
            # Собираем доказательства
            evidence = self._collect_campaign_evidence(posts, users)
            
            campaign = DisinformationCampaign(
                id=f"camp_{group_id}",
                name=self._generate_campaign_name(target, group_narratives),
                start_date=min(p.get('date', datetime.now()) for p in posts),
                end_date=None,
                target=target,
                narratives=group_narratives,
                actors=[{'user_id': u, 'role': 'coordinator' if u in group_data.get('coordinators', []) else 'participant'} 
                       for u in users[:20]],
                scale=len(users),
                reach_estimate=reach,
                impact_score=impact_score,
                coordination_level=coordination_score,
                threat_level=threat_level,
                evidence=evidence,
                detected_at=datetime.now(),
                status="active"
            )
            
            campaigns.append(campaign)
            self.campaigns[campaign.id] = campaign
        
        # Сортируем по уровню угрозы
        threat_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        campaigns.sort(key=lambda x: threat_order.get(x.threat_level, 0), reverse=True)
        
        logger.info(f"Обнаружено {len(campaigns)} информационных кампаний, "
                   f"из них критических: {sum(1 for c in campaigns if c.threat_level == 'critical')}")
        
        return campaigns
    
    async def _find_coordinated_groups(self, social_data: List[Dict]) -> Dict[int, Dict]:
        """
        Поиск скоординированных групп пользователей
        На основе анализа временных паттернов и схожести контента [citation:3]
        """
        # Группировка по временным кластерам
        time_clusters = self._cluster_by_time(social_data, window_minutes=30)
        
        coordinated_groups = {}
        group_counter = 0
        
        for time_cluster in time_clusters:
            if len(time_cluster) < 5:
                continue
            
            # Анализ схожести текстов внутри кластера
            texts = [p.get('text', '') for p in time_cluster]
            similarity_matrix = self._calculate_similarity_matrix(texts)
            
            # Находим подгруппы с высокой схожестью
            subgroups = self._find_similarity_subgroups(similarity_matrix, threshold=0.6)
            
            for subgroup_indices in subgroups:
                if len(subgroup_indices) < 3:
                    continue
                
                subgroup_posts = [time_cluster[i] for i in subgroup_indices]
                subgroup_users = list(set(p.get('author_id') for p in subgroup_posts))
                
                # Ищем координаторов (пользователи, которые активно взаимодействуют)
                coordinators = self._find_coordinators(subgroup_posts, subgroup_users)
                
                coordinated_groups[group_counter] = {
                    'users': subgroup_users,
                    'posts': subgroup_posts,
                    'coordinators': coordinators,
                    'time_cluster': time_cluster
                }
                group_counter += 1
        
        return coordinated_groups
    
    def _cluster_by_time(self, posts: List[Dict], window_minutes: int = 30) -> List[List[Dict]]:
        """Кластеризация постов по времени"""
        if not posts:
            return []
        
        # Сортируем по времени
        sorted_posts = sorted(posts, key=lambda x: x.get('date', datetime.now()))
        
        clusters = []
        current_cluster = []
        last_time = None
        
        for post in sorted_posts:
            post_time = post.get('date', datetime.now())
            if isinstance(post_time, str):
                post_time = datetime.fromisoformat(post_time)
            
            if last_time and (post_time - last_time).total_seconds() > window_minutes * 60:
                if len(current_cluster) >= 3:
                    clusters.append(current_cluster)
                current_cluster = []
            
            current_cluster.append(post)
            last_time = post_time
        
        if len(current_cluster) >= 3:
            clusters.append(current_cluster)
        
        return clusters
    
    def _calculate_similarity_matrix(self, texts: List[str]) -> np.ndarray:
        """Расчёт матрицы схожести текстов"""
        if len(texts) < 2:
            return np.array([[1.0]])
        
        try:
            vectors = self.vectorizer.fit_transform(texts)
            return cosine_similarity(vectors)
        except:
            return np.eye(len(texts))
    
    def _find_similarity_subgroups(self, similarity_matrix: np.ndarray, threshold: float = 0.6) -> List[List[int]]:
        """Находит подгруппы с высокой схожестью текстов"""
        n = len(similarity_matrix)
        visited = set()
        subgroups = []
        
        for i in range(n):
            if i in visited:
                continue
            
            # Находим все индексы, похожие на i
            similar = [j for j in range(n) if similarity_matrix[i, j] > threshold]
            if len(similar) >= 3:
                subgroups.append(similar)
                visited.update(similar)
        
        return subgroups
    
    def _find_coordinators(self, posts: List[Dict], users: List[str]) -> List[str]:
        """Поиск координаторов в группе"""
        # Координаторы = те, кто создаёт больше всего постов
        post_counts = Counter(p.get('author_id') for p in posts)
        
        # Координаторы также те, кто получает много ответов/репостов
        mentioned_counts = Counter()
        for post in posts:
            mentions = self._extract_mentions(post.get('text', ''))
            for mention in mentions:
                mentioned_counts[mention] += 1
        
        # Комбинированный счёт
        combined_score = {}
        for user in users:
            combined_score[user] = post_counts.get(user, 0) + mentioned_counts.get(user, 0) * 2
        
        # Топ-20% — координаторы
        if not combined_score:
            return []
        
        threshold = sorted(combined_score.values(), reverse=True)[max(1, len(combined_score)//5)]
        coordinators = [u for u, s in combined_score.items() if s >= threshold]
        
        return coordinators
    
    async def _assess_coordination_level(self, posts: List[Dict]) -> float:
        """Оценка уровня скоординированности кампании"""
        if len(posts) < 3:
            return 0.0
        
        signals = []
        
        # 1. Схожесть текстов
        texts = [p.get('text', '') for p in posts]
        similarity = self._calculate_text_similarity(texts)
        if similarity > 0.6:
            signals.append(0.8)
        elif similarity > 0.4:
            signals.append(0.5)
        
        # 2. Временная скоординированность
        dates = [p.get('date', datetime.now()) for p in posts]
        if len(dates) > 1:
            time_diff = max(dates) - min(dates)
            if time_diff.total_seconds() < 1800:  # 30 минут
                signals.append(0.7)
            elif time_diff.total_seconds() < 3600:
                signals.append(0.4)
        
        # 3. Использование одинаковых хештегов
        hashtags = []
        for post in posts:
            text = post.get('text', '')
            post_hashtags = re.findall(r'#(\w+)', text)
            hashtags.extend(post_hashtags)
        
        if hashtags:
            hashtag_counter = Counter(hashtags)
            common_hashtags = [h for h, c in hashtag_counter.items() if c > len(posts) * 0.3]
            if common_hashtags:
                signals.append(0.6)
        
        if not signals:
            return 0.0
        
        return sum(signals) / len(signals)
    
    async def _extract_group_narratives(self, posts: List[Dict]) -> List[Narrative]:
        """Извлечение нарративов, используемых группой"""
        # Используем существующий метод detect_narratives
        narratives = await self.detect_narratives(posts, hours_back=72)
        
        # Фильтруем только те, где есть вклад группы
        group_narratives = []
        for narrative in narratives:
            group_contributors = [a for a in narrative.main_actors if any(a in p.get('author_id', '') for p in posts)]
            if group_contributors:
                group_narratives.append(narrative)
        
        return group_narratives[:5]
    
    def _identify_campaign_target(self, posts: List[Dict]) -> str:
        """Идентификация цели информационной кампании"""
        all_text = ' '.join([p.get('text', '').lower() for p in posts])
        
        targets = {
            'mayor': ['мэр', 'глава города', 'градоначальник'],
            'administration': ['администрация', 'мэрия', 'власть', 'чиновник'],
            'specific_project': ['стройка', 'парк', 'дороги', 'бюджет'],
            'general': ['город', 'район', 'жители']
        }
        
        for target, keywords in targets.items():
            if any(kw in all_text for kw in keywords):
                return target
        
        return "general"
    
    def _calculate_impact_score(self, posts: List[Dict], coordination_score: float) -> float:
        """Расчёт оценки влияния кампании"""
        total_reach = sum(p.get('views', 0) for p in posts)
        total_engagement = sum(p.get('likes', 0) + p.get('comments', 0) * 2 for p in posts)
        
        # Нормализация (предполагаем, что охват > 10000 = высокий)
        reach_score = min(1.0, total_reach / 10000)
        engagement_score = min(1.0, total_engagement / 500)
        
        impact = (reach_score * 0.4 + engagement_score * 0.4 + coordination_score * 0.2)
        
        return min(1.0, impact)
    
    def _assess_campaign_threat(self, impact: float, coordination: float, narratives: List[Narrative]) -> str:
        """Оценка уровня угрозы от кампании"""
        # Учитываем негативность нарративов
        negative_narratives = sum(1 for n in narratives if n.sentiment < -0.3)
        
        if impact > 0.7 and coordination > 0.6 and negative_narratives > 1:
            return "critical"
        elif impact > 0.5 and coordination > 0.4:
            return "high"
        elif impact > 0.3:
            return "medium"
        else:
            return "low"
    
    def _collect_campaign_evidence(self, posts: List[Dict], users: List[str]) -> List[Dict]:
        """Сбор доказательств координации"""
        evidence = []
        
        # Примеры похожих постов
        texts = [p.get('text', '') for p in posts]
        similarity_matrix = self._calculate_similarity_matrix(texts)
        
        # Находим пары с высокой схожестью
        for i in range(len(posts)):
            for j in range(i+1, len(posts)):
                if similarity_matrix[i, j] > 0.7:
                    evidence.append({
                        'type': 'similar_text',
                        'post1': posts[i].get('id', 'unknown'),
                        'post2': posts[j].get('id', 'unknown'),
                        'similarity': float(similarity_matrix[i, j]),
                        'text1': posts[i].get('text', '')[:200],
                        'text2': posts[j].get('text', '')[:200]
                    })
                    if len(evidence) >= 5:
                        break
            if len(evidence) >= 5:
                break
        
        # Временные паттерны
        dates = [p.get('date', datetime.now()) for p in posts]
        if len(dates) > 1:
            min_date = min(dates)
            max_date = max(dates)
            evidence.append({
                'type': 'temporal_pattern',
                'first_post': min_date.isoformat(),
                'last_post': max_date.isoformat(),
                'duration_hours': (max_date - min_date).total_seconds() / 3600,
                'post_count': len(posts)
            })
        
        return evidence
    
    def _generate_campaign_name(self, target: str, narratives: List[Narrative]) -> str:
        """Генерация названия кампании"""
        target_names = {
            'mayor': 'против мэра',
            'administration': 'против администрации',
            'specific_project': 'против городского проекта',
            'general': 'дестабилизационная'
        }
        
        target_text = target_names.get(target, 'информационная')
        
        if narratives and narratives[0].sentiment < -0.3:
            return f"Негативная кампания {target_text}"
        else:
            return f"Координированная кампания {target_text}"
    
    # ==================== 5. МОНИТОРИНГ И ФОРМИРОВАНИЕ ОТЧЁТОВ ====================
    
    async def run_full_analysis(self, social_data: List[Dict]) -> Dict[str, Any]:
        """
        Запуск полного цикла анализа общественного мнения
        """
        logger.info(f"Запуск полного анализа для города {self.city_name}")
        
        results = {
            'city': self.city_name,
            'timestamp': datetime.now().isoformat(),
            'data_volume': len(social_data),
            'opinion_leaders': [],
            'radical_users': [],
            'narratives': [],
            'disinformation_campaigns': [],
            'summary': {}
        }
        
        # Параллельный запуск анализаторов
        leaders = await self.detect_opinion_leaders(social_data)
        radicals = await self.detect_radical_users(social_data)
        narratives = await self.detect_narratives(social_data)
        campaigns = await self.detect_disinformation_campaigns(social_data)
        
        # Формируем результаты
        results['opinion_leaders'] = [
            {
                'username': l.username,
                'influence_score': l.influence_score,
                'sentiment_towards_admin': l.sentiment_towards_admin,
                'risk_level': l.risk_level,
                'main_topics': l.main_topics
            }
            for l in leaders[:20]
        ]
        
        results['radical_users'] = [
            {
                'username': r.username,
                'radical_score': r.radical_score,
                'call_to_action_score': r.call_to_action_score,
                'threat_level': r.threat_level,
                'target_entities': r.target_entities
            }
            for r in radicals[:20]
        ]
        
        results['narratives'] = [
            {
                'title': n.title,
                'sentiment': n.sentiment,
                'volume': n.volume,
                'trend': n.trend,
                'dominant_vector': n.dominant_vector,
                'is_artificial': n.is_artificial
            }
            for n in narratives[:10]
        ]
        
        results['disinformation_campaigns'] = [
            {
                'name': c.name,
                'target': c.target,
                'scale': c.scale,
                'impact_score': c.impact_score,
                'threat_level': c.threat_level,
                'coordination_level': c.coordination_level
            }
            for c in campaigns
        ]
        
        # Сводка
        results['summary'] = {
            'total_opinion_leaders': len(leaders),
            'critical_leaders': sum(1 for l in leaders if l.risk_level == 'critical'),
            'total_radical_users': len(radicals),
            'critical_radicals': sum(1 for r in radicals if r.threat_level == 'critical'),
            'active_narratives': len(narratives),
            'artificial_narratives': sum(1 for n in narratives if n.is_artificial),
            'active_campaigns': len(campaigns),
            'critical_campaigns': sum(1 for c in campaigns if c.threat_level == 'critical'),
            'overall_threat_level': self._calculate_overall_threat(leaders, radicals, campaigns)
        }
        
        logger.info(f"Анализ завершён. Общий уровень угрозы: {results['summary']['overall_threat_level']}")
        
        return results
    
    def _calculate_overall_threat(self, leaders: List, radicals: List, campaigns: List) -> str:
        """Расчёт общего уровня угрозы"""
        threat_scores = []
        
        # Лидеры мнений
        for l in leaders:
            if l.risk_level == 'critical':
                threat_scores.append(4)
            elif l.risk_level == 'high':
                threat_scores.append(3)
            elif l.risk_level == 'medium':
                threat_scores.append(2)
        
        # Радикалы
        for r in radicals:
            if r.threat_level == 'critical':
                threat_scores.append(4)
            elif r.threat_level == 'high':
                threat_scores.append(3)
            elif r.threat_level == 'medium':
                threat_scores.append(2)
        
        # Кампании
        for c in campaigns:
            if c.threat_level == 'critical':
                threat_scores.append(4)
            elif c.threat_level == 'high':
                threat_scores.append(3)
            elif c.threat_level == 'medium':
                threat_scores.append(2)
        
        if not threat_scores:
            return 'low'
        
        avg_threat = sum(threat_scores) / len(threat_scores)
        
        if avg_threat >= 3.5:
            return 'critical'
        elif avg_threat >= 2.5:
            return 'high'
        elif avg_threat >= 1.5:
            return 'medium'
        else:
            return 'low'
    
    async def generate_alert(self, threat_level: str, threat_type: str, details: Dict) -> Dict:
        """
        Генерация оповещения об угрозе для администрации
        """
        alert = {
            'alert_id': hashlib.md5(f"{datetime.now().isoformat()}{threat_type}".encode()).hexdigest()[:8],
            'timestamp': datetime.now().isoformat(),
            'city': self.city_name,
            'threat_level': threat_level,
            'threat_type': threat_type,
            'details': details,
            'recommended_actions': self._get_recommended_actions(threat_type, threat_level)
        }
        
        logger.warning(f"⚠️ ОПОВЕЩЕНИЕ [{threat_level.upper()}]: {threat_type} - {details.get('message', '')}")
        
        return alert
    
    def _get_recommended_actions(self, threat_type: str, threat_level: str) -> List[str]:
        """Рекомендованные действия при обнаружении угрозы"""
        actions = []
        
        if threat_type == 'radical_user' and threat_level == 'critical':
            actions = [
                "Передать информацию в правоохранительные органы",
                "Усилить мониторинг за данным пользователем",
                "Провести анализ связей пользователя",
                "Подготовить разъяснительную информацию для опровержения"
            ]
        elif threat_type == 'disinformation_campaign' and threat_level == 'critical':
            actions = [
                "Немедленно опубликовать официальное опровержение",
                "Задействовать лояльных лидеров мнений для контрпропаганды",
                "Усилить модерацию в соцсетях",
                "Обратиться в Роскомнадзор для блокировки ботов",
                "Провести пресс-конференцию"
            ]
        elif threat_type == 'negative_narrative' and threat_level == 'high':
            actions = [
                "Подготовить разъяснительный пост в соцсетях",
                "Провести встречу с авторитетными жителями",
                "Запустить позитивную информационную кампанию"
            ]
        else:
            actions = [
                "Продолжить мониторинг ситуации",
                "Проинформировать профильных специалистов"
            ]
        
        return actions


# ==================== ИНТЕГРАЦИЯ С ОСНОВНЫМ ПРИЛОЖЕНИЕМ ====================

async def create_opinion_intelligence_analyzer(city_name: str) -> OpinionIntelligenceAnalyzer:
    """Фабричная функция для создания анализатора"""
    return OpinionIntelligenceAnalyzer(city_name)


# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("🧪 Тестирование OpinionIntelligenceAnalyzer...")
        
        # Создаём анализатор
        analyzer = OpinionIntelligenceAnalyzer("Коломна")
        
        # Генерируем тестовые данные (в реальности берутся из парсера)
        test_posts = [
            {
                'id': '1',
                'author_id': 'user_001',
                'author_username': 'ivan_petrov',
                'text': 'Мэр отлично поработал! Парк в центре просто прекрасный. Спасибо администрации!',
                'date': datetime.now(),
                'likes': 150,
                'comments': 20,
                'reposts': 10,
                'views': 5000
            },
            {
                'id': '2',
                'author_id': 'user_002',
                'author_username': 'angry_citizen',
                'text': 'Власть ничего не делает! Дороги разбиты, мусор не вывозят. Пора выходить на митинг!',
                'date': datetime.now() - timedelta(hours=2),
                'likes': 80,
                'comments': 45,
                'reposts': 30,
                'views': 3000
            },
            {
                'id': '3',
                'author_id': 'user_003',
                'author_username': 'repost_bot_01',
                'text': 'Дороги разбиты, мусор не вывозят. Власть ничего не делает! Пора выходить на митинг!',
                'date': datetime.now() - timedelta(hours=1),
                'likes': 5,
                'comments': 1,
                'reposts': 0,
                'views': 200
            },
            {
                'id': '4',
                'author_id': 'user_004',
                'author_username': 'repost_bot_02',
                'text': 'Дороги разбиты, мусор не вывозят. Власть ничего не делает! Пора выходить на митинг!',
                'date': datetime.now() - timedelta(hours=1),
                'likes': 3,
                'comments': 0,
                'reposts': 0,
                'views': 150
            }
        ]
        
        # Запускаем полный анализ
        results = await analyzer.run_full_analysis(test_posts)
        
        # Выводим результаты
        print(f"\n📊 РЕЗУЛЬТЫ АНАЛИЗА:")
        print(f"  • Лидеров мнений: {results['summary']['total_opinion_leaders']}")
        print(f"  • Радикальных пользователей: {results['summary']['total_radical_users']}")
        print(f"  • Активных нарративов: {results['summary']['active_narratives']}")
        print(f"  • Информационных кампаний: {results['summary']['active_campaigns']}")
        print(f"  • Общий уровень угрозы: {results['summary']['overall_threat_level']}")
        
        if results['disinformation_campaigns']:
            print(f"\n⚠️ ОБНАРУЖЕНЫ КАМПАНИИ:")
            for camp in results['disinformation_campaigns']:
                print(f"  • {camp['name']} — уровень угрозы: {camp['threat_level']}")
        
        print("\n✅ Тест завершен")
    
    asyncio.run(demo())
