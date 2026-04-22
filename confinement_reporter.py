#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 4: ИНТЕГРАЦИЯ С ОТВЕТАМИ (confinement_reporter.py)
Формирует отчеты и ответы на основе конфайнтмент-модели для городских систем
Адаптировано для анализа городов на основе новостного контекста
"""

from datetime import datetime
from typing import Optional, Dict, List, Any
import logging

# Импортируем необходимые классы из других модулей
from confinement_model import ConfinementModel9, ConfinementElement, VECTORS, get_vector_description, get_city_state

# Настройка логирования
logger = logging.getLogger(__name__)


class CityLoopAnalyzer:
    """
    Анализатор петель обратной связи для городских систем
    """
    
    def __init__(self, model: ConfinementModel9):
        self.model = model
        self.loops = []
        
    def analyze(self) -> List[Dict]:
        """Анализирует петли в городской системе"""
        # Если петли уже найдены в модели
        if self.model.loops:
            self.loops = self.model.loops
        else:
            # Пытаемся найти петли самостоятельно
            self._find_city_loops()
        
        return self.loops
    
    def _find_city_loops(self):
        """Находит характерные для города петли"""
        self.loops = []
        
        # Проверяем наличие основных петель
        # Петля 1: Проблемы → Безопасность → Экономика
        if self._check_cycle([1, 2, 3]):
            self.loops.append({
                'type': 'safety_economy_cycle',
                'description': 'Проблемы с безопасностью отпугивают бизнес, экономический спад усугубляет проблемы',
                'impact': 0.7,
                'elements': [1, 2, 3],
                'breaking_points': ['Инвестиции в безопасность', 'Создание рабочих мест']
            })
        
        # Петля 2: Экономика → Качество жизни → Социальный капитал
        if self._check_cycle([3, 4, 5]):
            self.loops.append({
                'type': 'quality_of_life_cycle',
                'description': 'Экономические проблемы снижают качество жизни, что разрушает социальные связи',
                'impact': 0.65,
                'elements': [3, 4, 5],
                'breaking_points': ['Социальные программы', 'Благоустройство']
            })
        
        # Петля 3: Полный порочный круг
        if self._check_cycle([1, 2, 3, 4, 9]):
            self.loops.append({
                'type': 'full_vicious_cycle',
                'description': 'Полный порочный круг: проблемы → страх → экономический спад → падение качества жизни → укрепление негативных мифов',
                'impact': 0.85,
                'elements': [1, 2, 3, 4, 9],
                'breaking_points': ['Разрыв городского мифа', 'Быстрые позитивные изменения']
            })
        
        # Петля 4: Институциональная
        if self._check_cycle([5, 7, 6]):
            self.loops.append({
                'type': 'institutional_cycle',
                'description': 'Негативные нарративы парализуют институты, слабые институты не могут улучшить среду',
                'impact': 0.75,
                'elements': [5, 7, 6],
                'breaking_points': ['Прозрачность власти', 'Успешные кейсы']
            })
    
    def _check_cycle(self, elements: List[int]) -> bool:
        """Проверяет существование цикла связей"""
        for i in range(len(elements)-1):
            from_elem = self.model.elements.get(elements[i])
            to_elem = self.model.elements.get(elements[i+1])
            
            if not from_elem or not to_elem:
                return False
            
            if to_elem.id not in from_elem.causes:
                return False
        
        # Проверяем замыкание
        last_elem = self.model.elements.get(elements[-1])
        first_elem = self.model.elements.get(elements[0])
        
        if not last_elem or not first_elem:
            return False
        
        return first_elem.id in last_elem.causes
    
    def get_strongest_loop(self) -> Optional[Dict]:
        """Возвращает самую сильную петлю"""
        if not self.loops:
            return None
        
        return max(self.loops, key=lambda x: x.get('impact', 0))
    
    def get_break_points(self) -> List[Dict]:
        """Возвращает точки разрыва для петель"""
        break_points = []
        
        for loop in self.loops:
            for point in loop.get('breaking_points', []):
                break_points.append({
                    'loop_type': loop['type'],
                    'description': point,
                    'impact': loop.get('impact', 0.5)
                })
        
        return break_points


class CityKeyConfinementDetector:
    """
    Детектор ключевого ограничения для городской системы
    """
    
    def __init__(self, model: ConfinementModel9, loops: List[Dict]):
        self.model = model
        self.loops = loops
        
    def detect(self) -> Optional[Dict]:
        """Определяет ключевое ограничение города"""
        if not self.model.key_confinement:
            # Если ключевой конфайнмент не определен в модели, определяем сами
            return self._detect_from_elements()
        
        # Используем уже определенный в модели
        key = self.model.key_confinement
        
        # Добавляем интервенцию
        key['intervention'] = self._get_intervention_for_city(key['id'])
        
        return key
    
    def _detect_from_elements(self) -> Optional[Dict]:
        """Определяет ключевое ограничение на основе элементов"""
        # Приоритет: элемент 9 (замыкающий) > элемент 5 (нарратив) > самый сильный элемент
        
        # Проверяем замыкающий элемент
        closing = self.model.elements.get(9)
        if closing and closing.strength > 0.7:
            return {
                'id': 9,
                'element': closing,
                'description': self._describe_city_confinement(9, closing),
                'importance': 1.0,
                'intervention': self._get_intervention_for_city(9)
            }
        
        # Проверяем общий нарратив
        narrative = self.model.elements.get(5)
        if narrative and narrative.strength > 0.7:
            return {
                'id': 5,
                'element': narrative,
                'description': self._describe_city_confinement(5, narrative),
                'importance': 0.9,
                'intervention': self._get_intervention_for_city(5)
            }
        
        # Ищем самый сильный элемент
        strongest = None
        for elem in self.model.elements.values():
            if elem and (strongest is None or elem.strength > strongest.strength):
                strongest = elem
        
        if strongest:
            return {
                'id': strongest.id,
                'element': strongest,
                'description': self._describe_city_confinement(strongest.id, strongest),
                'importance': strongest.strength,
                'intervention': self._get_intervention_for_city(strongest.id)
            }
        
        return None
    
    def _describe_city_confinement(self, element_id: int, element: ConfinementElement) -> str:
        """Описывает ключевое ограничение для города"""
        descriptions = {
            1: f"**Главная проблема города** — {element.description[:80] if element.description else 'Кризисная ситуация'}... Держит всю систему в напряжении.",
            2: f"**Ключевой вызов в безопасности** — {element.name}. Страх и тревога парализуют развитие города.",
            3: f"**Экономическое ограничение** — {element.name}. Нехватка ресурсов не позволяет решать накопившиеся проблемы.",
            4: f"**Критическое падение качества жизни** — {element.name}. Люди теряют мотивацию что-то менять.",
            5: f"**Центральный городской нарратив** — {element.description[:80] if element.description else 'Убеждение, блокирующее развитие'}... Он пронизывает все уровни системы.",
            6: f"**Деградация локальной среды** — {element.name}. Районы становятся некомфортными для жизни.",
            7: f"**Ключевой институциональный провал** — {element.name}. Система управления не справляется с вызовами.",
            8: f"**Контекстная ловушка** — {element.name}. Региональные проблемы давят на городское развитие.",
            9: f"**Замыкающий городской миф** — {element.description[:80] if element.description else 'Самосбывающееся пророчество'}... Именно он не дает системе вырваться из кризиса."
        }
        
        return descriptions.get(element_id, f"Ключевое ограничение: {element.name}")
    
    def _get_intervention_for_city(self, element_id: int) -> Dict:
        """Возвращает интервенцию для города"""
        interventions = {
            1: {
                'target': 'Главная проблема города',
                'approach': 'Системный подход',
                'method': 'Декомпозиция проблемы на подзадачи',
                'exercise': 'Провести анализ первопричин, создать дорожную карту решения',
                'duration': '3-6 месяцев',
                'expected': 'Понимание структуры проблемы и первые шаги к решению',
                'city_level': 'Стратегический'
            },
            2: {
                'target': 'Безопасность и стабильность',
                'approach': 'Комплексная безопасность',
                'method': 'Внедрение программ "Безопасный город"',
                'exercise': 'Установка камер, увеличение патрулей, программы neighborhood watch',
                'duration': '6-12 месяцев',
                'expected': 'Снижение преступности, рост доверия жителей',
                'city_level': 'Тактический'
            },
            3: {
                'target': 'Экономика и инфраструктура',
                'approach': 'Экономическое развитие',
                'method': 'Привлечение инвестиций, поддержка МСП',
                'exercise': 'Создание ТОР, бизнес-инкубаторов, инвестиционных сессий',
                'duration': '1-3 года',
                'expected': 'Рост экономики, новые рабочие места',
                'city_level': 'Стратегический'
            },
            4: {
                'target': 'Качество жизни',
                'approach': 'Человеко-ориентированность',
                'method': 'Благоустройство, социальные программы',
                'exercise': 'Создание общественных пространств, развитие соцсферы',
                'duration': '6-18 месяцев',
                'expected': 'Повышение комфорта жизни, снижение оттока населения',
                'city_level': 'Тактический'
            },
            5: {
                'target': 'Городские нарративы',
                'approach': 'Коммуникационная стратегия',
                'method': 'Медиа-кампании, работа с лидерами мнений',
                'exercise': 'Серия публикаций о позитивных изменениях, городские фестивали',
                'duration': '3-9 месяцев',
                'expected': 'Изменение восприятия города, рост городской гордости',
                'city_level': 'Коммуникационный'
            },
            6: {
                'target': 'Локальная среда',
                'approach': 'Низовое развитие',
                'method': 'Программы инициативного бюджетирования',
                'exercise': 'Конкурс проектов благоустройства дворов, поддержка ТОС',
                'duration': '6-12 месяцев',
                'expected': 'Активные сообщества, комфортные дворы',
                'city_level': 'Локальный'
            },
            7: {
                'target': 'Городские институты',
                'approach': 'Институциональная реформа',
                'method': 'Повышение прозрачности, цифровизация',
                'exercise': 'Внедрение открытых данных, электронных услуг, обратной связи',
                'duration': '12-24 месяца',
                'expected': 'Эффективное управление, доверие к власти',
                'city_level': 'Системный'
            },
            8: {
                'target': 'Региональный контекст',
                'approach': 'Межмуниципальное сотрудничество',
                'method': 'Лоббирование, кооперация',
                'exercise': 'Создание ассоциации городов, совместные проекты',
                'duration': '12-36 месяцев',
                'expected': 'Поддержка региона, совместные решения',
                'city_level': 'Стратегический'
            },
            9: {
                'target': 'Городской миф',
                'approach': 'Мифодизайн',
                'method': 'Создание новой городской идентичности',
                'exercise': 'Разработка и продвижение нового бренда города, серия успешных кейсов',
                'duration': '6-24 месяца',
                'expected': 'Новая городская идентичность, прорыв порочного круга',
                'city_level': 'Трансформационный'
            }
        }
        
        intervention = interventions.get(element_id, {
            'target': 'Системная проблема',
            'approach': 'Комплексный анализ',
            'method': 'Глубокое исследование',
            'exercise': 'Провести диагностику и разработать программу развития',
            'duration': 'Не определено',
            'expected': 'Улучшение ситуации',
            'city_level': 'Аналитический'
        })
        
        # Добавляем описание на основе модели
        if self.model.key_confinement:
            intervention['description'] = self.model.key_confinement.get('description', '')
        
        return intervention


class ConfinementReporter:
    """
    Формирует отчеты и ответы на основе конфайнтмент-модели для городов
    """
    
    def __init__(self, model: ConfinementModel9, city_name: str = None):
        """
        Инициализация репортера
        
        Args:
            model: построенная конфайнтмент-модель города
            city_name: название города
        """
        self.model = model
        self.city_name = city_name or model.city_name or "Город"
        self.loop_analyzer = CityLoopAnalyzer(model)
        self.loops = self.loop_analyzer.analyze()
        self.key_detector = CityKeyConfinementDetector(model, self.loops)
        self.key = self.key_detector.detect()
        
        logger.info(f"ConfinementReporter инициализирован для города {self.city_name}")
    
    def get_summary(self) -> str:
        """
        Возвращает краткое резюме модели для быстрого понимания ситуации в городе
        
        Returns:
            str: краткий отчет о модели
        """
        if not self.model.elements.get(1):
            return "Модель для этого города еще не построена"
        
        lines = []
        
        # Заголовок
        lines.append(f"🏙️ **КОНФАЙНМЕНТ-МОДЕЛЬ ГОРОДА: {self.city_name.upper()}**\n")
        
        # Результат (главная проблема)
        result = self.model.elements.get(1)
        if result:
            desc = result.description[:100] if result.description else "Не определена"
            lines.append(f"🎯 **Главная проблема:** {desc}...\n")
        
        # Ключевой конфайнмент
        if self.key:
            lines.append(f"⛓ **Ключевое ограничение развития:**")
            lines.append(self.key['description'])
            lines.append("")
        
        # Текущие метрики города
        lines.append("📊 **Текущее состояние города:**")
        for vector_code, score in self.model.source_scores.items():
            if vector_code in VECTORS:
                vector_info = VECTORS[vector_code]
                lvl = self._get_level(score)
                lines.append(f"  {vector_info['emoji']} {vector_info['name']}: уровень {lvl}/6")
        lines.append("")
        
        # Петли
        if self.loops:
            strongest = self.loop_analyzer.get_strongest_loop()
            if strongest:
                lines.append(f"🔄 **Главный порочный круг:**")
                lines.append(strongest['description'])
                impact = strongest.get('impact', 0)
                lines.append(f"Сила влияния: {impact:.1%}")
                lines.append("")
        
        # Замыкание системы
        closure_status = "🔒 замкнута (критично)" if self.model.is_closed else "🔓 не замкнута (есть шанс)"
        closure_score = self.model.closure_score if hasattr(self.model, 'closure_score') else 0
        lines.append(f"📈 **Городская система:** {closure_status} (степень зацикленности {closure_score:.1%})")
        
        return "\n".join(lines)
    
    def get_detailed_report(self) -> str:
        """
        Возвращает детальный отчет по модели со всеми элементами
        
        Returns:
            str: подробный отчет о городе
        """
        lines = []
        
        lines.append(f"🏙️ **ПОЛНАЯ КОНФАЙНМЕНТ-МОДЕЛЬ ГОРОДА {self.city_name.upper()}**\n")
        lines.append(f"📅 Анализ проведен: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
        
        # Метаданные города
        if self.model.population or self.model.region or self.model.city_type:
            lines.append("**🏷️ Метаданные города:**")
            if self.model.city_type:
                lines.append(f"  • Тип: {self.model.city_type}")
            if self.model.region:
                lines.append(f"  • Регион: {self.model.region}")
            if self.model.population:
                lines.append(f"  • Население: {self.model.population:,} чел.")
            lines.append("")
        
        # Все элементы
        lines.append("**🔍 9 ключевых элементов системы:**\n")
        
        element_descriptions = {
            1: "🎯 Главная проблема",
            2: "🛡️ Безопасность и стабильность",
            3: "🏗️ Экономика и инфраструктура",
            4: "😊 Качество жизни",
            5: "💭 Городские нарративы",
            6: "🏘️ Локальная среда",
            7: "🏛️ Городские институты",
            8: "🗺️ Региональный контекст",
            9: "🌍 Замыкающий городской миф"
        }
        
        for i in range(1, 10):
            elem = self.model.elements.get(i)
            if not elem:
                continue
            
            default_name = element_descriptions.get(i, f"Элемент {i}")
            name = elem.name if elem.name != f"Элемент {i}" else default_name
            
            lines.append(f"**{i}. {name}**")
            
            if elem.description:
                desc = elem.description[:200] if len(elem.description) > 200 else elem.description
                lines.append(f"   {desc}")
            
            # Добавляем уровень если есть
            if elem.level:
                lines.append(f"   📊 Уровень: {elem.level}/6")
            
            # Добавляем архетип если есть
            if elem.archetype:
                lines.append(f"   🏷️ Архетип: {elem.archetype}")
            
            # Связи
            if elem.causes:
                causes_str = ", ".join([f"→{c}" for c in elem.causes[:4]])
                lines.append(f"   🔗 Влияет на элементы: {causes_str}")
            
            # Новостные ссылки
            if elem.news_references:
                lines.append(f"   📰 Подтверждающие новости: {len(elem.news_references)}")
            
            lines.append("")
        
        # Петли
        if self.loops:
            lines.append("**🔄 Порочные круги (рекурсивные петли):**\n")
            for i, loop in enumerate(self.loops, 1):
                lines.append(f"{i}. **{loop['description']}**")
                impact = loop.get('impact', 0)
                lines.append(f"   Сила: {impact:.1%}")
                
                if loop.get('breaking_points'):
                    points = ", ".join(loop['breaking_points'][:3])
                    lines.append(f"   💡 Точки разрыва: {points}")
                lines.append("")
        
        # Ключевой конфайнмент
        if self.key:
            lines.append("**⛓ КЛЮЧЕВОЕ ОГРАНИЧЕНИЕ РАЗВИТИЯ**\n")
            lines.append(self.key['description'])
            lines.append("")
            
            # Интервенция
            intervention = self.key.get('intervention', {})
            if intervention:
                lines.append("**💡 ПЛАН ДЕЙСТВИЙ (ИНТЕРВЕНЦИЯ)**")
                lines.append(f"🎯 Цель: {intervention.get('target', 'Не указана')}")
                lines.append(f"📌 Подход: {intervention.get('approach', 'Не указан')}")
                lines.append(f"⚡ Метод: {intervention.get('method', 'Не указан')}")
                lines.append(f"📋 Упражнение/проект: {intervention.get('exercise', 'Не указано')}")
                lines.append(f"⏱️ Сроки: {intervention.get('duration', 'Не указаны')}")
                lines.append(f"✨ Ожидаемый результат: {intervention.get('expected', 'Не указан')}")
                lines.append(f"🎚️ Уровень вмешательства: {intervention.get('city_level', 'Не указан')}")
        
        return "\n".join(lines)
    
    def get_simple_advice(self) -> str:
        """
        Возвращает простой совет для города на основе модели
        
        Returns:
            str: простой совет
        """
        if not self.key:
            return f"Для города {self.city_name} недостаточно данных для точного анализа."
        
        elem = self.key.get('element')
        
        # Советы для городов
        simple_advice = {
            1: f"Главная проблема города {self.city_name} — {elem.description[:60].lower() if elem and elem.description else 'кризис'}... Начните с декомпозиции: разбейте большую проблему на маленькие шаги.",
            2: f"Безопасность — основа. Инвестируйте в программы 'Безопасный город' и вовлекайте жителей в охрану порядка.",
            3: f"Экономика требует вливаний. Создайте условия для бизнеса, привлекайте инвесторов, поддерживайте местных предпринимателей.",
            4: f"Качество жизни — приоритет. Начните с быстрых побед: благоустройте один парк, отремонтируйте одну школу.",
            5: f"Городские мифы можно изменить. Начните публиковать истории успеха, показывайте позитивные изменения.",
            6: f"Локальная среда меняется снизу. Поддержите инициативы жителей, запустите проект 'Бюджет инициатив'.",
            7: f"Институты требуют реформы. Внедрите открытые данные, создайте понятные каналы обратной связи.",
            8: f"Работайте с регионом. Ищите союзников, участвуйте в региональных программах, лоббируйте интересы города.",
            9: f"Разрушьте главный миф. Найдите три факта, которые его опровергают, и сделайте их достоянием общественности."
        }
        
        elem_id = elem.id if elem else 1
        advice = simple_advice.get(elem_id, "Требуется комплексный анализ ситуации в городе.")
        
        # Добавляем специфику на основе метрик
        weak_vectors = self._get_weakest_vectors()
        if weak_vectors:
            advice += f"\n\n⚠️ Особое внимание уделите: {', '.join(weak_vectors[:2])}"
        
        return f"💡 **СОВЕТ ДЛЯ ГОРОДА {self.city_name.upper()}**\n\n{advice}"
    
    def _get_weakest_vectors(self) -> List[str]:
        """Возвращает список самых слабых векторов"""
        if not self.model.source_scores:
            return []
        
        weak = []
        for vector, score in self.model.source_scores.items():
            if score <= 2.5:  # уровень 2 или ниже
                vector_info = VECTORS.get(vector, {})
                weak.append(vector_info.get('name', vector))
        
        return weak
    
    def get_intervention(self) -> Optional[Dict]:
        """
        Возвращает полную интервенцию для работы с ключевым конфайнментом города
        
        Returns:
            dict: полная интервенция или None
        """
        if not self.key:
            return None
        
        return self.key.get('intervention')
    
    def get_markdown_report(self, detailed: bool = False) -> str:
        """
        Возвращает отчет, отформатированный для Telegram/мессенджеров (Markdown)
        
        Args:
            detailed: если True - детальный отчет, иначе краткий
            
        Returns:
            str: отчет в Markdown
        """
        if detailed:
            return self.get_detailed_report()
        else:
            return self.get_summary()
    
    def get_text_for_stakeholders(self) -> str:
        """
        Возвращает текст для отправки стейкхолдерам (властям, инвесторам, активистам)
        
        Returns:
            str: текст для общего доступа
        """
        lines = []
        lines.append(f"🏙️ **АНАЛИЗ ГОРОДСКОЙ СИСТЕМЫ: {self.city_name.upper()}**\n")
        
        if self.key:
            lines.append(f"🎯 **Ключевое ограничение развития:**")
            lines.append(self.key['description'])
            lines.append("")
        
        if self.loops:
            strongest = self.loop_analyzer.get_strongest_loop()
            if strongest:
                lines.append(f"🔄 **Главный системный порочный круг:**")
                lines.append(strongest['description'])
                lines.append("")
        
        # Рекомендации для действий
        if self.key and self.key.get('intervention'):
            intervention = self.key['intervention']
            lines.append(f"💡 **Приоритетное направление работы:**")
            lines.append(f"{intervention.get('approach', 'Не определено')}")
            lines.append("")
            lines.append(f"⚡ **Ключевой проект:**")
            lines.append(f"{intervention.get('exercise', 'Не определен')}")
        
        return "\n".join(lines)
    
    def get_json_report(self) -> Dict:
        """
        Возвращает отчет в виде JSON для сохранения и API
        
        Returns:
            dict: данные отчета
        """
        # Сериализуем элементы модели
        elements_json = {}
        for i, elem in self.model.elements.items():
            if elem:
                elements_json[i] = {
                    'id': elem.id,
                    'name': elem.name,
                    'description': elem.description,
                    'element_type': elem.element_type,
                    'vector': elem.vector,
                    'level': elem.level,
                    'archetype': elem.archetype,
                    'strength': elem.strength,
                    'vak': elem.vak,
                    'causes': elem.causes,
                    'caused_by': elem.caused_by,
                    'news_references': elem.news_references
                }
        
        return {
            'city_name': self.city_name,
            'city_id': self.model.city_id,
            'analysis_date': datetime.now().isoformat(),
            'vectors_scores': self.model.source_scores,
            'key_confinement': self.key,
            'loops': self.loops,
            'elements': elements_json,
            'is_closed': self.model.is_closed,
            'closure_score': self.model.closure_score if hasattr(self.model, 'closure_score') else 0,
            'city_metadata': {
                'population': self.model.population,
                'region': self.model.region,
                'city_type': self.model.city_type
            },
            'recommendations': self.get_break_points_summary()
        }
    
    def get_break_points_summary(self) -> Dict[str, Any]:
        """
        Возвращает точки разрыва петель (места для вмешательства)
        
        Returns:
            dict: точки разрыва с приоритетами
        """
        break_points = self.loop_analyzer.get_break_points() if self.loop_analyzer else []
        
        summary = {
            'total_break_points': len(break_points),
            'priority_break_points': [],
            'quick_wins': []
        }
        
        # Сортируем по влиянию
        break_points.sort(key=lambda x: x.get('impact', 0), reverse=True)
        
        for point in break_points[:5]:  # Топ-5
            summary['priority_break_points'].append({
                'description': point.get('description'),
                'loop_type': point.get('loop_type'),
                'expected_impact': point.get('impact', 0),
                'timeframe': self._estimate_timeframe(point)
            })
        
        # Добавляем быстрые победы (из ключевого конфайнмента)
        if self.key and self.key.get('element'):
            elem = self.key['element']
            if elem and elem.level and elem.level <= 2:
                summary['quick_wins'].append({
                    'action': f"Сфокусироваться на {elem.name}",
                    'expected_impact': 'Высокий',
                    'timeframe': '3-6 месяцев'
                })
        
        # Добавляем ключевое ограничение как приоритетную точку разрыва
        if self.key and self.key.get('element'):
            key_element = self.key['element']
            summary['critical_break_point'] = {
                'element_id': key_element.id if key_element else None,
                'element_name': key_element.name if key_element else None,
                'description': self.key['description'],
                'priority': 'critical',
                'intervention': self.key.get('intervention', {})
            }
        
        return summary
    
    def _estimate_timeframe(self, break_point: Dict) -> str:
        """Оценивает временные рамки для точки разрыва"""
        impact = break_point.get('impact', 0)
        
        if impact > 0.8:
            return "6-12 месяцев (долгосрочно)"
        elif impact > 0.5:
            return "3-6 месяцев (среднесрочно)"
        else:
            return "1-3 месяца (быстрая победа)"
    
    def get_recommendation_for_city(self, target_audience: str = "administration") -> str:
        """
        Возвращает персонализированную рекомендацию для разных аудиторий
        
        Args:
            target_audience: 'administration' (власть), 'business' (бизнес), 
                            'activists' (активисты), 'residents' (жители)
        
        Returns:
            str: рекомендация
        """
        if not self.key:
            return f"Для точной рекомендации для {self.city_name} нужно больше данных."
        
        elem = self.key.get('element')
        if not elem:
            return "Ключевое ограничение определено, но элемент не найден."
        
        # Рекомендации для разных аудиторий
        recommendations = {
            'administration': {
                1: f"Создайте рабочую группу по решению главной проблемы. Разбейте ее на 5-7 подзадач с конкретными сроками.",
                2: f"Запустите программу 'Безопасный город'. Начните с установки камер в проблемных районах и увеличения патрулей.",
                3: f"Создайте инвестиционный портал города. Привлекайте инвесторов через презентации и налоговые льготы.",
                4: f"Запустите проект быстрого благоустройства. Выберите 10 дворов для пилотного проекта.",
                5: f"Разработайте коммуникационную стратегию. Начните еженедельную рассылку позитивных новостей о городе.",
                6: f"Внедрите инициативное бюджетирование. Выделите 10% бюджета на проекты жителей.",
                7: f"Создайте 'Открытую мэрию' - публикуйте все решения и бюджет в открытом доступе.",
                8: f"Активизируйте работу с регионом. Создайте совместные проекты с соседними муниципалитетами.",
                9: f"Разработайте новый бренд города. Проведите серию фокус-групп и ребрендинг."
            },
            'business': {
                1: f"Объединитесь с другими предпринимателями для решения системных проблем города.",
                2: f"Инвестируйте в безопасность своих сотрудников и объектов - это повысит лояльность.",
                3: f"Создайте бизнес-ассоциацию для диалога с властью и совместных проектов.",
                4: f"Развивайте корпоративную социальную ответственность - благоустраивайте территории у офисов.",
                5: f"Станьте примером успеха - публикуйте истории развития вашего бизнеса в городе.",
                6: f"Поддерживайте локальные инициативы - спонсируйте проекты благоустройства.",
                7: f"Участвуйте в публичных слушаниях и экспертных советах при мэрии.",
                8: f"Ищите рынки за пределами города, но реинвестируйте прибыль в локальное развитие.",
                9: f"Создайте позитивный PR-кейс, который разрушит миф о безнадежности города."
            },
            'activists': {
                1: f"Объедините усилия всех активных горожан для решения главной проблемы.",
                2: f"Создайте программу 'Соседский дозор' - организуйте взаимопомощь в вопросах безопасности.",
                3: f"Запустите краудфандинговую платформу для поддержки локального бизнеса.",
                4: f"Организуйте общественные слушания по качеству жизни - соберите предложения.",
                5: f"Создайте альтернативный медиа-канал с позитивной повесткой о городе.",
                6: f"Запустите проект 'Двор, который мы хотим' - вовлекайте соседей в благоустройство.",
                7: f"Добивайтесь прозрачности через запросы информации и общественный контроль.",
                8: f"Создайте коалицию с активистами соседних городов для обмена опытом.",
                9: f"Организуйте городской фестиваль, который покажет, что город может быть классным."
            },
            'residents': {
                1: f"Не оставайтесь в стороне - ваше участие важно. Начните с малого: напишите в мэрию о проблеме.",
                2: f"Объединяйтесь с соседями. Вместе вы можете сделать свой двор безопаснее.",
                3: f"Поддерживайте местный бизнес - покупайте у локальных производителей.",
                4: f"Участвуйте в субботниках и городских мероприятиях. Это меняет город.",
                5: f"Рассказывайте друзьям о хорошем в городе. Негативные мифы можно победить.",
                6: f"Станьте инициатором проекта благоустройства - подайте заявку на инициативное бюджетирование.",
                7: f"Используйте все каналы обратной связи с властью - они работают лучше, когда активны жители.",
                8: f"Участвуйте в региональных опросах - голос города должен быть слышен.",
                9: f"Поверьте, что город может измениться. Начните с малого изменения вокруг себя."
            }
        }
        
        audience_recs = recommendations.get(target_audience, recommendations['residents'])
        elem_id = elem.id if elem else 1
        
        recommendation = audience_recs.get(elem_id, 
            f"Обратите внимание на {elem.name.lower()}. Это ключевое ограничение развития города.")
        
        # Добавляем информацию о срочности
        if self.model.is_closed and self.model.closure_score > 0.7:
            recommendation += "\n\n⚠️ КРИТИЧНО: Система сильно зациклена. Требуются срочные меры!"
        elif self.model.closure_score > 0.5:
            recommendation += "\n\n⚠️ Система начинает зацикливаться. Не откладывайте действия."
        
        audience_names = {
            'administration': 'АДМИНИСТРАЦИИ',
            'business': 'БИЗНЕС-СООБЩЕСТВА',
            'activists': 'ГОРОДСКИХ АКТИВИСТОВ',
            'residents': 'ЖИТЕЛЕЙ'
        }
        
        audience_name = audience_names.get(target_audience, 'ГОРОДА')
        
        return f"💡 **РЕКОМЕНДАЦИЯ ДЛЯ {audience_name}**\n\n{recommendation}"


# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def create_reporter_from_city_data(city_metrics: Dict, 
                                   city_name: str = None,
                                   news_articles: List[Dict] = None,
                                   city_metadata: Dict = None) -> Optional[ConfinementReporter]:
    """
    Создает репортер из метрик города
    
    Args:
        city_metrics: словарь с метриками города (СБ, ТФ, УБ, ЧВ)
        city_name: название города
        news_articles: список новостей
        city_metadata: метаданные города (население, регион и т.д.)
        
    Returns:
        ConfinementReporter или None
    """
    try:
        from confinement_model import ConfinementModel9
        
        model = ConfinementModel9(city_name=city_name)
        
        if city_metadata:
            model.population = city_metadata.get('population')
            model.region = city_metadata.get('region')
            model.city_type = city_metadata.get('city_type')
        
        model.build_from_city_data(city_metrics, news_articles, city_metadata)
        return ConfinementReporter(model, city_name)
    except Exception as e:
        logger.error(f"Ошибка при создании репортера для города {city_name}: {e}")
        return None


def format_intervention_for_display(intervention: Dict) -> str:
    """
    Форматирует интервенцию для красивого отображения
    
    Args:
        intervention: словарь с интервенцией
        
    Returns:
        str: отформатированный текст
    """
    if not intervention:
        return "Интервенция не найдена"
    
    text = f"""
