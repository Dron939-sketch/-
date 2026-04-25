#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 40: УПРАВЛЕНИЕ ПОВЕСТКОЙ ДЕПУТАТОВ (Deputy Agenda Manager) — облегчённая версия

Помощник координатора депутатского корпуса. Формирует список тем для освещения,
распределяет их между депутатами по компетенции (сектор/округ), готовит
черновики текстов и тезисы, ведёт учёт фактических публикаций.

Что осознанно НЕ делается (отличия от исходной версии):
- Нет метрики "лояльности администрации" — депутаты не ранжируются по лояльности.
- Нет party-based forbidden_topics — модуль не подавляет критику по партийному
  признаку.
- Нет генерации "волн" публикаций (wave 1/2/3) с расписанием для маскировки
  скоординированной активности под органический поток.
- `suggest_draft` возвращает явный ЧЕРНОВИК с пометкой DRAFT и тезисами для
  депутата, а не готовый пост "от его имени".
"""

import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ==================== МОДЕЛИ ====================

class DeputyRole(Enum):
    """Роли депутатов в информационной работе"""
    SPEAKER = "speaker"           # Основной спикер (комментирует широкий круг тем)
    SECTOR_LEAD = "sector_lead"   # Ведущий по сектору (ЖКХ, экономика, соцблок)
    DISTRICT_REP = "district_rep" # Представитель округа
    SUPPORT = "support"           # Поддержка (репосты, амплификация)
    NEUTRAL = "neutral"           # Нейтральный (узкая тематика)


class MessageTone(Enum):
    """Тональность сообщения. OFFENSIVE намеренно убран — модуль не предназначен
    для координированных атак на оппонентов."""
    POSITIVE = "positive"         # Позитивная (достижения, успехи)
    NEUTRAL = "neutral"           # Нейтральная (информирование)
    PROTECTIVE = "protective"     # Защитная (отвечаем на критику фактами)
    EXPLANATORY = "explanatory"   # Разъяснительная (объясняем решения)
    MOBILIZING = "mobilizing"     # Мобилизующая (приглашение к участию)


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
    """Модель депутата.

    Поле `loyalty` намеренно отсутствует. Сектор/округ — единственная основа
    для автоматического распределения тем.
    """
    id: str
    name: str
    role: DeputyRole
    district: str
    party: str
    sectors: List[str] = field(default_factory=list)
    followers: int = 0
    influence_score: float = 0.5
    telegram_channel: Optional[str] = None
    vk_page: Optional[str] = None


@dataclass
class TopicTask:
    """Тема для освещения"""
    id: str
    title: str
    description: str
    priority: str                       # critical / high / medium / low
    target_tone: MessageTone
    key_messages: List[str] = field(default_factory=list)
    talking_points: List[str] = field(default_factory=list)
    target_audience: List[str] = field(default_factory=lambda: ["all"])
    deadline: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=3))
    assigned_deputies: List[str] = field(default_factory=list)
    required_posts: int = 5
    completed_posts: int = 0
    status: str = "active"              # active / paused / completed
    source: str = "manual"              # manual / crisis / agenda / task_manager


@dataclass
class DeputyDraft:
    """Черновик публикации, который выдаётся депутату для согласования.

    `is_draft=True` — система возвращает именно черновик, не готовый пост от
    имени депутата. Депутат сам решает, что публиковать.
    """
    topic_id: str
    deputy_id: str
    deputy_name: str
    suggested_text: str
    talking_points: List[str]
    tone: str
    suggested_platform: str
    hashtags: List[str]
    is_draft: bool = True
    note: str = "Черновик для согласования. Депутат публикует под своей ответственностью."


@dataclass
class DeputyPost:
    """Фактическая публикация депутата (учёт)"""
    id: str
    deputy_id: str
    topic_id: str
    content: str
    platform: Platform
    published_at: datetime
    views: int = 0
    likes: int = 0
    comments: int = 0
    reposts: int = 0


@dataclass
class DeputyBriefing:
    """Брифинг для депутата.

    `forbidden_topics` оставлено как поле, но наполняется только из
    переданного администратором списка. Никаких автоматических ограничений
    по партии или роли модуль не накладывает.
    """
    id: str
    deputy_id: str
    deputy_name: str
    date: datetime
    topics: List[Dict[str, Any]]
    talking_points: List[str]
    recommended_hashtags: List[str]
    deadline: datetime
    forbidden_topics: List[str] = field(default_factory=list)
    read: bool = False


# ==================== ШАБЛОНЫ ====================

@dataclass
class MessageTemplate:
    id: str
    title: str
    body: str
    tone: MessageTone
    suggested_platform: Platform
    hashtags: List[str]


def _default_templates() -> Dict[str, MessageTemplate]:
    return {
        "achievement_report": MessageTemplate(
            id="achievement_report",
            title="Отчёт о работе",
            body="За {period} в {city} сделано: {achievements}.",
            tone=MessageTone.POSITIVE,
            suggested_platform=Platform.TELEGRAM,
            hashtags=["отчёт", "итоги"],
        ),
        "infrastructure_update": MessageTemplate(
            id="infrastructure_update",
            title="Инфраструктура",
            body="В {district} завершены работы: {works}. Срок — {deadline}.",
            tone=MessageTone.POSITIVE,
            suggested_platform=Platform.VK,
            hashtags=["благоустройство"],
        ),
        "explanation": MessageTemplate(
            id="explanation",
            title="Разъяснение решения",
            body="Почему принято решение по теме «{topic}»: {reason}. Ожидаемый эффект — {effect}.",
            tone=MessageTone.EXPLANATORY,
            suggested_platform=Platform.TELEGRAM,
            hashtags=["разъяснение"],
        ),
        "factual_response": MessageTemplate(
            id="factual_response",
            title="Фактический ответ",
            body="По теме «{topic}»: факты — {facts}. Источник — {source}.",
            tone=MessageTone.PROTECTIVE,
            suggested_platform=Platform.TELEGRAM,
            hashtags=["факты"],
        ),
        "invitation": MessageTemplate(
            id="invitation",
            title="Приглашение к участию",
            body="Приглашаем жителей {district} принять участие: {event}. Где и когда: {when_where}.",
            tone=MessageTone.MOBILIZING,
            suggested_platform=Platform.VK,
            hashtags=["участвуйте"],
        ),
    }


# ==================== ОСНОВНОЙ КЛАСС ====================

class DeputyAgendaManager:
    """In-memory менеджер повестки депутатов.

    Для продовой работы оборачивается слоем persistence (см. `db/deputy_queries.py`).
    Сам класс остаётся pure-Python, чтобы его можно было использовать без БД
    в тестах и скриптах.
    """

    def __init__(self, city_name: str):
        self.city_name = city_name
        self.deputies: Dict[str, Deputy] = {}
        self.topics: Dict[str, TopicTask] = {}
        self.posts: List[DeputyPost] = []
        self.briefings: List[DeputyBriefing] = []
        self.templates = _default_templates()

    # -------- депутаты --------

    def add_deputy(self, deputy: Deputy) -> None:
        self.deputies[deputy.id] = deputy

    def get_deputies_by_sector(self, sector: str) -> List[Deputy]:
        s = sector.lower()
        return [d for d in self.deputies.values() if any(x.lower() == s for x in d.sectors)]

    def get_deputies_by_district(self, district: str) -> List[Deputy]:
        d = district.lower()
        return [dep for dep in self.deputies.values() if dep.district.lower() == d]

    # -------- темы --------

    def create_topic(self, data: Dict[str, Any]) -> TopicTask:
        title = data["title"]
        topic_id = data.get("id") or f"topic_{hashlib.md5(title.encode('utf-8')).hexdigest()[:10]}"
        tone = data.get("target_tone", MessageTone.NEUTRAL)
        if isinstance(tone, str):
            tone = MessageTone(tone)
        topic = TopicTask(
            id=topic_id,
            title=title,
            description=data.get("description", ""),
            priority=data.get("priority", "medium"),
            target_tone=tone,
            key_messages=list(data.get("key_messages", [])),
            talking_points=list(data.get("talking_points", [])),
            target_audience=list(data.get("target_audience", ["all"])),
            deadline=data.get("deadline") or (datetime.now(timezone.utc) + timedelta(days=3)),
            required_posts=int(data.get("required_posts", 5)),
            source=data.get("source", "manual"),
        )
        self.topics[topic_id] = topic
        return topic

    def assign_deputies(
        self,
        topic_id: str,
        deputy_ids: Optional[List[str]] = None,
        *,
        auto: bool = True,
        max_assignees: int = 5,
    ) -> List[str]:
        """Назначить депутатов на тему.

        Если `deputy_ids` передан — используем его (ручное назначение).
        Иначе при `auto=True` подбираем по сектору/округу/роли SPEAKER.
        """
        topic = self.topics.get(topic_id)
        if topic is None:
            raise KeyError(f"topic {topic_id} not found")

        if deputy_ids is not None:
            chosen = [d for d in deputy_ids if d in self.deputies]
        elif auto:
            chosen = self._auto_assign(topic, max_assignees=max_assignees)
        else:
            chosen = []

        topic.assigned_deputies = chosen
        return chosen

    def _auto_assign(self, topic: TopicTask, *, max_assignees: int) -> List[str]:
        keywords = (topic.title + " " + " ".join(topic.key_messages)).lower()
        chosen: List[str] = []

        # SPEAKER берёт темы с высоким приоритетом
        if topic.priority in ("critical", "high"):
            for d in self.deputies.values():
                if d.role == DeputyRole.SPEAKER:
                    chosen.append(d.id)

        # Депутаты с подходящим сектором
        for d in self.deputies.values():
            if d.id in chosen:
                continue
            if any(s.lower() in keywords for s in d.sectors):
                chosen.append(d.id)

        # Представители округа, если округ назван в теме
        for d in self.deputies.values():
            if d.id in chosen:
                continue
            if d.district and d.district.lower() in keywords:
                chosen.append(d.id)

        return chosen[:max_assignees]

    # -------- черновики --------

    def suggest_draft(
        self,
        topic_id: str,
        deputy_id: str,
        *,
        platform: Optional[Platform] = None,
    ) -> DeputyDraft:
        """Сформировать ЧЕРНОВИК публикации для депутата.

        Возвращает черновик с пометкой `is_draft=True`. Фактический текст
        публикации остаётся за депутатом — модуль предлагает только структуру
        и тезисы.
        """
        topic = self.topics.get(topic_id)
        deputy = self.deputies.get(deputy_id)
        if topic is None or deputy is None:
            raise KeyError("topic or deputy not found")

        template = self._select_template(topic)
        suggested_platform = platform or template.suggested_platform

        # Подставляем плейсхолдеры — но оставляем их видимыми, чтобы депутат
        # дозаполнил конкретные цифры/факты сам.
        suggested_text = template.body.format(
            city=self.city_name,
            district=deputy.district or "—",
            period="[период]",
            achievements="[список достижений]",
            works="[виды работ]",
            deadline="[срок]",
            topic=topic.title,
            reason="[обоснование]",
            effect="[ожидаемый эффект]",
            facts="[конкретные факты]",
            source="[источник]",
            event="[событие]",
            when_where="[место и время]",
        )

        return DeputyDraft(
            topic_id=topic_id,
            deputy_id=deputy_id,
            deputy_name=deputy.name,
            suggested_text=suggested_text,
            talking_points=list(topic.talking_points),
            tone=topic.target_tone.value,
            suggested_platform=suggested_platform.value,
            hashtags=list(template.hashtags),
        )

    def _select_template(self, topic: TopicTask) -> MessageTemplate:
        tone = topic.target_tone
        if tone == MessageTone.POSITIVE:
            return self.templates["infrastructure_update"]
        if tone == MessageTone.PROTECTIVE:
            return self.templates["factual_response"]
        if tone == MessageTone.EXPLANATORY:
            return self.templates["explanation"]
        if tone == MessageTone.MOBILIZING:
            return self.templates["invitation"]
        return self.templates["achievement_report"]

    # -------- брифинги --------

    def build_briefing(
        self,
        deputy_id: str,
        *,
        forbidden_topics: Optional[List[str]] = None,
        recommended_hashtags: Optional[List[str]] = None,
        horizon_days: int = 1,
    ) -> Optional[DeputyBriefing]:
        deputy = self.deputies.get(deputy_id)
        if deputy is None:
            return None

        my_topics = [
            t for t in self.topics.values()
            if t.status == "active"
            and deputy_id in t.assigned_deputies
            and t.deadline > datetime.now(timezone.utc)
        ]
        if not my_topics:
            return None

        return DeputyBriefing(
            id=f"briefing_{deputy_id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
            deputy_id=deputy_id,
            deputy_name=deputy.name,
            date=datetime.now(timezone.utc),
            topics=[{
                "id": t.id,
                "title": t.title,
                "priority": t.priority,
                "key_messages": t.key_messages,
                "talking_points": t.talking_points,
                "tone": t.target_tone.value,
                "deadline": t.deadline.isoformat(),
            } for t in my_topics],
            talking_points=self._merge_talking_points(my_topics),
            recommended_hashtags=list(recommended_hashtags or []),
            forbidden_topics=list(forbidden_topics or []),
            deadline=datetime.now(timezone.utc) + timedelta(days=horizon_days),
        )

    def _merge_talking_points(self, topics: List[TopicTask]) -> List[str]:
        seen: Dict[str, None] = {}
        for t in topics:
            for p in t.talking_points:
                if p not in seen:
                    seen[p] = None
        return list(seen.keys())[:10]

    # -------- учёт публикаций --------

    def register_post(self, data: Dict[str, Any]) -> DeputyPost:
        platform = data["platform"]
        if isinstance(platform, str):
            platform = Platform(platform)
        published_at = data.get("published_at") or datetime.now(timezone.utc)
        deputy_id = data["deputy_id"]
        post_seed = f"{deputy_id}{published_at.isoformat()}".encode("utf-8")
        post = DeputyPost(
            id=data.get("id") or f"post_{hashlib.md5(post_seed).hexdigest()[:10]}",
            deputy_id=deputy_id,
            topic_id=data["topic_id"],
            content=data.get("content", ""),
            platform=platform,
            published_at=published_at,
            views=int(data.get("views", 0)),
            likes=int(data.get("likes", 0)),
            comments=int(data.get("comments", 0)),
            reposts=int(data.get("reposts", 0)),
        )
        self.posts.append(post)
        topic = self.topics.get(post.topic_id)
        if topic is not None:
            topic.completed_posts += 1
        return post

    # -------- отчёты --------

    def topic_report(self, topic_id: str) -> Dict[str, Any]:
        topic = self.topics.get(topic_id)
        if topic is None:
            return {"error": "topic not found"}
        topic_posts = [p for p in self.posts if p.topic_id == topic_id]
        per_deputy: Dict[str, int] = defaultdict(int)
        for p in topic_posts:
            per_deputy[p.deputy_id] += 1
        return {
            "topic_id": topic.id,
            "title": topic.title,
            "status": topic.status,
            "priority": topic.priority,
            "assigned": len(topic.assigned_deputies),
            "required_posts": topic.required_posts,
            "completed_posts": len(topic_posts),
            "completion_rate": round(len(topic_posts) / topic.required_posts, 2) if topic.required_posts else 0,
            "total_views": sum(p.views for p in topic_posts),
            "total_likes": sum(p.likes for p in topic_posts),
            "by_deputy": [
                {"deputy_id": did, "deputy_name": self.deputies[did].name if did in self.deputies else did, "posts": cnt}
                for did, cnt in per_deputy.items()
            ],
        }

    def coordinator_dashboard(self) -> Dict[str, Any]:
        active = [t for t in self.topics.values() if t.status == "active"]
        return {
            "city": self.city_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "totals": {
                "deputies": len(self.deputies),
                "active_topics": len(active),
                "completed_topics": len([t for t in self.topics.values() if t.status == "completed"]),
                "total_posts": len(self.posts),
            },
            "active_topics": [
                {
                    "id": t.id,
                    "title": t.title,
                    "priority": t.priority,
                    "assigned": len(t.assigned_deputies),
                    "completed": t.completed_posts,
                    "required": t.required_posts,
                    "deadline": t.deadline.isoformat(),
                    "source": t.source,
                }
                for t in sorted(active, key=lambda x: x.deadline)
            ],
        }
