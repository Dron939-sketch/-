#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 17: ИНЖИНИРИНГ НАРРАТИВОВ (Narrative Engineering)
Система формирования общественного мнения, управления информационными потоками
и создания устойчивых позитивных паттернов восприятия

Основан на методах:
- Теория нарративов и меметики
- Прикладная психология убеждения (Р. Чалдини)
- Теория фреймов (Гоффман)
- Социальное доказательство и создание трендов
- Каскадное распространение информации
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging
import hashlib
import json
import random

logger = logging.getLogger(__name__)


# ==================== МОДЕЛИ ДАННЫХ ====================

class NarrativeType(Enum):
    """Типы нарративов"""
    VISION = "vision"           # Видение будущего (куда идём)
    ACHIEVEMENT = "achievement" # Достижения (что сделали)
    VALUES = "values"           # Ценности (во что верим)
    URGENCY = "urgency"         # Срочность (почему надо действовать сейчас)
    HOPE = "hope"               # Надежда (всё будет хорошо)
    IDENTITY = "identity"       # Идентичность (кто мы)


class ChannelType(Enum):
    """Типы каналов коммуникации"""
    OFFICIAL = "official"       # Официальные (сайт, соцсети администрации)
    MEDIA = "media"             # СМИ (телевидение, газеты, новостные порталы)
    SOCIAL = "social"           # Социальные сети (Telegram, VK)
    INFORMAL = "informal"       # Неформальные (дворовые чаты, сарафанное радио)
    EVENTS = "events"           # Событийные (фестивали, встречи)
    VISUAL = "visual"           # Визуальные (баннеры, видео, наружка)


class ToolType(Enum):
    """Типы инструментов информационной политики"""
    STORY = "story"             # Истории успеха
    SYMBOL = "symbol"           # Символы и брендинг
    RITUAL = "ritual"           # Ритуалы и традиции
    HERO = "hero"               # Герои и лидеры мнений
    METAPHOR = "metaphor"       # Метафоры и аналогии
    DATA = "data"               # Данные и факты
    EMOTION = "emotion"         # Эмоциональные триггеры
    COMMUNITY = "community"     # Сообщества и группы


@dataclass
class NarrativeCampaign:
    """Информационная кампания"""
    id: str
    name: str
    description: str
    target_vectors: List[str]          # какие векторы улучшаем
    target_audience: List[str]         # целевая аудитория
    key_message: str                    # ключевое сообщение
    narrative_type: NarrativeType
    tools: List[ToolType]
    channels: List[ChannelType]
    timeline: Dict[str, List[Dict]]    # расписание активностей
    budget_million_rub: float
    expected_impact: Dict[str, float]   # ожидаемое влияние на метрики
    kpis: List[str]                     # ключевые показатели эффективности
    status: str = "draft"               # draft/active/completed
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class MessageTemplate:
    """Шаблон сообщения"""
    id: str
    title: str
    content: str
    emotion: str                        # радость/гордость/надежда/срочность
    target_vector: str
    best_channels: List[ChannelType]
    engagement_rate: float              # ожидаемый уровень вовлечения
    examples: List[str]


@dataclass
class InfluenceMap:
    """Карта влияния"""
    id: str
    campaign_id: str
    nodes: List[Dict]                   # узлы (ЛОМ, СМИ, сообщества)
    connections: List[Dict]             # связи между узлами
    diffusion_paths: List[List[str]]    # пути распространения
    estimated_reach: int                # оценочный охват
    key_influencers: List[str]          # ключевые влиятели


# ==================== КОНФИГУРАЦИЯ ====================

