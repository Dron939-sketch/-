# confinement_model.py
# Полная конфайнт-модель для анализа городских систем через новостной контекст
# Адаптировано из психологической модели Мейстера

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import logging
import json
from enum import Enum

# Настройка логирования
logger = logging.getLogger(__name__)

# ==================== КОНСТАНТЫ МОДЕЛИ ====================

# Векторы для городского контекста
VECTORS = {
    'СБ': {
        'name': 'Безопасность и стабильность',
        'emoji': '🛡️',
        'description': 'Физическая и психологическая безопасность горожан',
        'levels': {
            1: {'desc': 'Кризис безопасности', 'city_state': 'Хаос, паника, высокая угроза'},
            2: {'desc': 'Высокая тревожность', 'city_state': 'Постоянное напряжение, инциденты'},
            3: {'desc': 'Ситуативная стабильность', 'city_state': 'Спокойно, но непредсказуемо'},
            4: {'desc': 'Уверенность', 'city_state': 'Предсказуемо, низкий уровень угроз'},
            5: {'desc': 'Высокая защищенность', 'city_state': 'Комфорт, доверие к системам'},
            6: {'desc': 'Абсолютная гармония', 'city_state': 'Идеальная среда, процветание'}
        }
    },
    'ТФ': {
        'name': 'Экономика и инфраструктура',
        'emoji': '🏗️',
        'description': 'Материальная база и развитие города',
        'levels': {
            1: {'desc': 'Деградация', 'city_state': 'Коллапс экономики, разруха'},
            2: {'desc': 'Выживание', 'city_state': 'Острая нехватка ресурсов'},
            3: {'desc': 'Стагнация', 'city_state': 'Хватает на базовые нужды'},
            4: {'desc': 'Развитие', 'city_state': 'Рост, новые проекты'},
            5: {'desc': 'Процветание', 'city_state': 'Избыток ресурсов, качественный рост'},
            6: {'desc': 'Изобилие', 'city_state': 'Технологический рай, безлимит'}
        }
    },
    'УБ': {
        'name': 'Качество жизни и благополучие',
        'emoji': '😊',
        'description': 'Удовлетворенность жизнью в городе',
        'levels': {
            1: {'desc': 'Страдание', 'city_state': 'Жизнь невыносима, массовый отток'},
            2: {'desc': 'Апатия', 'city_state': 'Нет радости, серость'},
            3: {'desc': 'Терпимость', 'city_state': 'Нормально, но хочется лучше'},
            4: {'desc': 'Удовлетворенность', 'city_state': 'Жить комфортно'},
            5: {'desc': 'Счастье', 'city_state': 'Город любви и радости'},
            6: {'desc': 'Эйфория', 'city_state': 'Город-утопия, исполнение желаний'}
        }
    },
    'ЧВ': {
        'name': 'Социальный капитал и идентичность',
        'emoji': '🤝',
        'description': 'Связи между людьми, общая культура',
        'levels': {
            1: {'desc': 'Изоляция', 'city_state': 'Все против всех, атомизация'},
            2: {'desc': 'Отчуждение', 'city_state': 'Не доверяют друг другу'},
            3: {'desc': 'Нейтралитет', 'city_state': 'Формальные отношения'},
            4: {'desc': 'Взаимодействие', 'city_state': 'Появляются связи, сообщества'},
            5: {'desc': 'Единство', 'city_state': 'Мы - одна команда'},
            6: {'desc': 'Сверхсознание', 'city_state': 'Город-организм, коллективный разум'}
        }
    }
}

