# metrics/trust_analyzer.py
"""
Анализ уровня доверия к городской администрации
На основе соцсетей, опросов, обращений граждан
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging
import aiohttp
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class TrustData:
    """Данные о доверии"""
    timestamp: datetime
    trust_index: float  # 0-1
    positive_mentions: int
    negative_mentions: int
    neutral_mentions: int
    top_complaints: List[str]
    top_praises: List[str]
    sentiment_trend: str  # 'rising', 'falling', 'stable'

class TrustAnalyzer:
    """Анализ уровня доверия"""
    
    def __init__(self, city_name: str, vk_token: str = None, tg_token: str = None):
        self.city_name = city_name
        self.vk_token = vk_token
        self.tg_token = tg_token
        self.trust_history = []
        self.current_trust = None
        
        # Ключевые слова для анализа
        self.positive_keywords = [
            'спасибо', 'молодец', 'отлично', 'хорошо', 'нравится', 'доволен',
            'эффективно', 'быстро', 'качественно', 'замечательно', 'горжусь',
            'прогресс', 'развитие', 'улучшение', 'помогли', 'решили'
        ]
        
        self.negative_keywords = [
            'плохо', 'ужасно', 'безобразие', 'возмутительно', 'позор',
            'недоволен', 'беспредел', 'бездарно', 'некомпетентно', 'коррупция',
            'воруют', 'обманывают', 'игнорируют', 'не слышат', 'бездействие'
        ]
        
        self.complaint_patterns = {
            'ЖКХ': ['жкх', 'коммуналка', 'отопление', 'вода', 'канализация'],
            'Дороги': ['дороги', 'ямы', 'ремонт дорог', 'тротуары'],
            'Транспорт': ['транспорт', 'автобус', 'маршрутка', 'пробки', 'остановки'],
            'Мусор': ['мусор', 'свалка', 'вывоз мусора', 'контейнеры'],
            'Власть': ['мэр', 'администрация', 'чиновники', 'депутаты'],
            'Благоустройство': ['парк', 'сквер', 'двор', 'площадка', 'освещение'],
            'Медицина': ['больница', 'поликлиника', 'врачи', 'лекарства'],
            'Образование': ['школа', 'детский сад', 'учителя', 'образование']
        }
    
    async def analyze_social_media(self, hours_back: int = 24) -> TrustData:
        """Анализ соцсетей (ВКонтакте, Telegram)"""
        
        # Сбор постов из VK
        vk_posts = await self._fetch_vk_posts(hours_back) if self.vk_token else []
        
        # Сбор постов из Telegram (нужно настроить парсинг каналов)
        tg_posts = await self._fetch_telegram_posts(hours_back) if self.tg_token else []
        
        all_posts = vk_posts + tg_posts
        
        # Анализ тональности
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        complaints = defaultdict(int)
        praises = defaultdict(int)
        
        for post in all_posts:
            sentiment, category = self._analyze_sentiment(post['text'])
            
            if sentiment > 0.2:
                positive_count += 1
                if category:
                    praises[category] += 1
            elif sentiment < -0.2:
                negative_count += 1
                if category:
                    complaints[category] += 1
            else:
                neutral_count += 1
        
        total = positive_count + negative_count + neutral_count
        if total == 0:
            trust_index = 0.5
        else:
            # Индекс доверия = (позитив - негатив) / общее + 0.5
            trust_index = 0.5 + (positive_count - negative_count) / (total * 2)
            trust_index = max(0, min(1, trust_index))
        
        # Топ жалоб и похвал
        top_complaints = sorted(complaints.items(), key=lambda x: x[1], reverse=True)[:5]
        top_praises = sorted(praises.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Тренд
        trend = self._calculate_trend(trust_index)
        
        trust_data = TrustData(
            timestamp=datetime.now(),
            trust_index=trust_index,
            positive_mentions=positive_count,
            negative_mentions=negative_count,
            neutral_mentions=neutral_count,
            top_complaints=[f"{cat}: {count}" for cat, count in top_complaints],
            top_praises=[f"{cat}: {count}" for cat, count in top_praises],
            sentiment_trend=trend
        )
        
        self.current_trust = trust_data
        self.trust_history.append(trust_data)
        
        # Оставляем историю за 30 дней
        if len(self.trust_history) > 30:
            self.trust_history = self.trust_history[-30:]
        
        return trust_data
    
    async def _fetch_vk_posts(self, hours_back: int) -> List[Dict]:
        """Сбор постов из VK"""
        # Здесь интеграция с VK API
        # Для демо возвращаем тестовые данные
        return self._generate_mock_posts('vk')
    
    async def _fetch_telegram_posts(self, hours_back: int) -> List[Dict]:
        """Сбор постов из Telegram"""
        # Интеграция с Telegram API через telethon
        return self._generate_mock_posts('tg')
    
    def _generate_mock_posts(self, source: str) -> List[Dict]:
        """Генерация тестовых постов"""
        mock_texts = [
            ("Спасибо администрации за новый парк! Очень красиво!", 0.8, 'Благоустройство'),
            ("Дороги в ужасном состоянии, ямы не ремонтируют", -0.7, 'Дороги'),
            ("Когда уже уберут мусор во дворе?", -0.5, 'Мусор'),
            ("Отличная работа! Детскую площадку сделали", 0.7, 'Благоустройство'),
            ("Тарифы ЖКХ опять подняли, издевательство", -0.6, 'ЖКХ'),
            ("Мэр молодец, видно, что старается", 0.6, 'Власть'),
            ("Автобусы ходят по расписанию, удобно", 0.5, 'Транспорт'),
            ("Коррупция на каждом шагу", -0.8, 'Власть'),
            ("Врачи в поликлинике замечательные", 0.6, 'Медицина'),
            ("В школе хорошие учителя", 0.5, 'Образование')
        ]
        
        posts = []
        for text, sentiment, category in mock_texts:
            posts.append({
                'source': source,
                'text': text,
                'sentiment': sentiment,
                'category': category
            })
        return posts
    
    def _analyze_sentiment(self, text: str) -> tuple:
        """Анализ тональности текста"""
        text_lower = text.lower()
        
        # Считаем позитивные и негативные слова
        pos_count = sum(1 for word in self.positive_keywords if word in text_lower)
        neg_count = sum(1 for word in self.negative_keywords if word in text_lower)
        
        total = pos_count + neg_count
        if total == 0:
            sentiment = 0
        else:
            sentiment = (pos_count - neg_count) / total
        
        # Определяем категорию
        category = None
        for cat, keywords in self.complaint_patterns.items():
            if any(kw in text_lower for kw in keywords):
                category = cat
                break
        
        return sentiment, category
    
    def _calculate_trend(self, current_index: float) -> str:
        """Расчёт тренда доверия"""
        if len(self.trust_history) < 2:
            return 'stable'
        
        prev_index = self.trust_history[-1].trust_index
        change = current_index - prev_index
        
        if change > 0.05:
            return 'rising'
        elif change < -0.05:
            return 'falling'
        else:
            return 'stable'
    
    async def analyze_appeals(self, appeals_data: List[Dict]) -> Dict:
        """Анализ обращений граждан"""
        total = len(appeals_data)
        resolved = sum(1 for a in appeals_data if a.get('resolved', False))
        resolved_percent = resolved / total if total > 0 else 0
        
        avg_response_time = 0
        if appeals_data:
            times = [a.get('response_time', 0) for a in appeals_data]
            avg_response_time = sum(times) / len(times)
        
        return {
            'total_appeals': total,
            'resolved_percent': resolved_percent,
            'avg_response_time_days': avg_response_time,
            'satisfaction_rate': self._estimate_satisfaction(resolved_percent, avg_response_time)
        }
    
    def _estimate_satisfaction(self, resolved_percent: float, response_time: float) -> float:
        """Оценка удовлетворённости ответом"""
        # Чем выше процент решённых и быстрее ответ, тем выше удовлетворённость
        resolved_score = resolved_percent
        time_score = max(0, 1 - response_time / 30)  # 30 дней - критично
        return (resolved_score * 0.7 + time_score * 0.3)