class NarrativeConfig:
    """Конфигурация системы нарративов"""
    
    # Шаблоны сообщений по векторам
    MESSAGE_TEMPLATES = {
        'СБ': [
            {
                "title": "Наш город становится безопаснее",
                "content": "За последние {months} месяцев количество преступлений снизилось на {percent}%. Камеры видеонаблюдения, патрулирование и неравнодушие жителей делают своё дело.",
                "emotion": "гордость",
                "engagement_rate": 0.72
            },
            {
                "title": "Вместе мы — сила",
                "content": "Программа «Соседский дозор» объединила {people} жителей. Вместе мы делаем наши дворы безопасными для детей и пожилых.",
                "emotion": "единство",
                "engagement_rate": 0.68
            },
            {
                "title": "Спокойствие возвращается",
                "content": "Благодаря новым мерам безопасности жители {district} снова могут спокойно гулять по вечерам. «Раньше боялись, теперь — нет», — делятся они.",
                "emotion": "надежда",
                "engagement_rate": 0.65
            }
        ],
        'ТФ': [
            {
                "title": "Новые рабочие места",
                "content": "{count} новых предприятий открылись в нашем городе за последний год. {jobs} человек нашли работу. Город развивается!",
                "emotion": "радость",
                "engagement_rate": 0.70
            },
            {
                "title": "Поддержка бизнеса — приоритет",
                "content": "Налоговые льготы и гранты помогли {count} предпринимателям запустить или расширить своё дело. Экономика города растёт.",
                "emotion": "гордость",
                "engagement_rate": 0.66
            }
        ],
        'УБ': [
            {
                "title": "Город преображается",
                "content": "{parks} новых парков и скверов появилось в этом году. {km} километров отремонтированных дорог. Город становится комфортнее для жизни.",
                "emotion": "радость",
                "engagement_rate": 0.75
            },
            {
                "title": "Жители довольны",
                "content": "По данным опроса, {percent}% жителей отмечают улучшение качества жизни в городе. «Стало чище, уютнее, появились места для отдыха», — говорят они.",
                "emotion": "гордость",
                "engagement_rate": 0.68
            }
        ],
        'ЧВ': [
            {
                "title": "Мы — одна команда",
                "content": "ТОСы, волонтёры, активисты — вместе мы делаем город лучше. За этот год реализовано {projects} проектов инициативного бюджетирования.",
                "emotion": "единство",
                "engagement_rate": 0.73
            },
            {
                "title": "Доверие растёт",
                "content": "Уровень доверия к городской администрации вырос на {percent}% за полгода. Жители видят перемены и поддерживают курс развития.",
                "emotion": "гордость",
                "engagement_rate": 0.64
            }
        ]
    }
    
    # Инструменты информационной политики
    TOOLS_DESCRIPTION = {
        ToolType.STORY: {
            "name": "Истории успеха",
            "description": "Реальные истории жителей, чья жизнь изменилась к лучшему",
            "effectiveness": 0.85,
            "cost": "Низкий",
            "examples": ["Видеоинтервью с предпринимателем", "Пост жителя о новом парке"]
        },
        ToolType.SYMBOL: {
            "name": "Символы и брендинг",
            "description": "Создание узнаваемых символов города, бренда",
            "effectiveness": 0.75,
            "cost": "Средний",
            "examples": ["Логотип города", "Флаг", "Гимн", "Маскот"]
        },
        ToolType.RITUAL: {
            "name": "Ритуалы и традиции",
            "description": "Создание новых городских традиций и праздников",
            "effectiveness": 0.80,
            "cost": "Средний",
            "examples": ["День города", "Фестиваль", "Субботник", "Парад"]
        },
        ToolType.HERO: {
            "name": "Герои и лидеры мнений",
            "description": "Продвижение через уважаемых людей",
            "effectiveness": 0.90,
            "cost": "Низкий",
            "examples": ["Интервью с врачом года", "История успеха предпринимателя"]
        },
        ToolType.METAPHOR: {
            "name": "Метафоры и аналогии",
            "description": "Создание понятных образов для сложных идей",
            "effectiveness": 0.70,
            "cost": "Низкий",
            "examples": ["Город-сад", "Город-семья", "Город-крепость"]
        },
        ToolType.DATA: {
            "name": "Данные и факты",
            "description": "Аргументация через цифры и статистику",
            "effectiveness": 0.65,
            "cost": "Низкий",
            "examples": ["Инфографика", "Дашборд достижений", "Отчёт"]
        },
        ToolType.EMOTION: {
            "name": "Эмоциональные триггеры",
            "description": "Апелляция к базовым эмоциям и ценностям",
            "effectiveness": 0.82,
            "cost": "Низкий",
            "examples": ["Трогательное видео", "История из жизни"]
        },
        ToolType.COMMUNITY: {
            "name": "Сообщества и группы",
            "description": "Создание и поддержка объединений по интересам",
            "effectiveness": 0.78,
            "cost": "Низкий",
            "examples": ["Чат ТОС", "Клуб волонтёров", "Соседские группы"]
        }
    }
    
    # Каналы коммуникации
    CHANNELS_PRIORITY = {
        ChannelType.SOCIAL: {"weight": 0.30, "speed": "быстро", "reach": "высокий"},
        ChannelType.OFFICIAL: {"weight": 0.25, "speed": "средне", "reach": "средний"},
        ChannelType.MEDIA: {"weight": 0.20, "speed": "медленно", "reach": "высокий"},
        ChannelType.INFORMAL: {"weight": 0.15, "speed": "медленно", "reach": "низкий", "trust": "высокий"},
        ChannelType.EVENTS: {"weight": 0.05, "speed": "медленно", "reach": "низкий", "impact": "высокий"},
        ChannelType.VISUAL: {"weight": 0.05, "speed": "медленно", "reach": "средний"}
    }


