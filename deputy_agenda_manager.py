#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 40: УПРАВЛЕНИЕ ПОВЕСТКОЙ ДЕПУТАТОВ (Deputy Agenda Manager)
Система формирования согласованной информационной повестки для депутатского корпуса

Позволяет:
- Распределять темы между депутатами
- Формировать единый информационный фронт
- Контролировать тональность выступлений
- Координировать публикации в соцсетях
- Отслеживать эффективность информационной работы
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


# ==================== МОДЕЛИ ====================

class DeputyRole(Enum):
    """Роли депутатов в информационной работе"""
    SPEAKER = "speaker"           # Основной спикер (комментирует всё)
    SECTOR_LEAD = "sector_lead"   # Ведущий по сектору (экономика, ЖКХ, соцблок)
    DISTRICT_REP = "district_rep" # Представитель района
    SUPPORT = "support"           # Поддержка (ретвиты, лайки, комментарии)
    NEUTRAL = "neutral"           # Нейтральный (не освещает острую повестку)


class MessageTone(Enum):
    """Тональность сообщения"""
    POSITIVE = "positive"         # Позитивная (достижения, успехи)
    NEUTRAL = "neutral"           # Нейтральная (информирование)
    PROTECTIVE = "protective"     # Защитная (отвечаем на критику)
    OFFENSIVE = "offensive"       # Наступательная (критикуем оппонентов)
    MOBILIZING = "mobilizing"     # Мобилизующая (призыв к действию)
    EXPLANATORY = "explanatory"   # Разъяснительная (объясняем решения)


class Platform(Enum):
    """Платформы для публикаций"""
    TELEGRAM = "telegram"
    VK = "vk"
    OK = "ok"
    WEBSITE = "website"
    MEDIA = "media"
    MEETING = "meeting"


@dataclass
class Deputy:
    """Модель депутата"""
    id: str
    name: str
    role: DeputyRole
    district: str                    # избирательный округ
    party: str                       # партийная принадлежность
    followers: int                   # подписчики в соцсетях
    sectors: List[str]               # курируемые сектора (ЖКХ, экономика, соцблок)
    influence_score: float           # 0-1, влияние в соцсетях
    loyalty: float                   # 0-1, лояльность к администрации
    telegram_channel: Optional[str]
    vk_page: Optional[str]
    

@dataclass
class MessageTemplate:
    """Шаблон сообщения"""
    id: str
    title: str
    body: str
    tone: MessageTone
    target_audience: str
    suggested_platform: Platform
    hashtags: List[str]
    estimated_reach: int


@dataclass
class DeputyPost:
    """Публикация депутата"""
    id: str
    deputy_id: str
    topic_id: str
    content: str
    platform: Platform
    published_at: datetime
    tone: MessageTone
    views: int = 0
    likes: int = 0
    comments: int = 0
    reposts: int = 0
    effectiveness_score: float = 0.0


@dataclass
class TopicTask:
    """Тема для освещения"""
    id: str
    title: str
    description: str
    priority: str                    # critical / high / medium / low
    target_tone: MessageTone
    key_messages: List[str]          # ключевые месседжи, которые нужно донести
    talking_points: List[str]        # тезисы для выступлений
    target_audience: List[str]       # целевая аудитория
    deadline: datetime
    assigned_deputies: List[str]     # ID депутатов
    required_posts: int              # сколько постов нужно
    scheduled_posts: int = 0
    completed_posts: int = 0
    status: str = "active"           # active/paused/completed


@dataclass
class DeputyBriefing:
    """Брифинг для депутата"""
    id: str
    deputy_id: str
    deputy_name: str
    date: datetime
    topics: List[Dict]               # темы для освещения
    approved_talking_points: List[str]  # согласованные тезисы
    forbidden_topics: List[str]      # что нельзя обсуждать
    recommended_hashtags: List[str]
    deadline: datetime
    read_status: bool = False
    acknowledgement_status: bool = False


# ==================== КЛАСС УПРАВЛЕНИЯ ====================