💡 **ПЛАН ТРАНСФОРМАЦИИ ГОРОДА**

🎯 **Цель:** {intervention.get('target', 'Не указана')}

📌 **Подход:** {intervention.get('approach', 'Не указан')}

⚡ **Метод:** {intervention.get('method', 'Не указан')}

📋 **Ключевой проект:**
{intervention.get('exercise', 'Не указан')}

⏱️ **Сроки реализации:** {intervention.get('duration', 'Не указаны')}

🎚️ **Уровень вмешательства:** {intervention.get('city_level', 'Не указан')}
"""
    
    if 'expected' in intervention:
        text += f"\n✨ **Ожидаемый результат:**\n{intervention['expected']}"
    
    return text


def get_loop_description_by_type(loop_type: str) -> str:
    """
    Возвращает описание петли по её типу
    
    Args:
        loop_type: тип петли
        
    Returns:
        str: описание
    """
    descriptions = {
        'safety_economy_cycle': 'Петля безопасности и экономики — страх отпугивает бизнес, кризис усиливает страх',
        'quality_of_life_cycle': 'Петля качества жизни — экономические проблемы снижают качество жизни, что усугубляет экономику',
        'full_vicious_cycle': 'Полный порочный круг — все проблемы города замыкаются в самоподдерживающуюся систему',
        'institutional_cycle': 'Институциональная петля — слабые институты и негативные нарративы усиливают друг друга',
        'major_loop': 'Главная петля, которая держит всю городскую систему',
        'secondary_loop': 'Второстепенная петля, усиливающая главную',
        'compensatory_loop': 'Компенсаторная петля — попытка исправить, но только ухудшает ситуацию',
        'paradox_loop': 'Парадоксальная петля — чем больше стараешься, тем хуже становится'
    }
    return descriptions.get(loop_type, 'Рекурсивная петля в городской системе')


def compare_cities(reporters: Dict[str, ConfinementReporter]) -> str:
    """
    Сравнивает несколько городов на основе их моделей
    
    Args:
        reporters: словарь {название_города: репортер}
        
    Returns:
        str: сравнительный анализ
    """
    if not reporters:
        return "Нет данных для сравнения"
    
    lines = []
    lines.append("🏙️ **СРАВНИТЕЛЬНЫЙ АНАЛИЗ ГОРОДОВ**\n")
    
    # Сбор метрик
    city_data = []
    for name, reporter in reporters.items():
        if reporter.model and reporter.model.source_scores:
            avg_score = sum(reporter.model.source_scores.values()) / 4
            city_data.append({
                'name': name,
                'avg_score': avg_score,
                'is_closed': reporter.model.is_closed,
                'closure_score': reporter.model.closure_score,
                'key_problem': reporter.model.elements.get(1).description[:50] if reporter.model.elements.get(1) else None
            })
    
    # Сортируем по среднему баллу
    city_data.sort(key=lambda x: x['avg_score'], reverse=True)
    
    lines.append("**Рейтинг городов по интегральному показателю:**")
    for i, city in enumerate(city_data, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        status = "🔒" if city['is_closed'] else "🔓"
        lines.append(f"{medal} {city['name']} {status} — {city['avg_score']:.1f}/6")
    
    lines.append("")
    lines.append("**Детальный анализ:**")
    
    for city in city_data:
        lines.append(f"\n📍 **{city['name']}**")
        lines.append(f"  Состояние системы: {'зациклена' if city['is_closed'] else 'открыта к изменениям'}")
        lines.append(f"  Степень зацикленности: {city['closure_score']:.1%}")
        if city['key_problem']:
            lines.append(f"  Главная проблема: {city['key_problem']}...")
    
    return "\n".join(lines)


def _get_level(score: float) -> int:
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


# ============================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================

if __name__ == "__main__":
    print("🧪 Тестирование ConfinementReporter для городского контекста...")
    
    # Тестовые метрики города
    test_metrics = {
        'СБ': 2.3,  # уровень 2 - проблемы с безопасностью
        'ТФ': 2.8,  # уровень 3 - экономическая стагнация
        'УБ': 3.2,  # уровень 3 - среднее качество жизни
        'ЧВ': 2.5   # уровень 2 - социальная напряженность
    }
    
    # Тестовые новости
    test_news = [
        {
            'title': 'Рост преступности в спальных районах',
            'content': 'За месяц количество грабежей увеличилось на 15%',
            'source': 'Городские новости',
            'published_at': datetime.now()
        },
        {
            'title': 'Закрытие градообразующего предприятия',
            'content': '500 человек останутся без работы',
            'source': 'Экономика города',
            'published_at': datetime.now()
        }
    ]
    
    # Создаем репортер
    reporter = create_reporter_from_city_data(
        city_metrics=test_metrics,
        city_name="Тестовый Город",
        news_articles=test_news,
        city_metadata={'population': 500000, 'region': 'Тестовый регион', 'city_type': 'средний'}
    )
    
    if reporter:
        print("\n📋 КРАТКИЙ ОТЧЕТ:")
        print(reporter.get_summary())
        
        print("\n📋 ДЕТАЛЬНЫЙ ОТЧЕТ:")
        print(reporter.get_detailed_report())
        
        print("\n💡 СОВЕТ:")
        print(reporter.get_simple_advice())
        
        print("\n📊 ТОЧКИ РАЗРЫВА:")
        break_points = reporter.get_break_points_summary()
        for bp in break_points.get('priority_break_points', []):
            print(f"  • {bp['description']} (влияние: {bp['expected_impact']:.0%})")
        
        print("\n💡 РЕКОМЕНДАЦИЯ ДЛЯ ВЛАСТИ:")
        print(reporter.get_recommendation_for_city('administration'))
        
        print("\n💡 РЕКОМЕНДАЦИЯ ДЛЯ ЖИТЕЛЕЙ:")
        print(reporter.get_recommendation_for_city('residents'))
        
        print("\n📊 JSON ОТЧЕТ:")
        json_report = reporter.get_json_report()
        print(f"  Город: {json_report['city_name']}")
        print(f"  Зацикленность: {json_report['closure_score']:.1%}")
        print(f"  Ключевых точек разрыва: {json_report['recommendations']['total_break_points']}")
        
        print("\n✅ Тест завершен")
    else:
        print("❌ Ошибка при создании репортера")
