#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 21: РЕПУТАЦИОННЫЙ МОНИТОРИНГ И АНТИКРИЗИСНЫЙ PR (Reputation Guard)
Система защиты репутации мэра и администрации города

Основан на методах:
- Мониторинг упоминаний в реальном времени
- Раннее обнаружение репутационных угроз
- Анализ тональности публикаций о мэре
- Генерация антикризисных коммуникаций
- Сравнение репутации с соседними городами
"""

import asyncio
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, Counter
import logging
import json
import hashlib

logger = logging.getLogger(__name__)


# ==================== МОДЕЛИ ДАННЫХ ====================

class ReputationRisk(Enum):
    """Уровни репутационного риска"""
    CRITICAL = "critical"   # Критический — немедленное вмешательство
    HIGH = "high"           # Высокий — вмешательство в течение 24 часов
    MEDIUM = "medium"       # Средний — мониторинг и план
    LOW = "low"             # Низкий — наблюдение


class ThreatType(Enum):
    """Типы репутационных угроз"""
    CORRUPTION = "corruption"           # Коррупционный скандал
    INCOMPETENCE = "incompetence"       # Обвинение в некомпетентности
    SCANDAL = "scandal"                 # Личный скандал
    FAILURE = "failure"                 # Провал проекта
    INJUSTICE = "injustice"             # Несправедливое решение
    FAKE = "fake"                       # Фейковая новость
    COMPARISON = "comparison"           # Негативное сравнение


@dataclass
class Mention:
    """Упоминание мэра или администрации"""
    id: str
    source: str                         # Telegram/VK/News/Forum
    text: str
    author: str
    published_at: datetime
    sentiment: float                    # -1 до +1
    threat_type: Optional[ThreatType]
    risk_level: ReputationRisk
    reach: int                          # охват (просмотры)
    url: str


@dataclass
class ReputationAlert:
    """Оповещение о репутационной угрозе"""
    id: str
    title: str
    description: str
    threat_type: ThreatType
    risk_level: ReputationRisk
    mentions: List[Mention]
    first_seen: datetime
    velocity: float                     # скорость распространения
    recommended_action: str
    status: str = "active"              # active/mitigated/resolved


@dataclass
class MayorRating:
    """Рейтинг мэра"""
    timestamp: datetime
    overall_score: float                # 0-1
    trust_score: float                  # доверие
    approval_score: float               # одобрение
    trend: str                          # rising/stable/declining
    compared_to_region: float           # сравнение с регионом
    compared_to_neighbors: float        # сравнение с соседями


# ==================== КОНФИГУРАЦИЯ ====================

class ReputationConfig:
    """Конфигурация системы репутационного мониторинга"""
    
    # Ключевые слова для детекции угроз
    THREAT_KEYWORDS = {
        ThreatType.CORRUPTION: [
            'коррупц', 'взятк', 'откат', 'схем', 'воруют', 'распил',
            'крышеван', 'отмыв', 'нажив'
        ],
        ThreatType.INCOMPETENCE: [
            'некомпетент', 'бездар', 'профан', 'дилетант', 'не справл',
            'не умеет', 'не может', 'провал', 'позор'
        ],
        ThreatType.SCANDAL: [
            'скандал', 'компромат', 'тайн', 'любовниц', 'незаконн',
            'интриг', 'закулисн'
        ],
        ThreatType.FAILURE: [
            'провал', 'позор', 'неудач', 'провалил', 'сорвал',
            'не выполнил', 'обманул'
        ],
        ThreatType.FAKE: [
            'фейк', 'ложь', 'врут', 'дезинформац', 'фальшивк'
        ]
    }
    
    # Веса для расчёта рейтинга
    RATING_WEIGHTS = {
        'sentiment': 0.35,
        'trust': 0.30,
        'achievements': 0.20,
        'comparison': 0.15
    }
    
    # Пороги оповещений
    ALERT_THRESHOLDS = {
        'critical_mentions_per_hour': 50,
        'negative_sentiment_threshold': -0.6,
        'velocity_threshold': 20  # упоминаний в час
    }


# ==================== ОСНОВНОЙ КЛАСС ====================

class ReputationGuard:
    """
    Система защиты репутации мэра и администрации
    
    Позволяет:
    - Мониторить все упоминания в реальном времени
    - Обнаруживать репутационные угрозы на ранней стадии
    - Получать рекомендации по антикризисным коммуникациям
    - Отслеживать динамику рейтинга мэра
    """
    
    def __init__(self, city_name: str, mayor_name: str, config: ReputationConfig = None):
        self.city_name = city_name
        self.mayor_name = mayor_name
        self.config = config or ReputationConfig()
        
        # Хранилище
        self.mentions: List[Mention] = []
        self.alerts: List[ReputationAlert] = []
        self.rating_history: List[MayorRating] = []
        
        # Ключевые слова для поиска
        self.mayor_keywords = [mayor_name.lower(), f"глава {city_name.lower()}", f"мэр {city_name.lower()}"]
        
        # Статистика
        self.stats = {
            'total_mentions': 0,
            'positive_mentions': 0,
            'negative_mentions': 0,
            'avg_sentiment': 0
        }
        
        logger.info(f"ReputationGuard инициализирован для города {city_name}, мэр {mayor_name}")
    
    # ==================== 1. СБОР УПОМИНАНИЙ ====================
    
    async def collect_mentions(self, sources_data: List[Dict]) -> List[Mention]:
        """
        Сбор упоминаний мэра из всех источников
        """
        logger.info("Сбор упоминаний мэра...")
        
        new_mentions = []
        
        for source in sources_data:
            source_type = source.get('type', 'unknown')
            items = source.get('items', [])
            
            for item in items:
                text = item.get('text', '').lower()
                
                # Проверяем, есть ли упоминание мэра
                if not any(kw in text for kw in self.mayor_keywords):
                    continue
                
                # Анализ тональности
                sentiment = self._analyze_sentiment(text)
                
                # Определение типа угрозы
                threat_type, risk_level = self._classify_threat(text, sentiment)
                
                mention = Mention(
                    id=f"m_{hashlib.md5(f'{source_type}_{item.get('id', '')}_{datetime.now().isoformat()}'.encode()).hexdigest()[:8]}",
                    source=source_type,
                    text=text[:500],
                    author=item.get('author', 'anonymous'),
                    published_at=item.get('date', datetime.now()),
                    sentiment=sentiment,
                    threat_type=threat_type,
                    risk_level=risk_level,
                    reach=item.get('views', 100),
                    url=item.get('url', '')
                )
                new_mentions.append(mention)
        
        self.mentions.extend(new_mentions)
        
        # Очищаем старые упоминания (старше 90 дней)
        cutoff = datetime.now() - timedelta(days=90)
        self.mentions = [m for m in self.mentions if m.published_at > cutoff]
        
        # Обновляем статистику
        self._update_stats()
        
        logger.info(f"Собрано {len(new_mentions)} новых упоминаний")
        return new_mentions
    
    def _analyze_sentiment(self, text: str) -> float:
        """Анализ тональности текста (упрощённая версия)"""
        positive_words = ['спасибо', 'молодец', 'отлично', 'хорошо', 'нравится', 
                         'горжусь', 'эффективно', 'быстро', 'качественно']
        negative_words = ['плохо', 'ужасно', 'позор', 'безобразие', 'возмутительно',
                         'недоволен', 'провал', 'бездарно', 'некомпетентно']
        
        text_lower = text.lower()
        
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        
        if pos_count + neg_count == 0:
            return 0
        
        sentiment = (pos_count - neg_count) / (pos_count + neg_count)
        return max(-1, min(1, sentiment))
    
    def _classify_threat(self, text: str, sentiment: float) -> Tuple[Optional[ThreatType], ReputationRisk]:
        """Классификация угрозы"""
        if sentiment >= 0:
            return None, ReputationRisk.LOW
        
        text_lower = text.lower()
        
        for threat_type, keywords in self.config.THREAT_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                # Определяем уровень риска
                if sentiment < -0.7:
                    risk = ReputationRisk.CRITICAL
                elif sentiment < -0.5:
                    risk = ReputationRisk.HIGH
                elif sentiment < -0.3:
                    risk = ReputationRisk.MEDIUM
                else:
                    risk = ReputationRisk.LOW
                
                return threat_type, risk
        
        # Не классифицировано
        if sentiment < -0.5:
            return ThreatType.INCOMPETENCE, ReputationRisk.MEDIUM
        elif sentiment < -0.3:
            return None, ReputationRisk.LOW
        else:
            return None, ReputationRisk.LOW
    
    def _update_stats(self):
        """Обновление статистики"""
        recent_mentions = [m for m in self.mentions 
                          if m.published_at > datetime.now() - timedelta(days=30)]
        
        self.stats['total_mentions'] = len(recent_mentions)
        self.stats['positive_mentions'] = sum(1 for m in recent_mentions if m.sentiment > 0.2)
        self.stats['negative_mentions'] = sum(1 for m in recent_mentions if m.sentiment < -0.2)
        
        if recent_mentions:
            self.stats['avg_sentiment'] = sum(m.sentiment for m in recent_mentions) / len(recent_mentions)
    
    # ==================== 2. ОБНАРУЖЕНИЕ УГРОЗ ====================
    
    async def detect_threats(self, window_hours: int = 24) -> List[ReputationAlert]:
        """
        Обнаружение репутационных угроз
        """
        logger.info("Обнаружение репутационных угроз...")
        
        cutoff = datetime.now() - timedelta(hours=window_hours)
        recent_mentions = [m for m in self.mentions if m.published_at > cutoff]
        
        # Группировка по типу угрозы
        threats_by_type = defaultdict(list)
        for mention in recent_mentions:
            if mention.threat_type:
                threats_by_type[mention.threat_type].append(mention)
        
        new_alerts = []
        
        for threat_type, mentions in threats_by_type.items():
            # Проверяем, достигнут ли порог
            if len(mentions) < 5:
                continue
            
            # Скорость распространения
            first_time = min(m.published_at for m in mentions)
            hours = (datetime.now() - first_time).total_seconds() / 3600
            velocity = len(mentions) / max(hours, 0.1)
            
            # Уровень риска
            max_risk = max(m.risk_level for m in mentions)
            
            # Создаём оповещение
            alert = ReputationAlert(
                id=f"alert_{threat_type.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                title=self._get_alert_title(threat_type),
                description=self._get_alert_description(threat_type, mentions),
                threat_type=threat_type,
                risk_level=max_risk,
                mentions=mentions[:10],
                first_seen=first_time,
                velocity=velocity,
                recommended_action=self._get_recommended_action(threat_type, max_risk),
                status="active"
            )
            new_alerts.append(alert)
            self.alerts.append(alert)
        
        # Сортируем по уровню риска
        risk_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        new_alerts.sort(key=lambda x: risk_order.get(x.risk_level.value, 0), reverse=True)
        
        logger.info(f"Обнаружено {len(new_alerts)} репутационных угроз")
        return new_alerts
    
    def _get_alert_title(self, threat_type: ThreatType) -> str:
        """Заголовок оповещения"""
        titles = {
            ThreatType.CORRUPTION: "Коррупционный скандал",
            ThreatType.INCOMPETENCE: "Обвинения в некомпетентности",
            ThreatType.SCANDAL: "Личный скандал",
            ThreatType.FAILURE: "Провал проекта",
            ThreatType.FAKE: "Фейковая новость",
            ThreatType.COMPARISON: "Негативное сравнение"
        }
        return titles.get(threat_type, "Репутационная угроза")
    
    def _get_alert_description(self, threat_type: ThreatType, mentions: List[Mention]) -> str:
        """Описание угрозы"""
        count = len(mentions)
        avg_sentiment = sum(m.sentiment for m in mentions) / count
        
        return f"Обнаружено {count} негативных упоминаний (средняя тональность {avg_sentiment:.2f}) по теме {threat_type.value}"
    
    def _get_recommended_action(self, threat_type: ThreatType, risk_level: ReputationRisk) -> str:
        """Рекомендованное действие"""
        actions = {
            (ThreatType.CORRUPTION, ReputationRisk.CRITICAL): 
                "НЕМЕДЛЕННО: Публичное опровержение, открытое расследование, встреча с журналистами",
            (ThreatType.CORRUPTION, ReputationRisk.HIGH): 
                "СРОЧНО: Заявление пресс-службы, проверка фактов, юридическая оценка",
            (ThreatType.INCOMPETENCE, ReputationRisk.CRITICAL): 
                "НЕМЕДЛЕННО: Публичный отчёт о достижениях, прямая линия с мэром",
            (ThreatType.FAKE, ReputationRisk.HIGH): 
                "СРОЧНО: Опровержение с фактами, мониторинг распространения",
            (ThreatType.FAILURE, ReputationRisk.CRITICAL): 
                "НЕМЕДЛЕННО: Признание ошибки, план исправления, компенсации"
        }
        
        return actions.get((threat_type, risk_level), "Усилить мониторинг, подготовить коммуникацию")
    
    # ==================== 3. РАСЧЁТ РЕЙТИНГА ====================
    
    async def calculate_rating(self) -> MayorRating:
        """
        Расчёт текущего рейтинга мэра
        """
        # 1. Сентимент-оценка (на основе упоминаний за 30 дней)
        recent_mentions = [m for m in self.mentions 
                          if m.published_at > datetime.now() - timedelta(days=30)]
        
        if recent_mentions:
            sentiment_score = (self.stats['avg_sentiment'] + 1) / 2
        else:
            sentiment_score = 0.5
        
        # 2. Доверие (на основе опросов или анализ обращений)
        trust_score = await self._calculate_trust_score()
        
        # 3. Достижения (на основе реализованных проектов)
        achievements_score = await self._calculate_achievements_score()
        
        # 4. Сравнение с соседями
        comparison_score = await self._calculate_comparison_score()
        
        # Итоговый рейтинг
        weights = self.config.RATING_WEIGHTS
        overall = (
            sentiment_score * weights['sentiment'] +
            trust_score * weights['trust'] +
            achievements_score * weights['achievements'] +
            comparison_score * weights['comparison']
        )
        
        # Тренд
        if len(self.rating_history) > 0:
            prev = self.rating_history[-1].overall_score
            if overall > prev + 0.03:
                trend = "rising"
            elif overall < prev - 0.03:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        rating = MayorRating(
            timestamp=datetime.now(),
            overall_score=overall,
            trust_score=trust_score,
            approval_score=sentiment_score,
            trend=trend,
            compared_to_region=0.52,  # заглушка, в реальности — данные по региону
            compared_to_neighbors=0.48  # заглушка
        )
        
        self.rating_history.append(rating)
        
        # Оставляем историю за 2 года
        if len(self.rating_history) > 730:
            self.rating_history = self.rating_history[-730:]
        
        logger.info(f"Рейтинг мэра: {overall:.0%} ({trend})")
        return rating
    
    async def _calculate_trust_score(self) -> float:
        """Расчёт индекса доверия"""
        # В реальности — интеграция с опросами и обращениями
        # Упрощённо — на основе тональности
        return self.stats['avg_sentiment'] * 0.5 + 0.5
    
    async def _calculate_achievements_score(self) -> float:
        """Расчёт оценки достижений"""
        # В реальности — количество выполненных обещаний, проектов
        return 0.65
    
    async def _calculate_comparison_score(self) -> float:
        """Сравнение с соседними городами"""
        # В реальности — данные по соседям
        return 0.55
    
    # ==================== 4. АНТИКРИЗИСНЫЕ КОММУНИКАЦИИ ====================
    
    async def generate_crisis_response(self, alert_id: str) -> Dict[str, Any]:
        """
        Генерация антикризисной коммуникации
        """
        alert = next((a for a in self.alerts if a.id == alert_id), None)
        if not alert:
            return {'error': 'Alert not found'}
        
        response = {
            'alert_id': alert.id,
            'threat_type': alert.threat_type.value,
            'risk_level': alert.risk_level.value,
            'generated_at': datetime.now().isoformat(),
            'press_release': None,
            'social_media_post': None,
            'mayor_statement': None,
            'action_plan': []
        }
        
        # Генерация пресс-релиза
        if alert.threat_type == ThreatType.CORRUPTION:
            response['press_release'] = {
                'title': f"Заявление администрации города {self.city_name}",
                'body': f"В связи с появившимися в информационном поле сообщениями администрация города заявляет, что все факты будут тщательно проверены. Мы открыты для диалога и готовы предоставить всю запрашиваемую информацию в установленном порядке.",
                'quote': f"«Мы не комментируем неподтверждённую информацию до завершения проверки», — заявил глава города {self.mayor_name}."
            }
            response['action_plan'] = [
                "Создать рабочую группу для проверки фактов (24 часа)",
                "Подготовить официальное заявление (12 часов)",
                "Провести встречу с журналистами (48 часов)",
                "Опубликовать результаты проверки (7 дней)"
            ]
        
        elif alert.threat_type == ThreatType.INCOMPETENCE:
            response['social_media_post'] = {
                'platform': 'Telegram',
                'text': f"📊 Друзья, сегодня хотим поделиться с вами ключевыми достижениями города {self.city_name} за последние полгода. Открыли 3 новых парка, отремонтировали 15 км дорог, создали 200 рабочих мест. Мы работаем для вас и открыты к обратной связи!",
                'hashtags': ['Коломна', 'Развитие', 'Достижения']
            }
            response['action_plan'] = [
                "Опубликовать отчёт о достижениях (24 часа)",
                "Провести прямую линию с мэром (3 дня)",
                "Организовать встречу с жителями (7 дней)"
            ]
        
        elif alert.threat_type == ThreatType.FAKE:
            response['mayor_statement'] = {
                'title': "Опровержение недостоверной информации",
                'text': f"Уважаемые жители! В сети появилась информация, не соответствующая действительности. Призываю вас проверять факты и доверять только официальным источникам. Администрация города подготовила подробное опровержение с фактами и доказательствами."
            }
            response['action_plan'] = [
                "Подготовить факт-чекинг (6 часов)",
                "Опубликовать опровержение (12 часов)",
                "Направить жалобу в Роскомнадзор (24 часа)"
            ]
        
        return response
    
    # ==================== 5. ДАШБОРД ====================
    
    async def get_reputation_dashboard(self) -> Dict[str, Any]:
        """
        Дашборд репутации для мэра
        """
        # Текущий рейтинг
        rating = await self.calculate_rating()
        
        # Активные оповещения
        active_alerts = [a for a in self.alerts if a.status == 'active']
        
        # Распределение по типам угроз
        threat_counts = Counter(a.threat_type for a in active_alerts)
        
        # Статистика упоминаний за 7 дней
        week_ago = datetime.now() - timedelta(days=7)
        week_mentions = [m for m in self.mentions if m.published_at > week_ago]
        
        sentiment_distribution = {
            'positive': len([m for m in week_mentions if m.sentiment > 0.2]),
            'neutral': len([m for m in week_mentions if -0.2 <= m.sentiment <= 0.2]),
            'negative': len([m for m in week_mentions if m.sentiment < -0.2])
        }
        
        return {
            'timestamp': datetime.now().isoformat(),
            'city': self.city_name,
            'mayor': self.mayor_name,
            'current_rating': {
                'score': rating.overall_score,
                'trend': rating.trend,
                'trust': rating.trust_score,
                'approval': rating.approval_score
            },
            'alerts': {
                'total': len(active_alerts),
                'critical': len([a for a in active_alerts if a.risk_level == ReputationRisk.CRITICAL]),
                'high': len([a for a in active_alerts if a.risk_level == ReputationRisk.HIGH]),
                'by_type': {k.value: v for k, v in threat_counts.items()}
            },
            'mentions': {
                'total_7days': len(week_mentions),
                'sentiment': sentiment_distribution,
                'avg_sentiment': self.stats['avg_sentiment']
            },
            'critical_alerts': [
                {
                    'title': a.title,
                    'threat_type': a.threat_type.value,
                    'velocity': f"{a.velocity:.0f} упоминаний/час",
                    'action': a.recommended_action[:100]
                }
                for a in active_alerts if a.risk_level == ReputationRisk.CRITICAL
            ],
            'recommendations': self._get_reputation_recommendations(rating, active_alerts)
        }
    
    def _get_reputation_recommendations(self, rating: MayorRating, alerts: List[ReputationAlert]) -> List[str]:
        """Рекомендации по улучшению репутации"""
        recommendations = []
        
        if rating.trend == 'declining':
            recommendations.append("📉 Рейтинг снижается. Рекомендуется усилить публичную активность")
        
        if len([a for a in alerts if a.risk_level == ReputationRisk.CRITICAL]) > 0:
            recommendations.append("🚨 КРИТИЧЕСКИЕ УГРОЗЫ: Немедленно реализовать антикризисный план")
        
        if rating.trust_score < 0.4:
            recommendations.append("🤝 Низкий уровень доверия. Провести серию открытых встреч с жителями")
        
        if rating.approval_score < 0.4:
            recommendations.append("📢 Низкое одобрение. Опубликовать отчёт о достижениях")
        
        if not recommendations:
            recommendations.append("✅ Репутация в норме. Продолжать мониторинг")
        
        return recommendations


# ==================== ИНТЕГРАЦИЯ ====================

async def create_reputation_guard(city_name: str, mayor_name: str) -> ReputationGuard:
    """Фабричная функция"""
    return ReputationGuard(city_name, mayor_name)


# ==================== ПРИМЕР ====================

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("🧪 Тестирование ReputationGuard...")
        
        guard = ReputationGuard("Коломна", "Гречищев А.В.")
        
        # 1. Сбор упоминаний
        print("\n📊 СБОР УПОМИНАНИЙ:")
        test_data = [
            {'type': 'telegram', 'items': [
                {'id': '1', 'text': 'Мэр Коломны отлично работает! Парк чудесный', 'author': 'user1', 'date': datetime.now(), 'views': 1000},
                {'id': '2', 'text': 'Глава Коломны — бездарь, дороги разбиты', 'author': 'user2', 'date': datetime.now(), 'views': 5000},
                {'id': '3', 'text': 'Коррупция в администрации Коломны? Говорят, взяточничество', 'author': 'user3', 'date': datetime.now(), 'views': 10000}
            ]}
        ]
        
        mentions = await guard.collect_mentions(test_data)
        print(f"  Собрано упоминаний: {len(mentions)}")
        
        # 2. Обнаружение угроз
        print("\n⚠️ ОБНАРУЖЕНИЕ УГРОЗ:")
        threats = await guard.detect_threats()
        for t in threats:
            print(f"  • {t.title} ({t.risk_level.value}) — {t.description}")
        
        # 3. Расчёт рейтинга
        print("\n📈 РЕЙТИНГ МЭРА:")
        rating = await guard.calculate_rating()
        print(f"  Общий рейтинг: {rating.overall_score:.0%} ({rating.trend})")
        print(f"  Доверие: {rating.trust_score:.0%}")
        print(f"  Одобрение: {rating.approval_score:.0%}")
        
        # 4. Антикризисная коммуникация
        if threats:
            print("\n📢 АНТИКРИЗИСНАЯ КОММУНИКАЦИЯ:")
            response = await guard.generate_crisis_response(threats[0].id)
            print(f"  Для угрозы: {threats[0].title}")
            if response.get('press_release'):
                print(f"  Пресс-релиз: {response['press_release']['title']}")
            if response.get('action_plan'):
                print(f"  План действий: {response['action_plan'][0]}")
        
        # 5. Дашборд
        print("\n📋 ДАШБОРД РЕПУТАЦИИ:")
        dashboard = await guard.get_reputation_dashboard()
        print(f"  Рейтинг: {dashboard['current_rating']['score']:.0%}")
        print(f"  Активных угроз: {dashboard['alerts']['total']}")
        print(f"  Критических: {dashboard['alerts']['critical']}")
        if dashboard['recommendations']:
            print(f"  Рекомендация: {dashboard['recommendations'][0]}")
        
        print("\n✅ Тест завершен")
    
    asyncio.run(demo())