# Профили уровней для городского контекста
LEVEL_PROFILES = {
    'СБ': {
        1: {
            'archetype': 'Город в осаде',
            'quote': 'Здесь опасно жить, нужно уезжать',
            'triggers': ['новости о преступлениях', 'чп', 'аварии'],
            'city_response': 'Режим ЧС, комендантский час'
        },
        2: {
            'archetype': 'Тревожный город',
            'quote': 'Надо быть начеку, но живем',
            'triggers': ['слухи', 'нестабильность', 'происшествия'],
            'city_response': 'Усиленное патрулирование, тревожные кнопки'
        },
        3: {
            'archetype': 'Спокойный город',
            'quote': 'В целом нормально, но бывает',
            'triggers': ['резонансные случаи', 'смена власти'],
            'city_response': 'Стандартная работа полиции'
        },
        4: {
            'archetype': 'Уверенный город',
            'quote': 'Мы под защитой',
            'triggers': ['позитивные изменения', 'инвестиции в безопасность'],
            'city_response': 'Профилактика, современное оборудование'
        },
        5: {
            'archetype': 'Город-крепость',
            'quote': 'Здесь безопасно как нигде',
            'triggers': ['международные рейтинги', 'туристический бум'],
            'city_response': 'Инновационные системы безопасности'
        },
        6: {
            'archetype': 'Город-утопия',
            'quote': 'Райский уголок',
            'triggers': ['абсолютное спокойствие', 'отсутствие проблем'],
            'city_response': 'Саморегулируемые сообщества'
        }
    },
    'ТФ': {
        1: {
            'archetype': 'Город-призрак',
            'quote': 'Экономика мертва, спасайся кто может',
            'triggers': ['закрытие заводов', 'дефолт', 'гиперинфляция'],
            'city_response': 'Экономический коллапс'
        },
        2: {
            'archetype': 'Депрессивный город',
            'quote': 'Еле сводим концы с концами',
            'triggers': ['рост цен', 'безработица', 'долги'],
            'city_response': 'Социальные выплаты, поддержка'
        },
        3: {
            'archetype': 'Стабильный город',
            'quote': 'Хватает на жизнь, но без излишеств',
            'triggers': ['бюджетные колебания', 'сезонность'],
            'city_response': 'Плановое финансирование'
        },
        4: {
            'archetype': 'Растущий город',
            'quote': 'Есть развитие и перспективы',
            'triggers': ['инвестиции', 'стройки', 'новые рабочие места'],
            'city_response': 'Развитие инфраструктуры'
        },
        5: {
            'archetype': 'Город-лидер',
            'quote': 'У нас лучшая экономика в регионе',
            'triggers': ['рекорды', 'достижения', 'прибыль'],
            'city_response': 'Инновационный центр'
        },
        6: {
            'archetype': 'Город-сказка',
            'quote': 'Денег столько, что не знаем куда девать',
            'triggers': ['экономическое чудо', 'нефтедоллары'],
            'city_response': 'Технологический рай'
        }
    },
    'УБ': {
        1: {
            'archetype': 'Город-ад',
            'quote': 'Здесь невозможно жить',
            'triggers': ['экокатастрофа', 'отсутствие услуг', 'грязь'],
            'city_response': 'Эвакуация, переселение'
        },
        2: {
            'archetype': 'Серый город',
            'quote': 'Все серо и уныло',
            'triggers': ['отсутствие досуга', 'плохая экология'],
            'city_response': 'Благоустройство по минимуму'
        },
        3: {
            'archetype': 'Обычный город',
            'quote': 'Как у всех, терпимо',
            'triggers': ['сезонные проблемы', 'отдельные жалобы'],
            'city_response': 'Точечное благоустройство'
        },
        4: {
            'archetype': 'Комфортный город',
            'quote': 'Жить приятно и удобно',
            'triggers': ['новые парки', 'спортобъекты', 'культура'],
            'city_response': 'Программы благоустройства'
        },
        5: {
            'archetype': 'Город-курорт',
            'quote': 'Лучшее место для жизни',
            'triggers': ['международные премии', 'туристический поток'],
            'city_response': 'Высокий уровень сервиса'
        },
        6: {
            'archetype': 'Город-мечта',
            'quote': 'Идеальный баланс во всем',
            'triggers': ['совершенство', 'гармония'],
            'city_response': 'Персонализированная среда'
        }
    },
    'ЧВ': {
        1: {
            'archetype': 'Город-муравейник',
            'quote': 'Каждый сам за себя',
            'triggers': ['конфликты', 'недоверие', 'агрессия'],
            'city_response': 'Разобщенность, низкая активность'
        },
        2: {
            'archetype': 'Чужой город',
            'quote': 'Здесь нет места своим',
            'triggers': ['миграция', 'разные культуры', 'непонимание'],
            'city_response': 'Закрытые сообщества'
        },
        3: {
            'archetype': 'Формальный город',
            'quote': 'Соседей не знаем, но не мешаем',
            'triggers': ['нейтральные новости', 'отсутствие событий'],
            'city_response': 'ТОСы, формальные объединения'
        },
        4: {
            'archetype': 'Дружный город',
            'quote': 'Вместе мы сила',
            'triggers': ['субботники', 'фестивали', 'активность'],
            'city_response': 'НКО, волонтерство'
        },
        5: {
            'archetype': 'Город-семья',
            'quote': 'Все друг друга знают и поддерживают',
            'triggers': ['общие победы', 'преодоление кризисов'],
            'city_response': 'Крепкие сообщества'
        },
        6: {
            'archetype': 'Город-организм',
            'quote': 'Мы единое целое',
            'triggers': ['коллективное сознание', 'синергия'],
            'city_response': 'Самоуправление, прямая демократия'
        }
    }
}

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def level(score: float) -> int:
    """Преобразует балл в уровень (1-6)"""
    if score <= 1.5:
        return 1
    elif score <= 2.5:
        return 2
    elif score <= 3.5:
        return 3
    elif score <= 4.5:
        return 4
    elif score <= 5.5:
        return 5
    else:
        return 6


def get_vector_description(vector_code: str, level_value: int) -> str:
    """Возвращает описание вектора на заданном уровне"""
    vector = VECTORS.get(vector_code, {})
    level_info = vector.get('levels', {}).get(level_value, {})
    return level_info.get('desc', 'Не определено')


def get_city_state(vector_code: str, level_value: int) -> str:
    """Возвращает состояние города по вектору"""
    vector = VECTORS.get(vector_code, {})
    level_info = vector.get('levels', {}).get(level_value, {})
    return level_info.get('city_state', 'Состояние не определено')


# ==================== ОСНОВНЫЕ КЛАССЫ МОДЕЛИ ====================

