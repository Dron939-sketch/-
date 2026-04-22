#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 7: АНАЛИЗ ВОПРОСОВ В КОНТЕКСТЕ ГОРОДСКОЙ КОНФАЙНМЕНТ-МОДЕЛИ
Анализирует вопросы о городе с учетом его системных паттернов и порочных кругов
Адаптировано для городского планирования и анализа запросов жителей/власти
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

from confinement_model import ConfinementModel9, VECTORS
from loop_analyzer import CityLoopAnalyzer

logger = logging.getLogger(__name__)


class CityQuestionContextAnalyzer:
    """
    Анализирует вопросы о городе в контексте его конфайнтмент-модели
    Не даёт советов и инструкций - только глубинный анализ городских проблем
    """
    
    # Ключевые слова для разных векторов (городской контекст)
    VECTOR_KEYWORDS = {
        'СБ': [  # Безопасность
            'безопасн', 'страх', 'боязнь', 'преступн', 'криминал', 'ограблен',
            'нападен', 'авария', 'дтп', 'пожар', 'чс', 'патруль', 'полиц',
            'освещен', 'темн', 'камер', 'опасн', 'угроз', 'насили', 'вандал'
        ],
        'ТФ': [  # Экономика
            'деньг', 'бюджет', 'зарплат', 'доход', 'работ', 'безработ',
            'бизнес', 'предприн', 'инвестиц', 'налог', 'долг', 'кредит',
            'цены', 'дорого', 'дешево', 'экономик', 'кризис', 'инфляц'
        ],
        'УБ': [  # Качество жизни
            'жизнь', 'комфорт', 'удобн', 'благоустр', 'парк', 'сквер',
            'двор', 'подъезд', 'мусор', 'чистот', 'гряз', 'экологи',
            'шум', 'тишин', 'транспорт', 'дорог', 'пробк', 'остановк'
        ],
        'ЧВ': [  # Социальный капитал
            'сосед', 'общен', 'встреч', 'мероприят', 'праздник', 'фестиваль',
            'сообщест', 'активист', 'тос', 'совет', 'собрание', 'помощь',
            'волонтер', 'дружб', 'единство', 'конфликт', 'скандал'
        ]
    }
    
    # Маркеры глубины вопроса (городской контекст)
    DEPTH_MARKERS = {
        'поверхностный': [
            'как', 'что делать', 'посоветуй', 'подскажи', 'научи',
            'метод', 'способ', 'инструмент', 'решение', 'план'
        ],
        'глубинный': [
            'почему', 'зачем', 'отчего', 'в чем причина', 'из-за чего',
            'откуда', 'как так', 'почему у нас', 'что с городом'
        ],
        'системный': [
            'систем', 'структур', 'корень', 'причин', 'закономер',
            'цикл', 'петля', 'круг', 'механизм', 'парадокс'
        ]
    }
    
    # Маркеры "эмоционального состояния" города (тональность)
    CITY_EMOTION_MARKERS = {
        'тревога': [
            'страшно', 'боюсь', 'тревожно', 'волнует', 'беспокоит',
            'опасно', 'жутко', 'напряжен', 'паник', 'кошмар'
        ],
        'недовольство': [
            'плохо', 'ужасно', 'отвратительно', 'безобразно', 'возмутительно',
            'бесит', 'раздражает', 'надоело', 'достало', 'неприемлемо'
        ],
        'безнадежность': [
            'бесполезно', 'безнадежн', 'никуда', 'все равно', 'не изменится',
            'вечно', 'постоянно', 'никогда', 'тупик', 'безвыходн'
        ],
        'надежда': [
            'хорошо', 'отлично', 'замечательно', 'радует', 'нравится',
            'здорово', 'прекрасно', 'классно', 'супер', 'отлично'
        ]
    }
    
    def __init__(self, model: ConfinementModel9, city_name: str = None):
        """
        Инициализация анализатора
        
        Args:
            model: конфайнтмент-модель города
            city_name: название города
        """
        self.model = model
        self.city_name = city_name or model.city_name or "Город"
        self.loop_analyzer = CityLoopAnalyzer(model)
        self.loops = self.loop_analyzer.analyze() if self.loop_analyzer else []
        
        # Кэш для результатов анализа
        self._analysis_cache = {}
        self._cache_time = {}
        self.cache_ttl = 300  # 5 минут
        
        # Определяем ключевое ограничение города
        self.key = self._detect_key_confinement()
        
        logger.info(f"CityQuestionContextAnalyzer инициализирован для города {self.city_name}")
    
    def _detect_key_confinement(self) -> Optional[Dict[str, Any]]:
        """
        Определяет ключевое ограничение города из петель
        """
        if not self.loops:
            return None
        
        # Ищем главную петлю (самую сильную)
        strongest_loop = None
        max_impact = 0
        
        for loop in self.loops:
            impact = loop.get('impact', 0)
            if impact > max_impact:
                max_impact = impact
                strongest_loop = loop
        
        if strongest_loop:
            # Извлекаем первый элемент петли как ключевой
            elements = strongest_loop.get('elements', [])
            first_elem = elements[0] if elements else None
            
            return {
                'description': strongest_loop.get('description', 'Ключевое ограничение города'),
                'element': first_elem,
                'impact': max_impact,
                'type': strongest_loop.get('type', 'major_cycle'),
                'priority': strongest_loop.get('strategic_priority', 'СРЕДНИЙ')
            }
        
        return None
    
    def analyze(self, question: str, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Главный метод анализа вопроса о городе
        
        Args:
            question: текст вопроса
            force_refresh: принудительно обновить кэш
            
        Returns:
            dict: полный контекстный анализ вопроса
        """
        # Проверяем кэш
        cache_key = hash(question) % 10000
        if not force_refresh and cache_key in self._analysis_cache:
            cache_age = (datetime.now() - self._cache_time.get(cache_key, datetime.now())).seconds
            if cache_age < self.cache_ttl:
                return self._analysis_cache[cache_key]
        
        # Проводим анализ
        analysis = {
            'question': question,
            'city_name': self.city_name,
            'timestamp': datetime.now().isoformat(),
            'vectors': self._analyze_vectors(question),
            'depth': self._analyze_depth(question),
            'city_emotion': self._analyze_city_emotion(question),
            'loops': self._find_activated_loops(question),
            'key_confinement': self._check_key_confinement(question),
            'system_paradox': self._find_system_paradox(question),
            'subtext': self._formulate_subtext(question),
            'reflection': self._generate_reflection(question),
            'stakeholder_perspective': self._get_stakeholder_perspective(question)
        }
        
        # Кэшируем результат
        self._analysis_cache[cache_key] = analysis
        self._cache_time[cache_key] = datetime.now()
        
        return analysis
    
    def _analyze_vectors(self, question: str) -> List[Dict[str, Any]]:
        """
        Определяет, какие векторы города затронуты в вопросе
        """
        question_lower = question.lower()
        vectors = []
        
        for vector, keywords in self.VECTOR_KEYWORDS.items():
            matches = []
            for keyword in keywords:
                if keyword in question_lower:
                    matches.append(keyword)
            
            if matches:
                # Получаем уровень из модели города
                level = self._get_city_vector_level(vector)
                
                # Рассчитываем релевантность
                relevance = min(len(matches) * 0.2, 0.9)
                
                vector_info = VECTORS.get(vector, {})
                
                vectors.append({
                    'vector': vector,
                    'name': vector_info.get('name', vector),
                    'emoji': vector_info.get('emoji', '🔍'),
                    'level': level,
                    'relevance': relevance,
                    'matches': matches[:3],
                    'city_state': self._get_city_state_description(vector, level)
                })
        
        return sorted(vectors, key=lambda x: x['relevance'], reverse=True)
    
    def _get_city_vector_level(self, vector: str) -> int:
        """Получает уровень вектора города из модели"""
        if self.model and hasattr(self.model, 'source_scores'):
            score = self.model.source_scores.get(vector, 3.0)
            # Преобразуем балл в уровень (1-6)
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
        return 3
    
    def _get_city_state_description(self, vector: str, level: int) -> str:
        """Возвращает описание состояния города по вектору"""
        states = {
            'СБ': {
                1: "город в кризисе безопасности",
                2: "постоянная тревога и напряжённость",
                3: "ситуативная стабильность",
                4: "уверенность и спокойствие",
                5: "высокая защищённость",
                6: "абсолютная гармония"
            },
            'ТФ': {
                1: "экономический коллапс",
                2: "выживание и нехватка ресурсов",
                3: "стагнация, хватает на базовое",
                4: "развитие и рост",
                5: "процветание и избыток",
                6: "экономическое изобилие"
            },
            'УБ': {
                1: "жизнь невыносима",
                2: "серость и апатия",
                3: "терпимо, но хочется лучше",
                4: "комфортно и приятно",
                5: "город счастья",
                6: "город-утопия"
            },
            'ЧВ': {
                1: "изоляция и атомизация",
                2: "отчуждение и недоверие",
                3: "нейтральные формальные связи",
                4: "взаимодействие и сообщества",
                5: "единство и сплочённость",
                6: "город-организм"
            }
        }
        return states.get(vector, {}).get(level, "среднее состояние")
    
    def _analyze_depth(self, question: str) -> Dict[str, Any]:
        """
        Анализирует глубину вопроса о городе
        """
        question_lower = question.lower()
        
        depth_type = 'поверхностный'
        for d_type, markers in self.DEPTH_MARKERS.items():
            for marker in markers:
                if marker in question_lower:
                    depth_type = d_type
                    break
        
        # Анализируем масштаб вопроса
        local_scale = any(word in question_lower for word in ['двор', 'подъезд', 'дом', 'улица', 'район'])
        city_scale = any(word in question_lower for word in ['город', 'центр', 'окраина', 'микрорайон'])
        system_scale = any(word in question_lower for word in ['систем', 'структур', 'власть', 'управлен'])
        
        return {
            'type': depth_type,
            'scale': 'локальный' if local_scale else 'городской' if city_scale else 'системный' if system_scale else 'общий',
            'is_why_question': 'почему' in question_lower or 'зачем' in question_lower,
            'is_how_question': 'как' in question_lower and 'почему' not in question_lower,
            'is_system_question': system_scale
        }
    
    def _analyze_city_emotion(self, question: str) -> Dict[str, Any]:
        """
        Анализирует эмоциональный фон вопроса о городе
        """
        question_lower = question.lower()
        
        emotions = {}
        primary_emotion = None
        max_intensity = 0
        
        for emotion, markers in self.CITY_EMOTION_MARKERS.items():
            matches = []
            for marker in markers:
                if marker in question_lower:
                    matches.append(marker)
            
            if matches:
                intensity = min(len(matches) * 0.25, 1.0)
                emotions[emotion] = {
                    'intensity': intensity,
                    'matches': matches[:3]
                }
                
                if intensity > max_intensity:
                    max_intensity = intensity
                    primary_emotion = emotion
        
        return {
            'present': bool(emotions),
            'primary': primary_emotion,
            'intensity': max_intensity,
            'all': emotions
        }
    
    def _find_activated_loops(self, question: str) -> List[Dict[str, Any]]:
        """
        Находит городские петли, которые активируются вопросом
        """
        if not self.loops:
            return []
        
        question_lower = question.lower()
        activated = []
        
        for loop in self.loops:
            loop_elements = loop.get('elements', [])
            matches = []
            
            for elem in loop_elements:
                if hasattr(elem, 'description') and elem.description:
                    desc_words = elem.description.lower().split()
                    for word in desc_words:
                        if len(word) > 3 and word in question_lower:
                            matches.append(word)
            
            if matches:
                activation_strength = min(len(matches) * 0.2, 0.9)
                activated.append({
                    'loop': loop,
                    'description': loop.get('description', 'Неизвестная петля'),
                    'type': loop.get('type', 'minor_cycle'),
                    'type_name': loop.get('type_name', 'Второстепенная'),
                    'priority': loop.get('strategic_priority', 'НИЗКИЙ'),
                    'activation_strength': activation_strength,
                    'matches': matches[:5]
                })
        
        return sorted(activated, key=lambda x: x['activation_strength'], reverse=True)
    
    def _check_key_confinement(self, question: str) -> Optional[Dict[str, Any]]:
        """
        Проверяет, связан ли вопрос с ключевым ограничением города
        """
        if not self.key:
            return None
        
        question_lower = question.lower()
        key_desc = self.key.get('description', '').lower()
        key_words = set(key_desc.split())
        
        matches = []
        for word in key_words:
            if len(word) > 3 and word in question_lower:
                matches.append(word)
        
        if matches:
            return {
                'is_related': True,
                'strength': min(len(matches) * 0.2, 0.9),
                'description': self.key.get('description', ''),
                'element': self.key.get('element'),
                'priority': self.key.get('priority', 'СРЕДНИЙ'),
                'matches': matches[:5]
            }
        
        return {'is_related': False}
    
    def _find_system_paradox(self, question: str) -> Optional[str]:
        """
        Ищет системный парадокс в вопросе о городе
        """
        question_lower = question.lower()
        
        # Получаем уровни векторов
        safety_level = self._get_city_vector_level('СБ')
        economy_level = self._get_city_vector_level('ТФ')
        quality_level = self._get_city_vector_level('УБ')
        
        # Проверяем типичные парадоксы
        if safety_level <= 2 and 'безопасность' in question_lower:
            return f"Город хочет быть безопасным, но страх уже стал частью повседневности. Камеры и патрули не убирают тревогу — они её легитимируют."
        
        if economy_level <= 2 and 'деньги' in question_lower:
            return f"Денег нет, но их не будет, пока город не начнёт привлекать инвестиции. А инвестиции не идут, потому что денег нет."
        
        if quality_level <= 2 and 'благоустройство' in question_lower:
            return f"Город хочет стать комфортным, но жители уже не верят, что что-то изменится. Без веры нет участия, без участия нет изменений."
        
        if 'власть' in question_lower and 'жители' in question_lower:
            return f"Власть ждёт инициативы от жителей, жители ждут действий от власти. Так и стоят."
        
        return None
    
    def _formulate_subtext(self, question: str) -> str:
        """
        Формулирует подтекст вопроса - что на самом деле спрашивают о городе
        """
        vectors = self._analyze_vectors(question)
        depth = self._analyze_depth(question)
        emotion = self._analyze_city_emotion(question)
        key = self._check_key_confinement(question)
        
        # Если вопрос глубинный и связан с ключевым ограничением
        if key and key.get('is_related') and depth['type'] != 'поверхностный':
            return f"Вы спрашиваете не просто о проблеме — вы вышли на ключевое системное ограничение города. За вопросом стоит {key['description'].lower()}"
        
        # Если вопрос про безопасность
        if any(v['vector'] == 'СБ' for v in vectors):
            if emotion.get('primary') == 'тревога':
                return "За вопросом о безопасности — не статистика преступности, а чувство, что город стал чужим. Что здесь нельзя расслабиться."
        
        # Если вопрос про экономику
        if any(v['vector'] == 'ТФ' for v in vectors):
            if emotion.get('primary') == 'безнадежность':
                return "Вы спрашиваете про деньги, но на самом деле про ощущение, что город не развивается. Что молодёжи здесь не место."
        
        # Если вопрос про качество жизни
        if any(v['vector'] == 'УБ' for v in vectors):
            return "За вопросом о комфорте — не только про скамейки и парки. Про то, приятно ли здесь жить, хочется ли здесь оставаться."
        
        # Если вопрос про сообщества
        if any(v['vector'] == 'ЧВ' for v in vectors):
            return "Вы спрашиваете про соседей и сообщества, но на самом деле про одиночество в городе. Про то, что даже в толпе можно быть одному."
        
        # Универсальный подтекст
        if depth['type'] == 'системный':
            return "Вы чувствуете, что проблема не случайна, что за ней стоит что-то большее. И вы правы."
        else:
            return "Вы описываете симптом. Но за ним — вся городская система."
    
    def _generate_reflection(self, question: str) -> str:
        """
        Генерирует основную рефлексию - то, что можно сказать о городе
        """
        vectors = self._analyze_vectors(question)
        depth = self._analyze_depth(question)
        emotion = self._analyze_city_emotion(question)
        loops = self._find_activated_loops(question)
        paradox = self._find_system_paradox(question)
        key = self._check_key_confinement(question)
        
        reflection = []
        
        # Учитываем эмоциональный фон города
        if emotion['present'] and emotion['intensity'] > 0.5:
            if emotion['primary'] == 'тревога':
                reflection.append(f"В этом вопросе чувствуется тревога за город. Не та, которую можно успокоить отчётом, а та, что живёт в людях.")
            elif emotion['primary'] == 'недовольство':
                reflection.append(f"Слышу усталость в этом вопросе. Не физическую, а ту, когда жители перестали верить, что что-то может измениться.")
            elif emotion['primary'] == 'безнадежность':
                reflection.append(f"Здесь есть отчаяние. Город застрял, и кажется, что выхода нет.")
            elif emotion['primary'] == 'надежда':
                reflection.append(f"В этом вопросе есть надежда. Кто-то ещё верит, что город может стать лучше.")
        
        # Добавляем анализ векторов
        if vectors:
            main_vector = vectors[0]
            reflection.append(f"Судя по профилю города, в сфере {main_vector['name'].lower()} у вас {main_vector['city_state']}.")
        
        # Добавляем парадокс, если есть
        if paradox:
            reflection.append(paradox)
        
        # Добавляем информацию о петлях
        if loops:
            main_loop = loops[0]
            priority_text = {
                'КРИТИЧЕСКИЙ': 'Это критический порочный круг',
                'ВЫСОКИЙ': 'Это сильный порочный круг',
                'СРЕДНИЙ': 'Это значимый порочный круг',
                'НИЗКИЙ': 'Это вторичный порочный круг'
            }.get(main_loop.get('priority', 'НИЗКИЙ'), 'Это порочный круг')
            
            reflection.append(f"{priority_text}: {main_loop['description']}")
        
        # Добавляем связь с ключевым ограничением
        if key and key.get('is_related'):
            reflection.append(f"И этот вопрос бьёт прямо в ключевое ограничение города ({key.get('priority', 'СРЕДНИЙ')} приоритет).")
        
        # Формулируем суть
        if depth['type'] == 'системный':
            reflection.append("Вы смотрите глубже симптомов. И это правильно — проблема действительно системная.")
        elif depth['type'] == 'глубинный':
            reflection.append("Вы ищете не просто решение, а понимание причин. Это путь к реальным изменениям.")
        else:
            if key and key.get('is_related'):
                reflection.append("За этим частным вопросом стоит системная проблема города.")
        
        # Если вопрос о локальной проблеме
        if depth['scale'] == 'локальный':
            reflection.append("Эта локальная проблема — отражение системного сбоя. Решить её в отдельном дворе можно, но без системных изменений она вернётся.")
        
        # Если ничего не нашли, даём универсальную рефлексию
        if not reflection:
            reflection.append(f"Вы описали ситуацию, в которой застрял {self.city_name}. Не столько спрашивая, сколько надеясь, что кто-то увидит, как городу тяжело.")
        
        return " ".join(reflection)
    
    def _get_stakeholder_perspective(self, question: str) -> Dict[str, str]:
        """
        Возвращает перспективы разных стейкхолдеров на заданный вопрос
        """
        perspectives = {}
        
        # Перспектива власти
        if any(word in question.lower() for word in ['деньги', 'бюджет', 'инвестиции']):
            perspectives['administration'] = "С точки зрения администрации: вопрос ресурсов. Но проблема не только в их количестве, но и в приоритетах."
        elif any(word in question.lower() for word in ['безопасность', 'преступность']):
            perspectives['administration'] = "С точки зрения власти: безопасность требует бюджета и системы. Но камеры и полиция не решают проблему доверия."
        else:
            perspectives['administration'] = "Власти видят проблему, но зажаты между бюджетом, политикой и ожиданиями жителей."
        
        # Перспектива бизнеса
        if any(word in question.lower() for word in ['экономика', 'работа', 'бизнес']):
            perspectives['business'] = "Бизнес готов инвестировать, но нужны стабильные правила игры и предсказуемая среда."
        else:
            perspectives['business'] = "Бизнес чувствует нестабильность и не спешит вкладываться в город."
        
        # Перспектива активистов
        if any(word in question.lower() for word in ['сообщество', 'актив', 'инициатива']):
            perspectives['activists'] = "Активисты готовы включаться, но им нужна поддержка и признание со стороны власти."
        else:
            perspectives['activists'] = "Активность есть, но она остаётся локальной, не перерастая в системные изменения."
        
        # Перспектива жителей
        perspectives['residents'] = "Жители хотят видимых изменений здесь и сейчас. Долгосрочные стратегии их не греют."
        
        return perspectives
    
    def get_response_context(self, question: str) -> Dict[str, Any]:
        """
        Возвращает контекст для формирования ответа о городе
        """
        analysis = self.analyze(question)
        
        return {
            'city_name': self.city_name,
            'vectors': analysis['vectors'],
            'depth': analysis['depth'],
            'city_emotion': analysis['city_emotion'],
            'loops': analysis['loops'],
            'key_confinement': analysis['key_confinement'],
            'system_paradox': analysis['system_paradox'],
            'subtext': analysis['subtext'],
            'reflection': analysis['reflection'],
            'stakeholder_perspectives': analysis['stakeholder_perspective']
        }
    
    def get_reflection_text(self, question: str) -> str:
        """
        Возвращает только текст рефлексии
        """
        analysis = self.analyze(question)
        return analysis['reflection']
    
    def get_analysis_for_report(self, question: str) -> Dict[str, Any]:
        """
        Возвращает полный анализ для отчёта
        """
        analysis = self.analyze(question)
        
        return {
            'city': self.city_name,
            'question': question,
            'analysis_date': datetime.now().isoformat(),
            'affected_vectors': [{'vector': v['vector'], 'name': v['name'], 'level': v['level']} for v in analysis['vectors']],
            'depth_type': analysis['depth']['type'],
            'scale': analysis['depth']['scale'],
            'primary_emotion': analysis['city_emotion']['primary'],
            'activated_loops': len(analysis['loops']),
            'touches_key_confinement': analysis['key_confinement'].get('is_related', False) if analysis['key_confinement'] else False,
            'reflection': analysis['reflection']
        }
    
    def clear_cache(self):
        """Очищает кэш анализов"""
        self._analysis_cache.clear()
        self._cache_time.clear()
        logger.info(f"Кэш анализов для города {self.city_name} очищен")


# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def create_city_analyzer_from_model(model: ConfinementModel9) -> CityQuestionContextAnalyzer:
    """
    Создаёт анализатор из модели города
    """
    return CityQuestionContextAnalyzer(model, model.city_name)


def analyze_city_question(model: ConfinementModel9, question: str) -> str:
    """
    Быстрый анализ вопроса о городе - возвращает только рефлексию
    """
    analyzer = CityQuestionContextAnalyzer(model, model.city_name)
    return analyzer.get_reflection_text(question)


# ============================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================

if __name__ == "__main__":
    print("🧪 Тестирование CityQuestionContextAnalyzer...")
    
    # Создаём тестовую модель города
    from confinement_model import ConfinementModel9
    
    test_metrics = {'СБ': 2.3, 'ТФ': 2.8, 'УБ': 3.2, 'ЧВ': 2.5}
    model = ConfinementModel9(city_name="Тестовый Город", city_id=1)
    model.build_from_city_data(test_metrics, [])
    
    # Создаём анализатор
    analyzer = CityQuestionContextAnalyzer(model)
    
    # Тестируем вопросы
    test_questions = [
        "Почему в нашем городе так небезопасно?",
        "Как привлечь инвестиции в город?",
        "Почему у нас такие плохие дороги и дворы?",
        "Что делать с оттоком молодёжи?",
        "Почему власть нас не слышит?"
    ]
    
    for q in test_questions:
        print(f"\n{'='*70}")
        print(f"❓ Вопрос: {q}")
        print(f"{'='*70}")
        
        reflection = analyzer.get_reflection_text(q)
        print(f"\n🧠 Рефлексия:\n{reflection}")
        
        # Показываем затронутые векторы
        analysis = analyzer.analyze(q)
        if analysis['vectors']:
            vectors_str = ", ".join([f"{v['emoji']}{v['name']}" for v in analysis['vectors'][:3]])
            print(f"\n📊 Затронутые сферы: {vectors_str}")
    
    print("\n✅ Тест завершен")