# ==================== ОСНОВНОЙ КЛАСС ====================

class NarrativeEngineer:
    """
    Инженер нарративов — система формирования общественного мнения
    
    Позволяет:
    - Создавать информационные кампании для улучшения метрик
    - Выбирать правильные инструменты и каналы
    - Формировать устойчивые позитивные нарративы
    - Отслеживать эффективность информационной работы
    """
    
    def __init__(self, city_name: str, config: NarrativeConfig = None):
        self.city_name = city_name
        self.config = config or NarrativeConfig()
        
        # Хранилище
        self.campaigns: Dict[str, NarrativeCampaign] = {}
        self.influence_maps: Dict[str, InfluenceMap] = {}
        self.templates = self.config.MESSAGE_TEMPLATES
        self.tools_info = self.config.TOOLS_DESCRIPTION
        
        # Статистика
        self.campaign_history = []
        
        logger.info(f"NarrativeEngineer инициализирован для города {city_name}")
    
    # ==================== 1. АНАЛИЗ ТЕКУЩЕГО НАРРАТИВА ====================
    
    async def analyze_current_narrative(self, 
                                         opinion_results: Dict,
                                         social_data: List[Dict]) -> Dict[str, Any]:
        """
        Анализ текущих доминирующих нарративов в городе
        """
        logger.info("Анализ текущих нарративов в информационном поле...")
        
        # Собираем все сообщения
        all_texts = []
        for post in social_data:
            text = post.get('text', '')
            if text:
                all_texts.append(text.lower())
        
        if not all_texts:
            return {'error': 'Недостаточно данных для анализа'}
        
        # Анализ тональности по векторам
        vector_mentions = defaultdict(int)
        vector_sentiment = defaultdict(list)
        
        vector_keywords = {
            'СБ': ['безопасн', 'страх', 'преступн', 'авария', 'дтп', 'полиц', 'патруль'],
            'ТФ': ['деньг', 'бизнес', 'работ', 'зарплат', 'экономик', 'налог', 'инвестиц'],
            'УБ': ['парк', 'благоустр', 'дорог', 'ремонт', 'чистот', 'комфорт', 'экологи'],
            'ЧВ': ['сосед', 'помощь', 'волонтер', 'вместе', 'общен', 'довер', 'активист']
        }
        
        for text in all_texts:
            for vector, keywords in vector_keywords.items():
                for kw in keywords:
                    if kw in text:
                        vector_mentions[vector] += 1
                        # Простая оценка тональности
                        positive = any(w in text for w in ['хорош', 'отличн', 'нравитс', 'спасиб'])
                        negative = any(w in text for w in ['плох', 'ужасн', 'возмут', 'позор'])
                        
                        if positive:
                            vector_sentiment[vector].append(1)
                        elif negative:
                            vector_sentiment[vector].append(-1)
                        else:
                            vector_sentiment[vector].append(0)
        
        # Доминирующие темы
        total_mentions = sum(vector_mentions.values())
        dominant_vectors = []
        for vector, count in sorted(vector_mentions.items(), key=lambda x: x[1], reverse=True):
            if total_mentions > 0:
                dominant_vectors.append({
                    'vector': vector,
                    'share': count / total_mentions,
                    'avg_sentiment': sum(vector_sentiment[vector]) / len(vector_sentiment[vector]) if vector_sentiment[vector] else 0
                })
        
        # Выявленные проблемы и возможности
        problems = []
        opportunities = []
        
        for dv in dominant_vectors:
            if dv['avg_sentiment'] < -0.2:
                problems.append(f"Доминирует негативный нарратив по {dv['vector']} (доля {dv['share']:.0%})")
            elif dv['avg_sentiment'] > 0.2 and dv['share'] > 0.1:
                opportunities.append(f"Позитивный нарратив по {dv['vector']} можно усилить (доля {dv['share']:.0%})")
        
        # Рекомендации
        recommendations = []
        if problems:
            recommendations.append(f"🎯 Приоритет: развернуть контрнарратив по {problems[0][:50]}")
        
        if opportunities:
            recommendations.append(f"📢 Усилить позитивный нарратив: {opportunities[0][:50]}")
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_messages_analyzed': len(all_texts),
            'dominant_vectors': dominant_vectors[:4],
            'problems': problems,
            'opportunities': opportunities,
            'recommendations': recommendations,
            'narrative_health_score': self._calculate_narrative_health(dominant_vectors)
        }
    
    def _calculate_narrative_health(self, dominant_vectors: List[Dict]) -> float:
        """Расчёт здоровья информационного поля (0-1)"""
        if not dominant_vectors:
            return 0.5
        
        # Чем выше позитивный сентимент, тем здоровее
        avg_sentiment = sum(d['avg_sentiment'] for d in dominant_vectors) / len(dominant_vectors)
        
        # Нормализация от -1..1 к 0..1
        health = (avg_sentiment + 1) / 2
        
        return min(1.0, max(0.0, health))
    
    # ==================== 2. СОЗДАНИЕ ИНФОРМАЦИОННОЙ КАМПАНИИ ====================
    
    async def create_campaign(self,
                               name: str,
                               description: str,
                               target_vectors: List[str],
                               target_audience: List[str],
                               key_message: str,
                               narrative_type: NarrativeType,
                               budget: float) -> NarrativeCampaign:
        """
        Создание информационной кампании
        """
        campaign_id = f"camp_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hashlib.md5(name.encode()).hexdigest()[:4]}"
        
        # Автоматический подбор инструментов и каналов
        tools = await self._recommend_tools(target_vectors, narrative_type)
        channels = await self._recommend_channels(target_vectors, target_audience)
        
        # Создание таймлайна
        timeline = await self._build_timeline(tools, channels, budget)
        
        # Оценка ожидаемого влияния
        expected_impact = await self._estimate_campaign_impact(target_vectors, tools, budget)
        
        # KPIs
        kpis = await self._generate_kpis(target_vectors)
        
        campaign = NarrativeCampaign(
            id=campaign_id,
            name=name,
            description=description,
            target_vectors=target_vectors,
            target_audience=target_audience,
            key_message=key_message,
            narrative_type=narrative_type,
            tools=tools,
            channels=channels,
            timeline=timeline,
            budget_million_rub=budget,
            expected_impact=expected_impact,
            kpis=kpis,
            status="draft",
            created_at=datetime.now()
        )
        
        self.campaigns[campaign_id] = campaign
        
        logger.info(f"Создана кампания '{name}' с бюджетом {budget} млн ₽")
        return campaign
    
    async def _recommend_tools(self, target_vectors: List[str], narrative_type: NarrativeType) -> List[ToolType]:
        """Рекомендация инструментов для кампании"""
        tools = []
        
        # Базовые инструменты (всегда эффективны)
        tools.append(ToolType.STORY)
        tools.append(ToolType.HERO)
        
        # В зависимости от типа нарратива
        if narrative_type == NarrativeType.VISION:
            tools.append(ToolType.METAPHOR)
            tools.append(ToolType.SYMBOL)
        elif narrative_type == NarrativeType.ACHIEVEMENT:
            tools.append(ToolType.DATA)
            tools.append(ToolType.VISUAL)
        elif narrative_type == NarrativeType.HOPE:
            tools.append(ToolType.EMOTION)
            tools.append(ToolType.STORY)
        elif narrative_type == NarrativeType.IDENTITY:
            tools.append(ToolType.RITUAL)
            tools.append(ToolType.COMMUNITY)
        
        # В зависимости от векторов
        if 'СБ' in target_vectors:
            tools.append(ToolType.COMMUNITY)
        if 'ЧВ' in target_vectors:
            tools.append(ToolType.RITUAL)
            tools.append(ToolType.HERO)
        
        return list(set(tools))[:6]  # не более 6 инструментов
    
    async def _recommend_channels(self, target_vectors: List[str], target_audience: List[str]) -> List[ChannelType]:
        """Рекомендация каналов коммуникации"""
        channels = [ChannelType.OFFICIAL, ChannelType.SOCIAL]  # база
        
        # По аудитории
        if 'молодёжь' in target_audience:
            channels.append(ChannelType.SOCIAL)
            channels.append(ChannelType.EVENTS)
        if 'пенсионеры' in target_audience:
            channels.append(ChannelType.MEDIA)
            channels.append(ChannelType.VISUAL)
        if 'бизнес' in target_audience:
            channels.append(ChannelType.OFFICIAL)
            channels.append(ChannelType.MEDIA)
        
        # По векторам
        if 'ЧВ' in target_vectors:
            channels.append(ChannelType.INFORMAL)
            channels.append(ChannelType.EVENTS)
        
        return list(set(channels))[:4]
    
    async def _build_timeline(self, tools: List[ToolType], channels: List[ChannelType], budget: float) -> Dict[str, List[Dict]]:
        """Построение таймлайна кампании"""
        timeline = {
            'month_1': [],
            'month_2': [],
            'month_3': []
        }
        
        # Месяц 1: запуск
        timeline['month_1'].append({
            'week': 1,
            'activity': 'Запуск официального сообщения',
            'channels': [c.value for c in channels if c in [ChannelType.OFFICIAL, ChannelType.SOCIAL]],
            'tools': [t.value for t in tools if t in [ToolType.DATA, ToolType.STORY]],
            'budget': budget * 0.3
        })
        
        # Месяц 2: усиление
        timeline['month_2'].append({
            'week': 5,
            'activity': 'Вовлечение лидеров мнений',
            'channels': [c.value for c in channels if c in [ChannelType.SOCIAL, ChannelType.MEDIA]],
            'tools': [t.value for t in tools if t in [ToolType.HERO, ToolType.STORY]],
            'budget': budget * 0.4
        })
        
        # Месяц 3: закрепление
        timeline['month_3'].append({
            'week': 9,
            'activity': 'Событийное мероприятие',
            'channels': [c.value for c in channels if c in [ChannelType.EVENTS, ChannelType.VISUAL]],
            'tools': [t.value for t in tools if t in [ToolType.RITUAL, ToolType.COMMUNITY]],
            'budget': budget * 0.3
        })
        
        return timeline
    
    async def _estimate_campaign_impact(self, target_vectors: List[str], tools: List[ToolType], budget: float) -> Dict[str, float]:
        """Оценка ожидаемого влияния кампании"""
        impact = {}
        
        # Базовое влияние
        base_impact = min(0.3, budget / 100)  # 100 млн = 0.3
        
        for vector in target_vectors:
            impact[vector] = base_impact
        
        # Коррекция от инструментов
        tool_effectiveness = sum(self.tools_info[t]['effectiveness'] for t in tools if t in self.tools_info) / len(tools) if tools else 0.7
        for vector in impact:
            impact[vector] *= tool_effectiveness
        
        return impact
    
    async def _generate_kpis(self, target_vectors: List[str]) -> List[str]:
        """Генерация KPIs для кампании"""
        kpis = [
            "Охват целевой аудитории (не менее 50%)",
            "Рост позитивных упоминаний на 30%",
            "Снижение негативных упоминаний на 20%"
        ]
        
        vector_kpis = {
            'СБ': "Рост индекса безопасности на 0.3 балла",
            'ТФ': "Рост индекса экономики на 0.2 балла",
            'УБ': "Рост качества жизни на 0.3 балла",
            'ЧВ': "Рост доверия к власти на 15%"
        }
        
        for vector in target_vectors:
            if vector in vector_kpis:
                kpis.append(vector_kpis[vector])
        
        return kpis
    
    # ==================== 3. ГЕНЕРАЦИЯ КОНКРЕТНЫХ МАТЕРИАЛОВ ====================
    
    async def generate_materials(self, campaign_id: str) -> Dict[str, Any]:
        """
        Генерация конкретных материалов для кампании
        """
        campaign = self.campaigns.get(campaign_id)
        if not campaign:
            return {'error': 'Campaign not found'}
        
        materials = {
            'key_messages': [],
            'social_media_posts': [],
            'press_release': None,
            'video_scenario': None,
            'infographics': [],
            'event_concept': None
        }
        
        # Ключевые сообщения
        for vector in campaign.target_vectors:
            templates = self.templates.get(vector, [])
            for template in templates[:2]:
                materials['key_messages'].append({
                    'vector': vector,
                    'title': template['title'],
                    'content': template['content'].format(
                        months=3,
                        percent=15,
                        people=500,
                        district='Колычёво',
                        count=10,
                        jobs=200,
                        parks=3,
                        km=5,
                        projects=12
                    ),
                    'emotion': template['emotion']
                })
        
        # Посты для соцсетей
        for msg in materials['key_messages'][:3]:
            materials['social_media_posts'].append({
                'platform': 'Telegram',
                'text': f"📢 {msg['title']}\n\n{msg['content']}\n\n#Коломна #Развитие",
                'hashtags': ['Коломна', 'Развитие', 'ГородскойРазум'],
                'best_time': '10:00 или 19:00'
            })
        
        # Пресс-релиз
        materials['press_release'] = {
            'title': f"«{campaign.name}»: новый этап развития города {self.city_name}",
            'lead': campaign.description[:200],
            'body': f"{campaign.key_message}\n\nКлючевые направления: {', '.join(campaign.target_vectors)}",
            'contacts': 'Пресс-служба администрации'
        }
        
        # Сценарий видео (если есть бюджет)
        if campaign.budget_million_rub > 10:
            materials['video_scenario'] = {
                'duration': 90,
                'style': 'документальный',
                'structure': [
                    'Вступление (15 сек) — проблема',
                    'Развитие (45 сек) — что делается',
                    'Кульминация (20 сек) — истории людей',
                    'Заключение (10 сек) — призыв к действию'
                ],
                'estimated_cost': campaign.budget_million_rub * 0.15
            }
        
        return materials
    
    # ==================== 4. КАРТА ВЛИЯНИЯ ====================
    
    async def build_influence_map(self, campaign_id: str) -> InfluenceMap:
        """
        Построение карты влияния для распространения нарратива
        """
        campaign = self.campaigns.get(campaign_id)
        if not campaign:
            return None
        
        # Узлы: ключевые каналы и ЛОМ
        nodes = [
            {'id': 'official', 'type': 'channel', 'name': 'Официальные соцсети', 'weight': 0.9},
            {'id': 'mayor', 'type': 'person', 'name': 'Глава города', 'weight': 0.95},
            {'id': 'local_media', 'type': 'media', 'name': 'Местные СМИ', 'weight': 0.8},
            {'id': 'tg_channels', 'type': 'channel', 'name': 'Городские Telegram-каналы', 'weight': 0.85},
            {'id': 'vk_groups', 'type': 'channel', 'name': 'VK-паблики', 'weight': 0.7},
            {'id': 'influencers', 'type': 'person', 'name': 'Лидеры мнений', 'weight': 0.88}
        ]
        
        # Связи
        connections = [
            {'from': 'official', 'to': 'local_media', 'strength': 0.8},
            {'from': 'official', 'to': 'tg_channels', 'strength': 0.9},
            {'from': 'mayor', 'to': 'official', 'strength': 1.0},
            {'from': 'mayor', 'to': 'influencers', 'strength': 0.7},
            {'from': 'influencers', 'to': 'tg_channels', 'strength': 0.85},
            {'from': 'tg_channels', 'to': 'vk_groups', 'strength': 0.6}
        ]
        
        # Пути распространения
        diffusion_paths = [
            ['official', 'tg_channels', 'vk_groups'],
            ['mayor', 'official', 'local_media'],
            ['mayor', 'influencers', 'tg_channels']
        ]
        
        influence_map = InfluenceMap(
            id=f"im_{campaign_id}",
            campaign_id=campaign_id,
            nodes=nodes,
            connections=connections,
            diffusion_paths=diffusion_paths,
            estimated_reach=50000,
            key_influencers=['Глава города', 'Топ-3 Telegram-канала']
        )
        
        self.influence_maps[influence_map.id] = influence_map
        
        return influence_map
    
    # ==================== 5. ФОРМИРОВАНИЕ НАРРАТИВОВ ====================
    
    async def craft_narrative(self, 
                               target_vector: str,
                               current_sentiment: float,
                               desired_change: float) -> Dict[str, Any]:
        """
        Формирование конкретного нарратива для улучшения метрики
        """
        logger.info(f"Формирование нарратива для вектора {target_vector}")
        
        # Определяем стратегию в зависимости от текущего сентимента
        if current_sentiment < -0.3:
            strategy = "anti_crisis"  # антикризисная
            narrative_type = NarrativeType.URGENCY
            tone = "решительный, мобилизующий"
            key_elements = [
                "Признание проблемы (честность)",
                "Конкретные меры (действия)",
                "Призыв к совместной работе (единство)"
            ]
        elif current_sentiment < 0.1:
            strategy = "stabilization"  # стабилизация
            narrative_type = NarrativeType.HOPE
            tone = "спокойный, уверенный"
            key_elements = [
                "Позитивная динамика (даже маленькие шаги)",
                "Примеры из жизни (истории людей)",
                "Перспективы на будущее"
            ]
        else:
            strategy = "amplification"  # усиление
            narrative_type = NarrativeType.ACHIEVEMENT
            tone = "вдохновляющий, гордый"
            key_elements = [
                "Конкретные достижения (цифры)",
                "Признание заслуг жителей",
                "Новые амбициозные цели"
            ]
        
        # Генерация ключевого сообщения
        templates = self.templates.get(target_vector, [])
        base_template = templates[0] if templates else None
        
        key_message = {
            'title': base_template['title'] if base_template else f"Успехи в развитии",
            'content': base_template['content'] if base_template else "Город меняется к лучшему",
            'emotion': base_template['emotion'] if base_template else "гордость"
        }
        
        # Рекомендуемые форматы
        formats = []
        if strategy == "anti_crisis":
            formats = ["Прямой эфир с мэром", "Пресс-конференция", "Инфографика мер"]
        elif strategy == "stabilization":
            formats = ["Истории жителей", "Фоторепортажи", "Регулярные посты"]
        else:
            formats = ["Видеоролик достижений", "Торжественное мероприятие", "Статья в СМИ"]
        
        return {
            'target_vector': target_vector,
            'current_sentiment': current_sentiment,
            'desired_change': desired_change,
            'strategy': strategy,
            'narrative_type': narrative_type.value,
            'tone': tone,
            'key_elements': key_elements,
            'key_message': key_message,
            'recommended_formats': formats,
            'timeline_weeks': 4 if strategy == "anti_crisis" else 8,
            'success_indicators': [
                f"Рост позитива на {desired_change*100:.0f}%",
                "Рост упоминаний ключевого сообщения",
                "Снижение негативных комментариев"
            ]
        }
    
    # ==================== 6. МОНИТОРИНГ ЭФФЕКТИВНОСТИ ====================
    
    async def track_campaign_effectiveness(self, campaign_id: str, 
                                            before_data: Dict,
                                            after_data: Dict) -> Dict[str, Any]:
        """
        Отслеживание эффективности кампании
        """
        campaign = self.campaigns.get(campaign_id)
        if not campaign:
            return {'error': 'Campaign not found'}
        
        effectiveness = {
            'campaign_id': campaign_id,
            'campaign_name': campaign.name,
            'status': campaign.status,
            'metrics_delta': {},
            'kpi_achievement': {},
            'roi': 0,
            'recommendations': []
        }
        
        # Изменение метрик
        for vector in campaign.target_vectors:
            before = before_data.get(vector, 3.0)
            after = after_data.get(vector, 3.0)
            delta = after - before
            effectiveness['metrics_delta'][vector] = delta
        
        # Достижение KPI
        avg_improvement = sum(effectiveness['metrics_delta'].values()) / len(effectiveness['metrics_delta']) if effectiveness['metrics_delta'] else 0
        
        if avg_improvement >= 0.2:
            effectiveness['kpi_achievement']['target'] = 'exceeded'
            effectiveness['kpi_achievement']['message'] = 'Цели перевыполнены!'
        elif avg_improvement >= 0.1:
            effectiveness['kpi_achievement']['target'] = 'achieved'
            effectiveness['kpi_achievement']['message'] = 'Цели достигнуты'
        else:
            effectiveness['kpi_achievement']['target'] = 'failed'
            effectiveness['kpi_achievement']['message'] = 'Цели не достигнуты, требуется корректировка'
        
        # ROI
        total_impact = sum(effectiveness['metrics_delta'].values())
        effectiveness['roi'] = total_impact / (campaign.budget_million_rub / 10) if campaign.budget_million_rub > 0 else 0
        
        # Рекомендации
        if effectiveness['kpi_achievement']['target'] == 'failed':
            effectiveness['recommendations'].append("Увеличить бюджет на 30%")
            effectiveness['recommendations'].append("Подключить дополнительных лидеров мнений")
            effectiveness['recommendations'].append("Изменить тональность сообщений")
        
        return effectiveness
    
    # ==================== 7. ДАШБОРД ====================
    
    async def get_narrative_dashboard(self) -> Dict[str, Any]:
        """
        Дашборд информационной политики для мэра
        """
        active_campaigns = [c for c in self.campaigns.values() if c.status == 'active']
        draft_campaigns = [c for c in self.campaigns.values() if c.status == 'draft']
        
        # Эффективность инструментов
        tools_effectiveness = []
        for tool, info in self.tools_info.items():
            tools_effectiveness.append({
                'name': info['name'],
                'effectiveness': info['effectiveness'],
                'cost': info['cost']
            })
        
        # Каналы приоритеты
        channels_priority = [
            {'name': ch.value, 'weight': data['weight'], 'speed': data['speed']}
            for ch, data in self.config.CHANNELS_PRIORITY.items()
        ]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'city': self.city_name,
            'statistics': {
                'total_campaigns': len(self.campaigns),
                'active_campaigns': len(active_campaigns),
                'draft_campaigns': len(draft_campaigns),
                'total_budget_active': sum(c.budget_million_rub for c in active_campaigns)
            },
            'active_campaigns': [
                {
                    'name': c.name,
                    'vectors': c.target_vectors,
                    'budget': c.budget_million_rub,
                    'tools': [t.value for t in c.tools],
                    'channels': [ch.value for ch in c.channels]
                }
                for c in active_campaigns[:5]
            ],
            'recommended_tools': [t for t in tools_effectiveness if t['effectiveness'] > 0.8][:5],
            'channel_priorities': channels_priority,
            'narrative_templates': {
                vector: [t['title'] for t in templates[:2]]
                for vector, templates in self.templates.items()
            },
            'quick_wins': self._generate_quick_wins()
        }
    
    def _generate_quick_wins(self) -> List[str]:
        """Быстрые победы в информационной политике"""
        return [
            "📢 Запустить рубрику «Хорошие новости» (еженедельно)",
            "🎥 Снять 3 коротких видео с жителями (истории успеха)",
            "🤝 Провести встречу с топ-10 Telegram-каналов",
            "🏆 Создать городскую награду «Активный житель»",
            "📊 Опубликовать инфографику достижений за квартал"
        ]