class DeputyAgendaManager:
    """
    Управление информационной повесткой депутатов
    
    Стратегия:
    - Единый информационный фронт
    - Распределение ролей (кто и что говорит)
    - Контроль тональности и месседжей
    """

    def __init__(self, city_name: str):
        self.city_name = city_name
        self.deputies: Dict[str, Deputy] = {}
        self.topics: Dict[str, TopicTask] = {}
        self.posts: List[DeputyPost] = []
        self.briefings: List[DeputyBriefing] = []
        self.message_templates = self._init_templates()
        
        logger.info(f"DeputyAgendaManager инициализирован для города {city_name}")

    def _init_templates(self) -> Dict[str, MessageTemplate]:
        """Инициализация шаблонов сообщений"""
        return {
            "budget_increase": MessageTemplate(
                id="budget_increase",
                title="Рост бюджета",
                body="Бюджет {city} вырос на {percent}% благодаря эффективной работе команды губернатора и главы города. Дополнительные средства пойдут на {projects}.",
                tone=MessageTone.POSITIVE,
                target_audience="all",
                suggested_platform=Platform.TELEGRAM,
                hashtags=["бюджет", "развитие", "нашидостижения"],
                estimated_reach=5000
            ),
            "road_repair": MessageTemplate(
                id="road_repair",
                title="Ремонт дорог",
                body="В {district} завершён ремонт {streets} общей протяжённостью {km} км. Работы выполнены по поручению главы города в срок.",
                tone=MessageTone.POSITIVE,
                target_audience="all",
                suggested_platform=Platform.VK,
                hashtags=["дороги", "благоустройство", "работаем"],
                estimated_reach=3000
            ),
            "crisis_response": MessageTemplate(
                id="crisis_response",
                title="О ситуации в городе",
                body="Ситуация находится на контроле главы города. Создан оперативный штаб. О результатах проинформируем дополнительно.",
                tone=MessageTone.PROTECTIVE,
                target_audience="all",
                suggested_platform=Platform.TELEGRAM,
                hashtags=["важно", "официально"],
                estimated_reach=8000
            ),
            "call_to_action": MessageTemplate(
                id="call_to_action",
                title="Примите участие!",
                body="Друзья, запускаем голосование по проекту {project}. Ваше мнение важно! Переходите по ссылке и выбирайте {options}.",
                tone=MessageTone.MOBILIZING,
                target_audience="youth",
                suggested_platform=Platform.VK,
                hashtags=["голосование", "решаемвместе"],
                estimated_reach=10000
            ),
            "achievement_report": MessageTemplate(
                id="achievement_report",
                title="Отчёт о работе",
                body="За {period} сделано: {achievements}. Спасибо команде главы города и жителям за поддержку!",
                tone=MessageTone.POSITIVE,
                target_audience="all",
                suggested_platform=Platform.MEETING,
                hashtags=["отчёт", "итоги", "развитие"],
                estimated_reach=2000
            ),
        }

    # ==================== 1. УПРАВЛЕНИЕ ДЕПУТАТАМИ ====================

    async def add_deputy(self, deputy: Deputy):
        """Добавление депутата в систему"""
        self.deputies[deputy.id] = deputy
        logger.info(f"Добавлен депутат: {deputy.name} ({deputy.role.value})")

    async def get_deputies_by_role(self, role: DeputyRole) -> List[Deputy]:
        """Получение депутатов по роли"""
        return [d for d in self.deputies.values() if d.role == role]

    async def get_deputies_by_district(self, district: str) -> List[Deputy]:
        """Депутаты по району"""
        return [d for d in self.deputies.values() if d.district == district]

    async def get_deputies_by_sector(self, sector: str) -> List[Deputy]:
        """Депутаты по сектору"""
        return [d for d in self.deputies.values() if sector in d.sectors]

    # ==================== 2. ФОРМИРОВАНИЕ ПОВЕСТКИ ====================

    async def create_topic(self, topic_data: Dict) -> TopicTask:
        """Создание темы для освещения"""
        topic_id = f"topic_{hashlib.md5(topic_data['title'].encode()).hexdigest()[:8]}"
        
        topic = TopicTask(
            id=topic_id,
            title=topic_data['title'],
            description=topic_data['description'],
            priority=topic_data['priority'],
            target_tone=topic_data.get('target_tone', MessageTone.NEUTRAL),
            key_messages=topic_data.get('key_messages', []),
            talking_points=topic_data.get('talking_points', []),
            target_audience=topic_data.get('target_audience', ['all']),
            deadline=topic_data.get('deadline', datetime.now() + timedelta(days=3)),
            assigned_deputies=[],
            required_posts=topic_data.get('required_posts', 5)
        )
        
        self.topics[topic_id] = topic
        logger.info(f"Создана тема: {topic.title} (приоритет {topic.priority})")
        return topic

    async def assign_deputies_to_topic(self, topic_id: str, deputy_ids: List[str], auto_assign: bool = True):
        """Назначение депутатов на тему"""
        topic = self.topics.get(topic_id)
        if not topic:
            raise ValueError(f"Тема {topic_id} не найдена")
        
        if auto_assign:
            deputy_ids = await self._auto_assign_deputies(topic)
        
        topic.assigned_deputies = deputy_ids
        logger.info(f"Теме '{topic.title}' назначено {len(deputy_ids)} депутатов")

    async def _auto_assign_deputies(self, topic: TopicTask) -> List[str]:
        """Автоматическое назначение депутатов на тему"""
        assigned = []
        
        # Определяем ключевые слова темы
        keywords = topic.title.lower() + " " + " ".join(topic.key_messages).lower()
        
        for deputy in self.deputies.values():
            # СПИКЕР получает всё
            if deputy.role == DeputyRole.SPEAKER:
                assigned.append(deputy.id)
                continue
            
            # Проверяем соответствие сектору
            for sector in deputy.sectors:
                if sector.lower() in keywords:
                    assigned.append(deputy.id)
                    break
            
            # Депутат района — если тема про его район
            if deputy.district.lower() in keywords:
                if deputy.id not in assigned:
                    assigned.append(deputy.id)
        
        # Ограничиваем количество (не более 5 на тему)
        return assigned[:5]

    async def generate_deputy_briefings(self) -> List[DeputyBriefing]:
        """Формирование брифингов для депутатов"""
        briefings = []
        active_topics = [t for t in self.topics.values() if t.status == "active" and t.deadline > datetime.now()]
        
        for deputy in self.deputies.values():
            # Какие темы этому депутату
            deputy_topics = [t for t in active_topics if deputy.id in t.assigned_deputies]
            
            if not deputy_topics:
                continue
            
            # Формируем брифинг
            briefing = DeputyBriefing(
                id=f"briefing_{deputy.id}_{datetime.now().strftime('%Y%m%d')}",
                deputy_id=deputy.id,
                deputy_name=deputy.name,
                date=datetime.now(),
                topics=[{
                    "title": t.title,
                    "priority": t.priority,
                    "key_messages": t.key_messages,
                    "talking_points": t.talking_points,
                    "target_tone": t.target_tone.value
                } for t in deputy_topics],
                approved_talking_points=self._get_talking_points(active_topics),
                forbidden_topics=self._get_forbidden_topics(deputy),
                recommended_hashtags=["Коломна", "Развитие", "НашиЛюди"],
                deadline=datetime.now() + timedelta(days=1)
            )
            briefings.append(briefing)
            self.briefings.append(briefing)
        
        logger.info(f"Сформировано {len(briefings)} брифингов")
        return briefings

    def _get_talking_points(self, topics: List[TopicTask]) -> List[str]:
        """Формирование единых тезисов"""
        all_points = []
        for topic in topics:
            all_points.extend(topic.talking_points)
        return list(set(all_points))[:10]

    def _get_forbidden_topics(self, deputy: Deputy) -> List[str]:
        """Запрещённые темы для депутата"""
        forbidden = []
        
        if deputy.role == DeputyRole.SUPPORT:
            forbidden.extend(["критика", "альтернативные предложения"])
        
        if deputy.party != "Единая Россия":
            forbidden.extend(["критика партии власти"])
        
        return forbidden

    # ==================== 3. ГЕНЕРАЦИЯ КОНТЕНТА ====================

    async def generate_post_content(self, topic_id: str, deputy_id: str, platform: Platform = None) -> Dict:
        """Генерация контента для публикации"""
        topic = self.topics.get(topic_id)
        deputy = self.deputies.get(deputy_id)
        
        if not topic or not deputy:
            return {"error": "Topic or deputy not found"}
        
        # Выбираем шаблон
        template = self._select_template(topic, deputy)
        
        # Персонализируем контент
        content = template.body.format(
            city=self.city_name,
            district=deputy.district,
            percent="15",
            projects="ремонт дорог и благоустройство дворов",
            streets="ул. Ленина, ул. Октябрьской революции",
            km="5",
            period="последние полгода",
            achievements="открыт новый парк, отремонтирована школа, запущен фестиваль",
            project="«Народный бюджет»",
            options="парк, спортплощадка, детский городок"
        )
        
        # Добавляем подпись депутата
        signature = f"\n\n@{deputy.telegram_channel}" if deputy.telegram_channel else ""
        
        return {
            "topic_id": topic_id,
            "deputy_id": deputy_id,
            "deputy_name": deputy.name,
            "content": content + signature,
            "tone": template.tone.value,
            "platform": platform or template.suggested_platform.value,
            "hashtags": " ".join([f"#{h}" for h in template.hashtags]),
            "key_messages": topic.key_messages,
            "talking_points": topic.talking_points[:3],
            "estimated_reach": template.estimated_reach
        }

    def _select_template(self, topic: TopicTask, deputy: Deputy) -> MessageTemplate:
        """Выбор шаблона под тему и депутата"""
        if topic.target_tone == MessageTone.POSITIVE:
            if "бюджет" in topic.title.lower():
                return self.message_templates["budget_increase"]
            elif "дорог" in topic.title.lower():
                return self.message_templates["road_repair"]
            elif "отчёт" in topic.title.lower():
                return self.message_templates["achievement_report"]
        
        if topic.target_tone == MessageTone.MOBILIZING:
            return self.message_templates["call_to_action"]
        
        if topic.target_tone == MessageTone.PROTECTIVE:
            return self.message_templates["crisis_response"]
        
        # Дефолтный шаблон
        return self.message_templates["budget_increase"]

    # ==================== 4. ПЛАНИРОВАНИЕ ПУБЛИКАЦИЙ ====================

    async def create_publication_plan(self, topic_id: str) -> List[Dict]:
        """Создание плана публикаций по теме"""
        topic = self.topics.get(topic_id)
        if not topic:
            return []
        
        plan = []
        deadline_days = (topic.deadline - datetime.now()).days
        
        for i, deputy_id in enumerate(topic.assigned_deputies):
            deputy = self.deputies.get(deputy_id)
            if not deputy:
                continue
            
            # Распределяем публикации по времени
            offset_hours = i * (24 / max(len(topic.assigned_deputies), 1))
            scheduled_time = datetime.now() + timedelta(hours=offset_hours)
            
            # Выбираем платформу
            if deputy.role == DeputyRole.SPEAKER:
                platforms = [Platform.TELEGRAM, Platform.VK, Platform.MEDIA]
            elif deputy.role == DeputyRole.SUPPORT:
                platforms = [Platform.VK, Platform.OK]
            else:
                platforms = [Platform.TELEGRAM, Platform.VK]
            
            post_content = await self.generate_post_content(topic_id, deputy_id, platforms[0])
            
            plan.append({
                "deputy_name": deputy.name,
                "role": deputy.role.value,
                "scheduled_time": scheduled_time.isoformat(),
                "platform": platforms[0].value,
                "content": post_content["content"],
                "hashtags": post_content["hashtags"],
                "tone": post_content["tone"]
            })
        
        return plan

    async def generate_coordinated_posts(self, topic_id: str) -> Dict:
        """Генерация скоординированных постов (волна)"""
        plan = await self.create_publication_plan(topic_id)
        
        # Группировка по времени
        waves = {
            "first_wave": [],    # первые 30% депутатов
            "second_wave": [],   # следующие 40%
            "third_wave": []     # оставшиеся 30%
        }
        
        total = len(plan)
        first_count = int(total * 0.3)
        second_count = int(total * 0.4)
        
        for i, post in enumerate(plan):
            if i < first_count:
                waves["first_wave"].append(post)
            elif i < first_count + second_count:
                waves["second_wave"].append(post)
            else:
                waves["third_wave"].append(post)
        
        return {
            "topic_id": topic_id,
            "topic_title": self.topics[topic_id].title,
            "total_posts": total,
            "waves": waves,
            "interval_hours": 3,
            "recommendation": "Первую волну запустить в 10:00, вторую в 13:00, третью в 16:00"
        }

    # ==================== 5. КОНТРОЛЬ И АНАЛИТИКА ====================

    async def register_post(self, post_data: Dict) -> DeputyPost:
        """Регистрация опубликованного поста"""
        post = DeputyPost(
            id=f"post_{hashlib.md5(f'{post_data['deputy_id']}{datetime.now().isoformat()}'.encode()).hexdigest()[:8]}",
            deputy_id=post_data['deputy_id'],
            topic_id=post_data['topic_id'],
            content=post_data['content'],
            platform=Platform(post_data['platform']),
            published_at=datetime.now(),
            tone=MessageTone(post_data['tone']),
            views=post_data.get('views', 0),
            likes=post_data.get('likes', 0),
            comments=post_data.get('comments', 0),
            reposts=post_data.get('reposts', 0)
        )
        
        self.posts.append(post)
        
        # Обновляем счётчики темы
        topic = self.topics.get(post_data['topic_id'])
        if topic:
            topic.scheduled_posts += 1
            topic.completed_posts += 1
        
        logger.info(f"Зарегистрирован пост от {post_data['deputy_id']}")
        return post

    async def get_campaign_report(self, topic_id: str) -> Dict:
        """Отчёт по информационной кампании"""
        topic = self.topics.get(topic_id)
        if not topic:
            return {"error": "Topic not found"}
        
        topic_posts = [p for p in self.posts if p.topic_id == topic_id]
        
        total_views = sum(p.views for p in topic_posts)
        total_likes = sum(p.likes for p in topic_posts)
        total_comments = sum(p.comments for p in topic_posts)
        total_reposts = sum(p.reposts for p in topic_posts)
        
        return {
            "topic_title": topic.title,
            "status": topic.status,
            "assigned_deputies": len(topic.assigned_deputies),
            "posts_published": len(topic_posts),
            "posts_required": topic.required_posts,
            "completion_rate": len(topic_posts) / topic.required_posts if topic.required_posts else 0,
            "total_reach": total_views,
            "engagement": {
                "likes": total_likes,
                "comments": total_comments,
                "reposts": total_reposts
            },
            "effectiveness_score": (total_likes + total_comments * 2 + total_reposts * 3) / max(total_views, 1),
            "deputy_performance": [
                {
                    "deputy": self.deputies.get(p.deputy_id).name if self.deputies.get(p.deputy_id) else p.deputy_id,
                    "posts": len([x for x in topic_posts if x.deputy_id == p.deputy_id]),
                    "views": p.views
                }
                for p in topic_posts
            ][:5]
        }

    # ==================== 6. ДАШБОРД ====================

    async def get_deputy_dashboard(self, deputy_id: str) -> Dict:
        """Дашборд для конкретного депутата"""
        deputy = self.deputies.get(deputy_id)
        if not deputy:
            return {"error": "Deputy not found"}
        
        my_topics = [t for t in self.topics.values() if deputy_id in t.assigned_deputies and t.status == "active"]
        my_posts = [p for p in self.posts if p.deputy_id == deputy_id]
        
        return {
            "deputy_name": deputy.name,
            "role": deputy.role.value,
            "district": deputy.district,
            "active_tasks": len(my_topics),
            "posts_published": len(my_posts),
            "upcoming_deadlines": [
                {"title": t.title, "deadline": t.deadline.isoformat()}
                for t in my_topics if t.deadline > datetime.now()
            ][:5],
            "pending_briefings": len([b for b in self.briefings if b.deputy_id == deputy_id and not b.read_status]),
            "performance": {
                "total_views": sum(p.views for p in my_posts),
                "total_likes": sum(p.likes for p in my_posts),
                "avg_effectiveness": sum(p.effectiveness_score for p in my_posts) / len(my_posts) if my_posts else 0
            },
            "next_actions": [
                f"Осветить тему: {t.title}" for t in my_topics[:3]
            ]
        }

    async def get_coordinator_dashboard(self) -> Dict:
        """Дашборд для координатора информационной работы"""
        active_topics = [t for t in self.topics.values() if t.status == "active"]
        completed_topics = [t for t in self.topics.values() if t.status == "completed"]
        
        all_posts = self.posts
        total_reach = sum(p.views for p in all_posts)
        
        return {
            "city": self.city_name,
            "timestamp": datetime.now().isoformat(),
            "statistics": {
                "total_deputies": len(self.deputies),
                "active_campaigns": len(active_topics),
                "completed_campaigns": len(completed_topics),
                "total_posts": len(all_posts),
                "total_reach": total_reach
            },
            "active_campaigns": [
                {
                    "title": t.title,
                    "priority": t.priority,
                    "deadline": t.deadline.isoformat(),
                    "progress": f"{t.completed_posts}/{t.required_posts}",
                    "assigned": len(t.assigned_deputies)
                }
                for t in active_topics[:5]
            ],
            "deputy_ranking": sorted(
                self.deputies.values(),
                key=lambda d: len([p for p in all_posts if p.deputy_id == d.id]),
                reverse=True
            )[:5],
            "pending_briefings": len([b for b in self.briefings if not b.read_status]),
            "recommendations": [
                "⚠️ Критическая тема «Бюджет» требует охвата — назначьте спикеров",
                "📢 Запустить волну постов по теме «Благоустройство» завтра в 10:00",
                "📊 Депутат Иванов показывает низкую эффективность — провести брифинг"
            ]
        }