class ConfinementElement:
    """
    Элемент конфайнмент-модели (один из 9 кружочков)
    Адаптирован для городского контекста
    """
    
    def __init__(self, element_id: int, name: str = None):
        self.id = element_id  # 1..9
        self.name = name or f"Элемент {element_id}"
        self.description = ""
        self.element_type = None  # 'result', 'cause', 'common', 'closing', 'city_context'
        self.vector = None  # СБ, ТФ, УБ, ЧВ (если привязан)
        self.level = None  # 1..6 (если привязан)
        self.archetype = None  # из LEVEL_PROFILES
        self.strength = 0.5  # сила влияния 0-1
        self.vak = 'digital'  # ведущий ВАК-канал
        
        # Городские метаданные
        self.city_metrics = {}  # конкретные метрики города
        self.news_references = []  # ссылки на новости
        self.keywords = []  # ключевые слова
        
        # Связи
        self.causes = []  # какие элементы вызывает
        self.caused_by = []  # какими элементами вызывается
        self.amplifies = []  # какие элементы усиливает
        
    def to_dict(self) -> dict:
        """Для сохранения в user_data"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'type': self.element_type,
            'vector': self.vector,
            'level': self.level,
            'archetype': self.archetype,
            'strength': self.strength,
            'vak': self.vak,
            'city_metrics': self.city_metrics.copy(),
            'news_references': self.news_references.copy(),
            'keywords': self.keywords.copy(),
            'causes': self.causes.copy(),
            'caused_by': self.caused_by.copy(),
            'amplifies': self.amplifies.copy()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ConfinementElement':
        """Восстановление из словаря"""
        element = cls(data['id'], data.get('name'))
        element.description = data.get('description', '')
        element.element_type = data.get('type')
        element.vector = data.get('vector')
        element.level = data.get('level')
        element.archetype = data.get('archetype')
        element.strength = data.get('strength', 0.5)
        element.vak = data.get('vak', 'digital')
        element.city_metrics = data.get('city_metrics', {})
        element.news_references = data.get('news_references', [])
        element.keywords = data.get('keywords', [])
        element.causes = data.get('causes', [])
        element.caused_by = data.get('caused_by', [])
        element.amplifies = data.get('amplifies', [])
        return element
    
    def add_news_reference(self, news_title: str, news_source: str, relevance: float = 0.5):
        """Добавляет ссылку на новость, подтверждающую этот элемент"""
        self.news_references.append({
            'title': news_title,
            'source': news_source,
            'relevance': relevance,
            'added_at': datetime.now().isoformat()
        })
    
    def __repr__(self) -> str:
        return f"<ConfinementElement {self.id}: {self.name} (level={self.level})>"


class ConfinementModel9:
    """
    Полная 9-элементная конфайнмент-модель по Мейстеру
    Адаптирована для анализа городских систем
    """
    
    # Константы для типов элементов
    TYPE_RESULT = 'result'  # элемент 1 - главная проблема города
    TYPE_IMMEDIATE_CAUSE = 'immediate_cause'  # элементы 2,3,4 - непосредственные причины
    TYPE_COMMON_CAUSE = 'common_cause'  # элемент 5 - общая причина/убеждения
    TYPE_UPPER_CAUSE = 'upper_cause'  # элементы 6,7,8 - причины верхнего уровня
    TYPE_CLOSING = 'closing'  # элемент 9 - замыкающий элемент
    
    def __init__(self, city_id: Union[int, str] = None, city_name: str = None):
        self.city_id = city_id
        self.city_name = city_name or f"Город_{city_id}"
        self.elements: Dict[int, Optional[ConfinementElement]] = {i: None for i in range(1, 10)}
        self.links = []  # все связи
        self.loops = []  # найденные петли
        self.key_confinement = None  # главное ограничение
        self.is_closed = False  # замкнута ли система
        self.closure_score = 0.0  # степень замыкания
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
        # Метаданные для построения
        self.source_scores = {}  # исходные баллы по векторам
        self.source_history = []  # исходная история (новости)
        self.news_articles = []  # новостные статьи
        
        # Городские метаданные
        self.population = None
        self.region = None
        self.city_type = None  # 'мегаполис', 'средний', 'малый'
    
    def build_from_city_data(self, city_metrics: Dict[str, float], 
                            news_articles: List[Dict] = None,
                            city_metadata: Dict = None) -> 'ConfinementModel9':
        """
        Строит модель на основе метрик города и новостей
        Это главный метод для городского контекста
        """
        logger.info(f"Building confinement model for city {self.city_name}")
        
        # Сохраняем исходные данные
        self.source_scores = city_metrics
        self.news_articles = news_articles or []
        
        # Сохраняем метаданные города
        if city_metadata:
            self.population = city_metadata.get('population')
            self.region = city_metadata.get('region')
            self.city_type = city_metadata.get('city_type')
        
        # Преобразуем новости в историю
        self.source_history = self._news_to_history(news_articles)
        
        try:
            # Шаг 1: Определяем главную проблему города (элемент 1)
            self.elements[1] = self._extract_main_city_problem()
            
            # Шаг 2: Три непосредственные причины (элементы 2,3,4) - из векторов
            self.elements[2] = self._element_from_vector('СБ', city_metrics.get('СБ', 3.0))
            self.elements[3] = self._element_from_vector('ТФ', city_metrics.get('ТФ', 3.0))
            self.elements[4] = self._element_from_vector('УБ', city_metrics.get('УБ', 3.0))
            
            # Шаг 3: Проверяем цепочку усиления 2→3→4
            self._ensure_causal_chain([2, 3, 4])
            
            # Шаг 4: Общая причина (элемент 5) - городские убеждения и нарративы
            self.elements[5] = self._find_common_cause([2, 3, 4])
            
            # Шаг 5: Причины верхнего уровня (элементы 6,7,8)
            self.elements[6] = self._find_cause_for([2, 5])  # локальная среда
            self.elements[7] = self._find_cause_for([6, 2])  # городские институты
            self.elements[8] = self._find_linked_to(7, causing=[6, 5])  # региональный контекст
            
            # Шаг 6: Замыкающий элемент (элемент 9) - городской миф
            self.elements[9] = self._find_closing_element()
            
            # Шаг 7: Проверяем и валидируем связи
            self._validate_links()
            
            # Шаг 8: Ищем петли обратной связи
            self._find_loops()
            
            # Шаг 9: Определяем ключевой конфайнмент
            self._identify_key_confinement()
            
            # Шаг 10: Оцениваем замыкание системы
            self._calculate_closure()
            
            # Шаг 11: Добавляем новостные ссылки к элементам
            self._enrich_with_news()
            
            self.updated_at = datetime.now()
            logger.info(f"Model built successfully for {self.city_name}")
            
        except Exception as e:
            logger.error(f"Error building model for {self.city_name}: {e}", exc_info=True)
            # Создаем минимальную модель, если что-то пошло не так
            self._build_fallback_model()
        
        return self
    
    def _news_to_history(self, news_articles: List[Dict]) -> List[Dict]:
        """Преобразует новости в формат истории для анализа"""
        history = []
        
        if not news_articles:
            return history
        
        for article in news_articles[:50]:  # ограничиваем 50 новостями
            history.append({
                'role': 'system',
                'text': f"[{article.get('source', 'news')}] {article.get('title', '')}: {article.get('content', '')[:300]}",
                'timestamp': article.get('published_at', datetime.now()),
                'sentiment': article.get('sentiment_score', 0)
            })
        
        return history
    
    def _build_fallback_model(self):
        """Создает запасную модель при ошибке"""
        logger.warning(f"Building fallback model for {self.city_name}")
        
        for i in range(1, 10):
            if not self.elements[i]:
                self.elements[i] = ConfinementElement(i, f"Компонент {i}")
                self.elements[i].description = "Требуется дополнительный анализ городских данных"
                self.elements[i].strength = 0.5
        
        self._validate_links()
        self.is_closed = False
        self.closure_score = 0.3
    
    def _extract_main_city_problem(self) -> ConfinementElement:
        """
        Извлекает главную проблему города из метрик и новостей
        Элемент 1 - результат системы (главный симптом)
        """
        if not self.source_scores:
            element = ConfinementElement(1, "Главная проблема города")
            element.description = "Требуется анализ городских метрик"
            element.element_type = self.TYPE_RESULT
            element.strength = 1.0
            return element
        
        # Определяем самый критичный вектор (с наименьшим уровнем)
        min_vector = min(self.source_scores.items(), 
                        key=lambda x: level(x[1]))
        vector, score = min_vector
        vector_info = VECTORS.get(vector, {})
        vector_name = vector_info.get('name', vector)
        vector_emoji = vector_info.get('emoji', '🔍')
        lvl = level(score)
        
        # Получаем профиль уровня
        profile = LEVEL_PROFILES.get(vector, {}).get(lvl, {})
        city_state = get_city_state(vector, lvl)
        
        # Анализируем новости для подтверждения
        problem_keywords = self._extract_problem_keywords_from_news()
        
        # Формируем описание проблемы
        description_parts = [
            f"{vector_emoji} **{city_state}**",
            f"\n{profile.get('quote', 'Требуется анализ')}",
        ]
        
        if problem_keywords:
            description_parts.append(f"\n\n🔍 *Ключевые темы в новостях:* {', '.join(problem_keywords[:5])}")
        
        element = ConfinementElement(1, f"Ключевая проблема: {vector_name}")
        element.description = ' '.join(description_parts)
        element.element_type = self.TYPE_RESULT
        element.vector = vector
        element.level = lvl
        element.archetype = profile.get('archetype')
        element.strength = 1.0  # результат всегда сильный
        element.keywords = problem_keywords
        
        return element
    
    def _extract_problem_keywords_from_news(self) -> List[str]:
        """Извлекает ключевые слова проблем из новостей"""
        if not self.news_articles:
            return []
        
        problem_keywords = [
            'кризис', 'проблема', 'авария', 'долги', 'безработица',
            'преступность', 'коррупция', 'разруха', 'отток', 'бедность'
        ]
        
        found_keywords = []
        for article in self.news_articles[:20]:
            text = (article.get('title', '') + ' ' + article.get('content', '')).lower()
            for keyword in problem_keywords:
                if keyword in text and keyword not in found_keywords:
                    found_keywords.append(keyword)
        
        return found_keywords
    
    def _element_from_vector(self, vector: str, score: float) -> ConfinementElement:
        """
        Создает элемент на основе вектора (СБ, ТФ, УБ)
        Для элементов 2,3,4 - непосредственные причины проблем города
        """
        lvl = level(score)
        vector_info = VECTORS.get(vector, {})
        vector_name = vector_info.get('name', vector)
        vector_emoji = vector_info.get('emoji', '🔍')
        
        # Получаем профиль уровня
        profile = LEVEL_PROFILES.get(vector, {}).get(lvl, {})
        level_desc = get_vector_description(vector, lvl)
        city_state = get_city_state(vector, lvl)
        
        # Определяем тип элемента по позиции
        element_map = {
            'СБ': 2,
            'ТФ': 3,
            'УБ': 4,
        }
        element_id = element_map.get(vector, 4)
        
        element = ConfinementElement(element_id, f"{vector_emoji} {vector_name}")
        
        # Формируем описание
        description = f"**Уровень {lvl}: {level_desc}**\n\n{city_state}"
        
        if profile.get('quote'):
            description += f"\n\n💬 *Общественные настроения:*\n«{profile['quote']}»"
        
        if profile.get('triggers'):
            triggers = profile['triggers'][:3]
            description += f"\n\n⚠️ *Триггеры обострения:*\n" + "\n".join(f"• {t}" for t in triggers)
        
        element.description = description
        element.element_type = self.TYPE_IMMEDIATE_CAUSE
        element.vector = vector
        element.level = lvl
        element.archetype = profile.get('archetype')
        element.strength = lvl / 6.0  # сила пропорциональна уровню
        element.vak = self._vector_to_vak(vector, lvl)
        
        return element
    
    def _ensure_causal_chain(self, element_ids: List[int]):
        """
        Проверяет и обеспечивает цепочку усиления 2→3→4 (каждый усиливает следующий)
        В городском контексте: проблемы безопасности влияют на экономику,
        экономика на качество жизни и т.д.
        """
        chain_descriptions = {
            (2, 3): "Проблемы безопасности отпугивают инвесторов и бизнес → экономика страдает",
            (3, 4): "Экономические проблемы снижают качество жизни и благополучие горожан",
            (2, 4): "Постоянная тревога ухудшает психологическое состояние жителей"
        }
        
        for i in range(len(element_ids)-1):
            cause_id = element_ids[i]
            effect_id = element_ids[i+1]
            
            cause = self.elements.get(cause_id)
            effect = self.elements.get(effect_id)
            
            if not cause or not effect:
                continue
            
            # Добавляем связь усиления
            if effect_id not in cause.amplifies:
                cause.amplifies.append(effect_id)
            if cause_id not in effect.caused_by:
                effect.caused_by.append(cause_id)
            
            # Описание связи
            link_desc = chain_descriptions.get((cause_id, effect_id), 
                                              f"{cause.name} усиливает {effect.name}")
            
            self.links.append({
                'from': cause_id,
                'to': effect_id,
                'type': 'amplifies',
                'strength': cause.strength * effect.strength,
                'description': link_desc
            })
    
    def _find_common_cause(self, effect_ids: List[int]) -> ConfinementElement:
        """
        Находит общую причину для нескольких элементов (элемент 5)
        В городском контексте - это коллективные убеждения и городские нарративы
        """
        # Собираем векторы эффектов
        vectors = []
        for eid in effect_ids:
            elem = self.elements.get(eid)
            if elem and elem.vector:
                vectors.append(elem.vector)
        
        # Определяем общую причину на основе комбинации
        common_causes = {
            ('СБ', 'ТФ', 'УБ'): {
                'name': '🏛️ Городской нарратив',
                'description': '«В этом городе невозможно ничего изменить»',
                'archetype': 'Город-ловушка'
            },
            ('СБ', 'ТФ'): {
                'name': '💭 Экономическая безнадежность',
                'description': '«Безопасность и деньги не появятся, пока не поменяется власть»',
                'archetype': 'Город-заложник'
            },
            ('ТФ', 'УБ'): {
                'name': '😔 Депрессивный нарратив',
                'description': '«Жить хорошо не получится, пока не разбогатеем»',
                'archetype': 'Город-терпелец'
            }
        }
        
        cause_key = tuple(sorted(vectors))
        cause_info = common_causes.get(cause_key, {
            'name': '💭 Коллективные убеждения',
            'description': 'Общие представления жителей о причинах проблем города',
            'archetype': 'Городской миф'
        })
        
        # Извлекаем из новостей повторяющиеся темы
        common_themes = self._extract_common_themes_from_news()
        
        element = ConfinementElement(5, cause_info['name'])
        element.description = cause_info['description']
        
        if common_themes:
            element.description += f"\n\n📰 *Частые темы в новостях:*\n" + "\n".join(f"• {theme}" for theme in common_themes[:3])
        
        element.element_type = self.TYPE_COMMON_CAUSE
        element.archetype = cause_info['archetype']
        element.strength = 0.8
        element.vak = 'auditory_digital'
        
        return element
    
    def _extract_common_themes_from_news(self) -> List[str]:
        """Извлекает повторяющиеся темы из новостей"""
        if not self.news_articles:
            return []
        
        themes = []
        theme_keywords = {
            'Коррупция': ['коррупц', 'взятк', 'откат', 'схем'],
            'Бездействие власти': ['чиновник', 'мэрия', 'губернатор', 'власть', 'бездействие'],
            'Проблемы ЖКХ': ['жкх', 'коммуналк', 'отопление', 'вода', 'канализация'],
            'Долги': ['долг', 'кредит', 'задолженност'],
            'Отток населения': ['уезжают', 'покидают', 'миграция', 'отток']
        }
        
        for theme, keywords in theme_keywords.items():
            count = 0
            for article in self.news_articles[:30]:
                text = (article.get('title', '') + ' ' + article.get('content', '')).lower()
                if any(kw in text for kw in keywords):
                    count += 1
            
            if count > 5:  # если тема встречается в 5+ новостях
                themes.append(theme)
        
        return themes
    
    def _find_cause_for(self, effect_ids: List[int]) -> ConfinementElement:
        """
        Находит причину для списка эффектов (элементы 6,7)
        В городском контексте - уровень среды и институтов
        """
        element_id = 6 if 6 not in effect_ids else 7
        
        if element_id == 6:
            element = ConfinementElement(6, "🏘️ Локальная среда")
            element.description = "Состояние района, соседские отношения, локальный бизнес и инфраструктура"
            element.element_type = self.TYPE_UPPER_CAUSE
            element.archetype = "Городской район"
            element.strength = 0.6
            element.vak = 'kinesthetic'
        else:
            element = ConfinementElement(7, "🏛️ Городские институты")
            element.description = "Муниципальная власть, бюрократия, градостроительная политика, распределение бюджета"
            element.element_type = self.TYPE_UPPER_CAUSE
            element.archetype = "Система управления"
            element.strength = 0.7
            element.vak = 'auditory_digital'
        
        return element
    
    def _find_linked_to(self, source_id: int, causing: List[int]) -> ConfinementElement:
        """
        Находит элемент, связанный с source_id и вызывающий указанные элементы
        Элемент 8 - региональный/федеральный контекст
        """
        element = ConfinementElement(8, "🗺️ Региональный контекст")
        element.description = "Региональная политика, экономика области, культурные особенности, исторический контекст"
        element.element_type = self.TYPE_UPPER_CAUSE
        element.archetype = "Внешняя среда"
        element.strength = 0.75
        element.vak = 'visual'
        
        return element
    
    def _find_closing_element(self) -> ConfinementElement:
        """
        Находит замыкающий элемент (9) - городской миф/самосбывающееся пророчество
        Это самый важный элемент, который не дает системе меняться
        """
        # Анализируем самый слабый вектор
        if self.source_scores:
            weakest = min(self.source_scores.items(), 
                         key=lambda x: level(x[1]))
            vector, score = weakest
            lvl = level(score)
        else:
            vector, lvl = 'СБ', 3
        
        # Карта замыкающих элементов для города
        closing_map = {
            'СБ': {
                'name': '🌍 Миф о безнадежности',
                'description': '«Этот город опасен и никогда не изменится»',
                'archetype': 'Город-ловушка'
            },
            'ТФ': {
                'name': '💰 Миф о бедности',
                'description': '«В этом городе невозможно разбогатеть, здесь только выживают»',
                'archetype': 'Город-нищий'
            },
            'УБ': {
                'name': '😔 Миф о депрессивности',
                'description': '«Здесь никогда не будет хорошо жить, это не наш удел»',
                'archetype': 'Город-уныние'
            },
            'ЧВ': {
                'name': '🤝 Миф о разобщенности',
                'description': '«Каждый сам за себя, вместе мы ничего не решим»',
                'archetype': 'Город-одиночка'
            }
        }
        
        closing = closing_map.get(vector, closing_map['СБ'])
        
        element = ConfinementElement(9, closing['name'])
        element.description = closing['description']
        element.element_type = self.TYPE_CLOSING
        element.vector = vector
        element.level = lvl
        element.archetype = closing['archetype']
        element.strength = 1.0  # замыкание всегда сильно
        element.vak = 'visual'
        
        # Добавляем подтверждение из новостей
        confirming_news = self._find_confirming_news(closing['description'])
        if confirming_news:
            element.news_references = confirming_news[:2]
        
        return element
    
    def _find_confirming_news(self, myth_description: str) -> List[Dict]:
        """Находит новости, подтверждающие городской миф"""
        confirming = []
        
        # Ключевые слова из описания мифа
        keywords = myth_description.lower().split()
        keywords = [kw.strip('.,!?') for kw in keywords if len(kw) > 4]
        
        for article in self.news_articles[:20]:
            text = (article.get('title', '') + ' ' + article.get('content', '')).lower()
            if any(kw in text for kw in keywords[:3]):
                confirming.append({
                    'title': article.get('title', ''),
                    'source': article.get('source', ''),
                    'relevance': 0.7
                })
        
        return confirming
    
    def _validate_links(self):
        """Проверяет и добавляет все необходимые связи между элементами"""
        # Связи по Мейстеру для городской модели
        standard_links = [
            (1, 2), (1, 3), (1, 4),  # главная проблема ← непосредственные причины
            (2, 3), (3, 4),           # цепочка усиления проблем
            (5, 2), (5, 3), (5, 4),   # общий нарратив → все причины
            (6, 2), (6, 5),           # локальная среда → проблемы и нарратив
            (7, 6), (7, 2),           # институты → среду и безопасность
            (8, 7), (8, 6), (8, 5),   # регион → институты, среду, нарратив
            (9, 7), (9, 8),           # городской миф → институты и регион
            (4, 9), (1, 9)            # качество жизни и проблема → замыкание
        ]
        
        # Описания связей для городского контекста
        link_descriptions = {
            (1, 2): "Главная проблема усугубляет чувство незащищенности",
            (1, 3): "Проблемы города напрямую влияют на экономическую ситуацию",
            (1, 4): "Системный кризис ухудшает качество жизни горожан",
            (2, 3): "Небезопасная среда отпугивает бизнес и инвестиции",
            (3, 4): "Экономические трудности снижают доступность качественной жизни",
            (5, 2): "Пессимистичные нарративы усиливают чувство страха",
            (5, 3): "Убеждение в безнадежности мешает экономическому развитию",
            (5, 4): "Неверие в лучшее снижает качество жизни",
            (6, 2): "Плохое состояние района повышает криминогенность",
            (6, 5): "Локальные проблемы формируют пессимистичные нарративы",
            (7, 6): "Неэффективное управление приводит к деградации районов",
            (7, 2): "Слабая власть не может обеспечить безопасность",
            (8, 7): "Региональная политика определяет качество управления",
            (8, 6): "Областной контекст влияет на состояние районов",
            (8, 5): "Региональные нарративы формируют городские мифы",
            (9, 7): "Миф о безнадежности парализует институты",
            (9, 8): "Городские мифы влияют на региональное восприятие",
            (4, 9): "Низкое качество жизни укрепляет пессимистичные мифы",
            (1, 9): "Неразрешенные проблемы замыкают порочный круг"
        }
        
        for from_id, to_id in standard_links:
            if self.elements.get(from_id) and self.elements.get(to_id):
                from_elem = self.elements[from_id]
                to_elem = self.elements[to_id]
                
                if to_id not in from_elem.causes:
                    from_elem.causes.append(to_id)
                if from_id not in to_elem.caused_by:
                    to_elem.caused_by.append(from_id)
                
                # Проверяем, нет ли уже такой связи
                link_exists = any(
                    l['from'] == from_id and l['to'] == to_id 
                    for l in self.links
                )
                if not link_exists:
                    desc = link_descriptions.get((from_id, to_id), 
                                                f"{from_elem.name} → {to_elem.name}")
                    self.links.append({
                        'from': from_id,
                        'to': to_id,
                        'type': 'causes',
                        'strength': 0.7,
                        'description': desc
                    })
    
    def _find_loops(self):
        """Находит рекурсивные петли обратной связи в городской системе"""
        self.loops = []
        
        # Основные петли для города:
        
        # Петля 1: Проблема → Безопасность → Экономика → Проблема
        loop1 = self._find_cycle([1, 2, 3, 1])
        if loop1:
            self.loops.append({
                'elements': loop1,
                'type': 'vicious_cycle_safety_economy',
                'description': 'Проблемы безопасности → экономический спад → усугубление проблем',
                'strength': self._calculate_loop_strength(loop1),
                'breaking_points': ['Инвестиции в безопасность', 'Поддержка МСП', 'Рабочие места']
            })
        
        # Петля 2: Нарратив → Институты → Среда → Нарратив
        loop2 = self._find_cycle([5, 7, 6, 5])
        if loop2:
            self.loops.append({
                'elements': loop2,
                'type': 'belief_institution_environment',
                'description': 'Пессимистичный нарратив → слабые институты → деградация среды → укрепление нарратива',
                'strength': self._calculate_loop_strength(loop2),
                'breaking_points': ['Позитивные кейсы', 'Успешные практики', 'Медиа-кампании']
            })
        
        # Петля 3: Полный цикл через замыкание (самый опасный)
        loop3 = self._find_cycle([1, 2, 3, 4, 9, 1])
        if loop3:
            self.loops.append({
                'elements': loop3,
                'type': 'full_closure_cycle',
                'description': 'Полный порочный круг: проблемы → страх → экономический спад → низкое качество жизни → миф о безнадежности → замыкание системы',
                'strength': self._calculate_loop_strength(loop3),
                'breaking_points': ['Разрыв мифа о безнадежности', 'Быстрые победы', 'Внешнее вмешательство']
            })
        
        # Петля 4: Социальная изоляция
        loop4 = self._find_cycle([4, 9, 7, 4])
        if loop4:
            self.loops.append({
                'elements': loop4,
                'type': 'social_isolation',
                'description': 'Низкое качество жизни → миф о разобщенности → слабые институты → ухудшение качества жизни',
                'strength': self._calculate_loop_strength(loop4),
                'breaking_points': ['Создание общественных пространств', 'Поддержка НКО', 'Соседские центры']
            })
    
    def _find_cycle(self, potential_cycle: List[int]) -> Optional[List[int]]:
        """Проверяет, существует ли указанный цикл связей"""
        for i in range(len(potential_cycle)-1):
            from_id = potential_cycle[i]
            to_id = potential_cycle[i+1]
            
            # Проверяем, есть ли элемент
            if not self.elements.get(from_id) or not self.elements.get(to_id):
                return None
            
            # Проверяем, есть ли связь
            if to_id not in self.elements[from_id].causes:
                return None
        
        return potential_cycle
    
    def _calculate_loop_strength(self, cycle: List[int]) -> float:
        """Вычисляет силу петли обратной связи"""
        strength = 1.0
        for i in range(len(cycle)-1):
            from_id = cycle[i]
            to_id = cycle[i+1]
            
            # Ищем связь
            for link in self.links:
                if link['from'] == from_id and link['to'] == to_id:
                    strength *= link['strength']
                    break
        
        return min(strength, 1.0)  # не больше 1
    
    def _identify_key_confinement(self):
        """Определяет ключевой конфайнмент (главное ограничение города)"""
        candidates = []
        
        for elem_id, element in self.elements.items():
            if not element:
                continue
            
            # Влияние = сколько элементов вызывает
            influence = len(element.causes)
            
            # Зависимость = сколько элементов на него влияют
            dependency = len(element.caused_by)
            
            # Важность для города
            if elem_id == 9:  # замыкающий элемент всегда важен
                importance = 10.0
            elif elem_id == 5:  # общий нарратив
                importance = (influence + 1) * (dependency + 1) * element.strength * 1.5
            else:
                importance = (influence + 1) * (dependency + 1) * element.strength
            
            candidates.append({
                'id': elem_id,
                'element': element,
                'influence': influence,
                'dependency': dependency,
                'importance': importance
            })
        
        # Сортируем по важности
        candidates.sort(key=lambda x: x['importance'], reverse=True)
        
        if candidates:
            top = candidates[0]
            self.key_confinement = {
                'id': top['id'],
                'element': top['element'],
                'description': self._describe_city_confinement(top),
                'importance': top['importance'],
                'intervention_points': self._get_intervention_points(top['id'])
            }
    
    def _describe_city_confinement(self, candidate: Dict) -> str:
        """Описывает ключевой конфайнмент для города"""
        elem = candidate['element']
        
        descriptions = {
            1: f"**Главная проблема города** — {elem.description[:80]}... Держит всю систему в кризисе.",
            2: f"**Ключевой вызов в безопасности** — {elem.name}. Страх и тревога парализуют развитие.",
            3: f"**Экономическое ограничение** — {elem.name}. Денежный голод не позволяет решать проблемы.",
            4: f"**Критическое падение качества жизни** — {elem.name}. Люди теряют мотивацию что-то менять.",
            5: f"**Центральный городской нарратив** — {elem.description[:80]}... Он пронизывает все уровни системы.",
            6: f"**Деградация локальной среды** — {elem.name}. Районы становятся некомфортными.",
            7: f"**Ключевой институциональный провал** — {elem.name}. Система управления не справляется.",
            8: f"**Контекстная ловушка** — {elem.name}. Региональные проблемы давят на город.",
            9: f"**Замыкающий городской миф** — {elem.description[:80]}... Именно он не дает системе вырваться из кризиса."
        }
        
        return descriptions.get(elem.id, "Ключевое ограничение требует анализа")
    
    def _get_intervention_points(self, element_id: int) -> List[str]:
        """Возвращает точки вмешательства для разрыва порочного круга"""
        intervention_map = {
            1: [
                "Фокус на решении самой острой проблемы",
                "Быстрые победы для создания импульса",
                "Вовлечение граждан в решение"
            ],
            2: [
                "Усиление patrol и быстрого реагирования",
                "Системы видеонаблюдения и освещение",
                "Программы neighborhood watch"
            ],
            3: [
                "Привлечение инвестиций в приоритетные сектора",
                "Поддержка малого и среднего бизнеса",
                "Создание рабочих мест"
            ],
            4: [
                "Благоустройство общественных пространств",
                "Развитие социальной инфраструктуры",
                "Экологические программы"
            ],
            5: [
                "Медиа-кампании с позитивными кейсами",
                "Видимые изменения от действий власти",
                "Вовлечение лидеров мнений"
            ],
            6: [
                "Программы развития дворовых территорий",
                "Поддержка ТОС и соседских сообществ",
                "Благоустройство по запросу жителей"
            ],
            7: [
                "Повышение прозрачности управления",
                "Внедрение механизмов обратной связи",
                "Бюджетирование с участием граждан"
            ],
            8: [
                "Лоббирование интересов города в регионе",
                "Межмуниципальное сотрудничество",
                "Использование региональных программ"
            ],
            9: [
                "Разрушение ключевого мифа через факты",
                "Демонстрация успешных примеров изменений",
                "Формирование новой городской идентичности"
            ]
        }
        
        return intervention_map.get(element_id, ["Комплексный анализ ситуации"])
    
    def _calculate_closure(self):
        """Оценивает степень замыкания системы (насколько город зациклен)"""
        # Проверяем наличие петли через элемент 9
        has_closing_loop = False
        for loop in self.loops:
            if 9 in loop['elements']:
                has_closing_loop = True
                self.closure_score = loop['strength']
                break
        
        if has_closing_loop:
            self.is_closed = self.closure_score > 0.5
        else:
            self.is_closed = False
            self.closure_score = 0.0
    
    def _enrich_with_news(self):
        """Обогащает элементы ссылками на новости"""
        if not self.news_articles:
            return
        
        for element in self.elements.values():
            if not element or not element.keywords:
                continue
            
            # Ищем новости, релевантные этому элементу
            for article in self.news_articles[:10]:
                text = (article.get('title', '') + ' ' + article.get('content', '')).lower()
                if any(kw in text for kw in element.keywords[:3]):
                    element.add_news_reference(
                        article.get('title', ''),
                        article.get('source', ''),
                        relevance=0.6
                    )
    
    def _vector_to_vak(self, vector: str, level: int) -> str:
        """Определяет ведущий ВАК-канал для вектора"""
        mapping = {
            'СБ': 'kinesthetic',  # безопасность - телесное ощущение
            'ТФ': 'digital',      # экономика - цифры и концепции
            'УБ': 'visual',       # качество жизни - визуальное восприятие
            'ЧВ': 'auditory'      # соцсвязи - слуховое (разговоры, новости)
        }
        
        # Корректировка по уровню
        if level <= 2:
            return mapping.get(vector, 'kinesthetic')
        elif level <= 4:
            return 'auditory_digital'
        else:
            return 'visual'
    
    def get_city_diagnosis(self) -> Dict:
        """
        Возвращает комплексный диагноз города
        """
        diagnosis = {
            'city_name': self.city_name,
            'city_id': self.city_id,
            'analysis_date': datetime.now().isoformat(),
            'vectors': {},
            'key_problem': None,
            'critical_loops': [],
            'closure_score': self.closure_score,
            'is_closed_system': self.is_closed,
            'recommendations': []
        }
        
        # Добавляем информацию по векторам
        for vector_code, score in self.source_scores.items():
            if vector_code in VECTORS:
                lvl = level(score)
                vector_info = VECTORS[vector_code]
                diagnosis['vectors'][vector_code] = {
                    'name': vector_info['name'],
                    'emoji': vector_info['emoji'],
                    'score': score,
                    'level': lvl,
                    'level_description': get_vector_description(vector_code, lvl),
                    'city_state': get_city_state(vector_code, lvl),
                    'archetype': LEVEL_PROFILES.get(vector_code, {}).get(lvl, {}).get('archetype')
                }
        
        # Добавляем ключевую проблему
        if self.elements[1]:
            diagnosis['key_problem'] = {
                'name': self.elements[1].name,
                'description': self.elements[1].description,
                'level': self.elements[1].level,
                'archetype': self.elements[1].archetype
            }
        
        # Добавляем критические петли
        for loop in self.loops:
            if loop['strength'] > 0.6:  # только сильные петли
                diagnosis['critical_loops'].append({
                    'type': loop['type'],
                    'description': loop['description'],
                    'strength': loop['strength'],
                    'breaking_points': loop.get('breaking_points', [])
                })
        
        # Добавляем рекомендации на основе ключевого конфайнмента
        if self.key_confinement:
            diagnosis['recommendations'] = self.key_confinement.get('intervention_points', [])
        
        # Общие рекомендации по системе
        if self.is_closed and self.closure_score > 0.7:
            diagnosis['recommendations'].append("⚠️ Город в глубокой системной ловушке - требуется комплексное вмешательство")
            diagnosis['recommendations'].append("🎯 Приоритет - разрыв замыкающего мифа через быстрые видимые изменения")
        
        return diagnosis
    
    def to_dict(self) -> Dict:
        """Сериализация для сохранения"""
        return {
            'city_id': self.city_id,
            'city_name': self.city_name,
            'elements': {k: v.to_dict() if v else None for k, v in self.elements.items()},
            'links': self.links.copy(),
            'loops': self.loops.copy(),
            'key_confinement': self.key_confinement,
            'is_closed': self.is_closed,
            'closure_score': self.closure_score,
            'source_scores': self.source_scores.copy(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'population': self.population,
            'region': self.region,
            'city_type': self.city_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConfinementModel9':
        """Десериализация"""
        model = cls(data.get('city_id'), data.get('city_name'))
        
        # Восстанавливаем элементы
        elements_data = data.get('elements', {})
        for k, v in elements_data.items():
            if v:
                model.elements[int(k)] = ConfinementElement.from_dict(v)
        
        model.links = data.get('links', [])
        model.loops = data.get('loops', [])
        model.key_confinement = data.get('key_confinement')
        model.is_closed = data.get('is_closed', False)
        model.closure_score = data.get('closure_score', 0.0)
        model.source_scores = data.get('source_scores', {})
        
        # Восстанавливаем метаданные
        model.population = data.get('population')
        model.region = data.get('region')
        model.city_type = data.get('city_type')
        
        # Восстанавливаем даты
        try:
            model.created_at = datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
            model.updated_at = datetime.fromisoformat(data.get('updated_at', datetime.now().isoformat()))
        except Exception:
            model.created_at = datetime.now()
            model.updated_at = datetime.now()
        
        return model


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ИНТЕГРАЦИИ ====================

def create_model_from_city_metrics(city_name: str, 
                                   safety_score: float,
                                   economy_score: float,
                                   wellbeing_score: float,
                                   social_score: float,
                                   news_articles: List[Dict] = None) -> ConfinementModel9:
    """
    Упрощенный конструктор модели из метрик города
    """
    model = ConfinementModel9(city_name=city_name)
    
    city_metrics = {
        'СБ': safety_score,
        'ТФ': economy_score,
        'УБ': wellbeing_score,
        'ЧВ': social_score
    }
    
    model.build_from_city_data(city_metrics, news_articles)
    return model


def analyze_city_from_scores(city_name: str, scores: Dict[str, float]) -> Dict:
    """
    Быстрый анализ города на основе только оценок (без новостей)
    """
    model = ConfinementModel9(city_name=city_name)
    model.build_from_city_data(scores, [])
    return model.get_city_diagnosis()