# ==================== ИНТЕГРАЦИЯ ====================

async def create_narrative_engineer(city_name: str) -> NarrativeEngineer:
    """Фабричная функция"""
    return NarrativeEngineer(city_name)


# ==================== ПРИМЕР ====================

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("🧪 Тестирование NarrativeEngineer...")
        
        engineer = NarrativeEngineer("Коломна")
        
        # 1. Анализ текущего нарратива
        print("\n📊 АНАЛИЗ ТЕКУЩЕГО НАРРАТИВА:")
        analysis = await engineer.analyze_current_narrative({}, [{'text': 'Ужасные дороги! Ничего не делают! Но парк в центре красивый'}, {'text': 'Наконец-то отремонтировали улицу Ленина, спасибо!'}])
        print(f"  Здоровье нарратива: {analysis['narrative_health_score']:.0%}")
        if analysis['problems']:
            print(f"  Проблемы: {analysis['problems'][0]}")
        if analysis['opportunities']:
            print(f"  Возможности: {analysis['opportunities'][0]}")
        
        # 2. Создание кампании
        print("\n📢 СОЗДАНИЕ КАМПАНИИ:")
        campaign = await engineer.create_campaign(
            name="Безопасная Коломна",
            description="Кампания по повышению уровня безопасности в городе",
            target_vectors=['СБ', 'ЧВ'],
            target_audience=['жители', 'семьи с детьми'],
            key_message="Вместе мы сделаем Коломну безопаснее!",
            narrative_type=NarrativeType.VISION,
            budget=5.0
        )
        print(f"  Кампания: {campaign.name}")
        print(f"  Инструменты: {[t.value for t in campaign.tools]}")
        print(f"  Каналы: {[ch.value for ch in campaign.channels]}")
        
        # 3. Генерация материалов
        print("\n📝 ГЕНЕРАЦИЯ МАТЕРИАЛОВ:")
        materials = await engineer.generate_materials(campaign.id)
        print(f"  Ключевых сообщений: {len(materials['key_messages'])}")
        print(f"  Постов для соцсетей: {len(materials['social_media_posts'])}")
        if materials['social_media_posts']:
            print(f"  Пример поста: {materials['social_media_posts'][0]['text'][:80]}...")
        
        # 4. Формирование нарратива
        print("\n🎯 ФОРМИРОВАНИЕ НАРРАТИВА:")
        narrative = await engineer.craft_narrative(
            target_vector='ЧВ',
            current_sentiment=-0.2,
            desired_change=0.3
        )
        print(f"  Стратегия: {narrative['strategy']}")
        print(f"  Ключевое сообщение: {narrative['key_message']['title']}")
        
        # 5. Дашборд
        print("\n📋 ДАШБОРД:")
        dashboard = await engineer.get_narrative_dashboard()
        print(f"  Всего кампаний: {dashboard['statistics']['total_campaigns']}")
        print(f"  Быстрые победы: {dashboard['quick_wins'][0]}")
        
        print("\n✅ Тест завершен")
    
    asyncio.run(demo())