# ==================== ПРИМЕР ====================

async def demo():
    print("=" * 70)
    print("🏛️ УПРАВЛЕНИЕ ПОВЕСТКОЙ ДЕПУТАТОВ")
    print("=" * 70)
    
    manager = DeputyAgendaManager("Коломна")
    
    # 1. Добавляем депутатов
    print("\n📋 ДОБАВЛЕНИЕ ДЕПУТАТОВ:")
    
    deputies_data = [
        Deputy("dep_001", "Иванов Иван", DeputyRole.SPEAKER, "Центральный", "Единая Россия", 15000, ["все"], 0.95, 0.98, "ivanov_telegram", "ivanov_vk"),
        Deputy("dep_002", "Петров Пётр", DeputyRole.SECTOR_LEAD, "Колычёво", "Единая Россия", 8000, ["ЖКХ", "благоустройство"], 0.82, 0.92, "petrov_telegram", "petrov_vk"),
        Deputy("dep_003", "Сидорова Мария", DeputyRole.SECTOR_LEAD, "Щурово", "Единая Россия", 5000, ["соцблок", "образование"], 0.78, 0.90, "sidorova_tg", "sidorova_vk"),
        Deputy("dep_004", "Козлов Дмитрий", DeputyRole.DISTRICT_REP, "Голутвин", "Единая Россия", 3000, ["транспорт"], 0.65, 0.85, None, "kozlov_vk"),
        Deputy("dep_005", "Новикова Анна", DeputyRole.SUPPORT, "Запрудня", "Единая Россия", 2000, [], 0.55, 0.80, None, None),
    ]
    
    for d in deputies_data:
        await manager.add_deputy(d)
        print(f"  + {d.name} — {d.role.value}, округ {d.district}")
    
    # 2. Создаём тему
    print("\n🎯 СОЗДАНИЕ ИНФОРМАЦИОННОЙ КАМПАНИИ:")
    
    topic = await manager.create_topic({
        "title": "Благоустройство дворовых территорий",
        "description": "Освещение программы благоустройства дворов в 2026 году",
        "priority": "high",
        "target_tone": MessageTone.POSITIVE,
        "key_messages": [
            "За 2 года благоустроено 45 дворов",
            "Установлены детские и спортивные площадки",
            "Жители выбирают проекты через голосование"
        ],
        "talking_points": [
            "Команда главы города выполняет обещания",
            "Благоустройство идёт по нацпроекту",
            "Жители активно участвуют в выборе проектов"
        ],
        "target_audience": ["all"],
        "required_posts": 8
    })
    print(f"  Создана тема: {topic.title}")
    
    # 3. Назначаем депутатов
    await manager.assign_deputies_to_topic(topic.id, [])
    print(f"  Назначено депутатов: {len(topic.assigned_deputies)}")
    
    # 4. Генерация постов
    print("\n📝 ГЕНЕРАЦИЯ ПОСТОВ:")
    
    for deputy_id in topic.assigned_deputies[:3]:
        post = await manager.generate_post_content(topic.id, deputy_id)
        print(f"  • {post['deputy_name']}: {post['content'][:60]}...")
    
    # 5. План публикаций
    print("\n📅 ПЛАН ПУБЛИКАЦИЙ:")
    plan = await manager.create_publication_plan(topic.id)
    for p in plan[:3]:
        print(f"  • {p['deputy_name']} — {p['scheduled_time'][:16]} — {p['platform']}")
    
    # 6. Дашборд координатора
    print("\n📊 ДАШБОРД КООРДИНАТОРА:")
    dashboard = await manager.get_coordinator_dashboard()
    print(f"  Всего депутатов: {dashboard['statistics']['total_deputies']}")
    print(f"  Активных кампаний: {dashboard['statistics']['active_campaigns']}")
    print(f"  Всего постов: {dashboard['statistics']['total_posts']}")
    
    print("\n✅ Готово!")

if __name__ == "__main__":
    asyncio.run(demo())
