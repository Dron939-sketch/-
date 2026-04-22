# key_confinement.py
"""
Детектор ключевого конфайнмента (главного ограничения) для городских систем
Адаптировано для анализа городов на основе новостного контекста
"""

from typing import Dict, List, Optional, Any
from confinement_model import ConfinementModel9, ConfinementElement, VECTORS


class CityKeyConfinementDetector:
    """
    Детектор ключевого конфайнмента для города (главного ограничения развития)
    """
    
    def __init__(self, model: ConfinementModel9, loops: List[Dict[str, Any]]):
        self.model = model
        self.loops = loops
    
    def detect(self) -> Optional[Dict[str, Any]]:
        """
        Определяет ключевой конфайнмент города
        """
        # Метод 1: По центральности в графе городской системы
        centrality_scores = self._calculate_centrality()
        
        # Метод 2: По участию в порочных кругах
        loop_participation = self._calculate_loop_participation()
        
        # Метод 3: По силе влияния элемента на город
        strength_scores = {eid: elem.strength 
                          for eid, elem in self.model.elements.items() 
                          if elem}
        
        # Метод 4: По типу элемента (замыкающие важнее для города)
        type_importance = self._calculate_type_importance()
        
        # Метод 5: По городским метрикам (слабые векторы)
        city_metrics_importance = self._calculate_city_metrics_importance()
        
        # Комбинируем с весами (адаптировано для города)
        final_scores = {}
        for eid in range(1, 10):
            if not self.model.elements.get(eid):
                continue
            
            final_scores[eid] = (
                centrality_scores.get(eid, 0) * 0.25 +
                loop_participation.get(eid, 0) * 0.35 +
                strength_scores.get(eid, 0) * 0.15 +
                type_importance.get(eid, 0) * 0.15 +
                city_metrics_importance.get(eid, 0) * 0.10
            )
        
        # Находим максимум
        if not final_scores:
            return None
        
        best_eid = max(final_scores, key=final_scores.get)
        best_element = self.model.elements[best_eid]
        
        return {
            'element_id': best_eid,
            'element': best_element,
            'score': final_scores[best_eid],
            'description': self._generate_city_description(best_element),
            'intervention': self._suggest_city_intervention(best_element),
            'priority_level': self._get_priority_level(final_scores[best_eid]),
            'estimated_timeline': self._estimate_timeline(best_element),
            'stakeholders': self._identify_stakeholders(best_element)
        }
    
    def _calculate_centrality(self) -> Dict[int, float]:
        """
        Вычисляет центральность элементов в городской системе
        (насколько они важны в графе связей)
        """
        centrality = {}
        
        for eid in range(1, 10):
            element = self.model.elements.get(eid)
            if not element:
                continue
            
            # Считаем количество входящих и исходящих связей
            in_degree = len(element.caused_by)
            out_degree = len(element.causes)
            
            # В городской системе важнее элементы с большим количеством исходящих связей
            # (которые влияют на многие другие элементы)
            weighted_degree = out_degree * 1.5 + in_degree
            
            # Максимальное количество связей в городской системе ~16
            max_links = 16
            centrality[eid] = min(weighted_degree / max_links, 1.0)
        
        return centrality
    
    def _calculate_loop_participation(self) -> Dict[int, float]:
        """
        Вычисляет, насколько часто элемент участвует в порочных кругах
        """
        participation = {eid: 0 for eid in range(1, 10)}
        
        for loop in self.loops:
            # Вес петли зависит от её силы
            loop_strength = loop.get('strength', 0.5)
            
            for eid in loop.get('elements', []):
                if eid in participation:
                    participation[eid] += 1 * loop_strength
        
        # Нормализуем
        max_participation = max(participation.values()) if participation else 1
        if max_participation > 0:
            participation = {k: v / max_participation for k, v in participation.items()}
        
        return participation
    
    def _calculate_type_importance(self) -> Dict[int, float]:
        """
        Вычисляет важность на основе типа элемента для города
        """
        importance = {}
        
        # В городской системе замыкающие элементы (9) и общие нарративы (5) важнее всего
        type_weights = {
            self.model.TYPE_CLOSING: 1.0,      # элемент 9 - городской миф
            self.model.TYPE_COMMON_CAUSE: 0.95, # элемент 5 - городские нарративы
            self.model.TYPE_UPPER_CAUSE: 0.8,   # элементы 6,7,8 - системы
            self.model.TYPE_IMMEDIATE_CAUSE: 0.6, # элементы 2,3,4 - причины
            self.model.TYPE_RESULT: 0.5         # элемент 1 - главная проблема
        }
        
        for eid in range(1, 10):
            element = self.model.elements.get(eid)
            if not element:
                continue
            
            importance[eid] = type_weights.get(element.element_type, 0.5)
            
            # Дополнительный вес для элемента 9 (замыкание)
            if eid == 9:
                importance[eid] = 1.0
        
        return importance
    
    def _calculate_city_metrics_importance(self) -> Dict[int, float]:
        """
        Вычисляет важность на основе городских метрик
        """
        importance = {eid: 0.0 for eid in range(1, 10)}
        
        if not self.model.source_scores:
            return importance
        
        # Находим самые слабые векторы города
        weak_vectors = []
        for vector, score in self.model.source_scores.items():
            if score <= 2.5:  # уровень 2 или ниже
                weak_vectors.append(vector)
        
        # Сопоставляем векторы с элементами
        vector_to_elements = {
            'СБ': [2, 9],  # безопасность влияет на элемент 2 и замыкание
            'ТФ': [3, 6],  # экономика влияет на элемент 3 и локальную среду
            'УБ': [4, 1],  # качество жизни влияет на элемент 4 и проблему
            'ЧВ': [5, 7]   # соцкапитал влияет на нарративы и институты
        }
        
        for vector in weak_vectors:
            for eid in vector_to_elements.get(vector, []):
                if eid in importance:
                    importance[eid] += 0.3
        
        # Нормализуем
        max_imp = max(importance.values()) if importance else 1
        if max_imp > 0:
            importance = {k: v / max_imp for k, v in importance.items()}
        
        return importance
    
    def _generate_city_description(self, element: ConfinementElement) -> str:
        """
        Генерирует описание ключевого конфайнмента для города
        """
        base = f"**{element.name}** — главное ограничение развития города {self.model.city_name}."
        
        short_desc = element.description[:80] if element.description else "..."
        
        # Описания для разных типов элементов в городском контексте
        details = {
            1: f"Главная проблема города («{short_desc}») возвращается снова и снова, потому что вся система её воспроизводит. Это системный кризис.",
            
            2: f"Проблемы в сфере безопасности («{short_desc}») запускают цепную реакцию: страх → отток бизнеса → снижение налогов → невозможность решать проблемы безопасности.",
            
            3: f"Экономические ограничения («{short_desc}») кажутся непреодолимыми, но именно они и есть главная ловушка. Денег нет, но их не будет, пока не начнешь что-то менять.",
            
            4: f"Низкое качество жизни («{short_desc}») незаметно, но именно через него всё замыкается: людям негде отдыхать → они уезжают → экономика падает → нет денег на благоустройство.",
            
            5: f"Городской нарратив «{short_desc}» — это линза, через которую жители видят всё. Пока он доминирует, любые изменения будут встречаться с недоверием.",
            
            6: f"Состояние локальной среды («{short_desc}») создает правила, по которым живут районы. Деградация дворов и улиц запускает цепочку оттока активных жителей.",
            
            7: f"Городские институты («{short_desc}») — это корень, из которого всё растет. Неэффективное управление делает невозможными системные изменения.",
            
            8: f"Региональный контекст («{short_desc}») давит на город. Пока не наладить отношения с областью/федерацией, прорывных изменений не будет.",
            
            9: f"Городской миф «{short_desc}» — именно он не дает системе измениться. Это самосбывающееся пророчество, которое замыкает порочный круг."
        }
        
        return base + " " + details.get(element.id, "Это ключевая точка городской системы, требующая вмешательства.")
    
    def _suggest_city_intervention(self, element: ConfinementElement) -> Dict[str, str]:
        """
        Предлагает интервенцию для работы с конфайнментом города
        """
        # Библиотека интервенций для города по типам элементов
        interventions = {
            self.model.TYPE_RESULT: {
                'approach': 'Системное решение главной проблемы',
                'method': 'Стратегическая сессия с участием всех стейкхолдеров',
                'project': 'Создание проектного офиса по решению ключевой проблемы',
                'duration': '3-6 месяцев',
                'difficulty': 'Высокая',
                'city_level': 'Стратегический',
                'expected': 'Дорожная карта и первые результаты'
            },
            self.model.TYPE_IMMEDIATE_CAUSE: {
                'approach': 'Трансформация ключевых секторов',
                'method': 'Целевые программы развития',
                'project': self._get_sector_project(element.vector),
                'duration': '6-12 месяцев',
                'difficulty': 'Средняя',
                'city_level': 'Тактический',
                'expected': 'Улучшение показателей по вектору'
            },
            self.model.TYPE_COMMON_CAUSE: {
                'approach': 'Работа с городскими нарративами',
                'method': 'Коммуникационная стратегия и медиа-кампания',
                'project': 'Кампания «Новый город» с серией позитивных кейсов',
                'duration': '6-9 месяцев',
                'difficulty': 'Средняя',
                'city_level': 'Коммуникационный',
                'expected': 'Изменение восприятия города'
            },
            self.model.TYPE_UPPER_CAUSE: {
                'approach': 'Институциональная трансформация',
                'method': 'Реформа управления и цифровизация',
                'project': self._get_institutional_project(element.id),
                'duration': '12-24 месяца',
                'difficulty': 'Высокая',
                'city_level': 'Системный',
                'expected': 'Повышение эффективности управления'
            },
            self.model.TYPE_CLOSING: {
                'approach': 'Трансформация городской идентичности',
                'method': 'Ребрендинг и создание новой городской мифологии',
                'project': 'Разработка и внедрение нового бренда города',
                'duration': '12-24 месяца',
                'difficulty': 'Очень высокая',
                'city_level': 'Трансформационный',
                'expected': 'Новая городская идентичность'
            }
        }
        
        intervention = interventions.get(element.element_type, 
                                        interventions[self.model.TYPE_COMMON_CAUSE])
        
        # Персонализируем под элемент и город
        intervention = intervention.copy()
        intervention['target'] = element.name
        intervention['element_id'] = element.id
        intervention['vector'] = element.vector
        intervention['level'] = element.level
        intervention['city_name'] = self.model.city_name
        
        # Добавляем конкретные KPI
        intervention['kpis'] = self._get_kpis_for_element(element)
        
        # Добавляем быстрые победы
        intervention['quick_wins'] = self._get_quick_wins_for_element(element)
        
        # Адаптируем под вектор города
        if element.vector and element.vector in VECTORS:
            vector_info = VECTORS[element.vector]
            intervention['personalized'] = f"Учитывая, что {vector_info['name'].lower()} — проблемная зона города, начните с..."
        
        return intervention
    
    def _get_sector_project(self, vector: Optional[str]) -> str:
        """Возвращает проект для конкретного сектора"""
        projects = {
            'СБ': 'Программа «Безопасный город»: установка камер, увеличение патрулей, освещение',
            'ТФ': 'Создание инвестиционного портала и поддержка МСП через гранты',
            'УБ': 'Благоустройство общественных пространств: парки, набережные, скверы',
            'ЧВ': 'Программа развития ТОС и поддержки соседских сообществ'
        }
        return projects.get(vector, 'Комплексная программа развития сектора')
    
    def _get_institutional_project(self, element_id: int) -> str:
        """Возвращает институциональный проект для элемента"""
        projects = {
            6: 'Программа «Комфортная среда»: благоустройство дворов и общественных пространств',
            7: 'Цифровая трансформация: внедрение открытых данных и электронных услуг',
            8: 'Программа межмуниципального сотрудничества и лоббирования интересов города'
        }
        return projects.get(element_id, 'Институциональная реформа и оптимизация процессов')
    
    def _get_kpis_for_element(self, element: ConfinementElement) -> List[str]:
        """Возвращает KPI для отслеживания прогресса"""
        kpis = {
            1: [
                'Снижение остроты главной проблемы (опросы)',
                'Количество реализованных решений',
                'Удовлетворенность жителей динамикой'
            ],
            2: [
                'Снижение уровня преступности на X%',
                'Рост индекса безопасности (опросы)',
                'Количество освещенных улиц'
            ],
            3: [
                'Рост бюджета города на X%',
                'Количество новых рабочих мест',
                'Объем привлеченных инвестиций'
            ],
            4: [
                'Рост удовлетворенности качеством жизни на X%',
                'Количество благоустроенных пространств',
                'Снижение оттока населения'
            ],
            5: [
                'Изменение тональности городских медиа',
                'Рост позитивных упоминаний города',
                'Уровень городской гордости'
            ],
            6: [
                'Количество реализованных проектов ТОС',
                'Удовлетворенность жителей районом',
                'Активность соседских сообществ'
            ],
            7: [
                'Время предоставления услуг',
                'Индекс прозрачности власти',
                'Доверие к администрации (опросы)'
            ],
            8: [
                'Объем межбюджетных трансфертов',
                'Количество совместных проектов с регионом',
                'Представительство города в региональных органах'
            ],
            9: [
                'Изменение ключевых городских нарративов',
                'Рост позитивных ожиданий жителей',
                'Успешность нового бренда города'
            ]
        }
        return kpis.get(element.id, ['Комплексная оценка эффективности'])
    
    def _get_quick_wins_for_element(self, element: ConfinementElement) -> List[str]:
        """Возвращает быстрые победы для элемента"""
        quick_wins = {
            1: [
                'Создать рабочую группу по проблеме',
                'Провести опрос жителей для уточнения проблемы',
                'Определить 3 быстрых решения'
            ],
            2: [
                'Установить освещение в 5 самых темных местах',
                'Запустить чат-бот для сообщений о ЧП',
                'Провести встречи с жителями по безопасности'
            ],
            3: [
                'Создать инвестиционный портал за 2 недели',
                'Провести встречу с топ-20 предпринимателями',
                'Запустить горячую линию для бизнеса'
            ],
            4: [
                'Благоустроить один двор за месяц',
                'Провести субботник в парке',
                'Установить 10 скамеек в центре'
            ],
            5: [
                'Запустить рубрику «Хорошие новости» в соцсетях',
                'Найти 5 позитивных историй о городе',
                'Провести городской фестиваль'
            ],
            6: [
                'Выбрать 3 пилотных двора для благоустройства',
                'Создать чаты домов/районов',
                'Провести конкурс «Лучший подъезд»'
            ],
            7: [
                'Опубликовать открытый бюджет города',
                'Запустить форму обратной связи на сайте',
                'Провести день открытых дверей в администрации'
            ],
            8: [
                'Инициировать встречу глав соседних городов',
                'Подготовить пакет предложений в регион',
                'Создать рабочую группу по межмуниципальным связям'
            ],
            9: [
                'Найти 3 факта, опровергающих главный миф',
                'Запустить кампанию с новыми историями',
                'Пригласить блогеров показать реальный город'
            ]
        }
        return quick_wins.get(element.id, ['Провести диагностику ситуации'])
    
    def _get_priority_level(self, score: float) -> str:
        """Определяет уровень приоритета"""
        if score >= 0.8:
            return "КРИТИЧЕСКИЙ"
        elif score >= 0.6:
            return "ВЫСОКИЙ"
        elif score >= 0.4:
            return "СРЕДНИЙ"
        else:
            return "НИЗКИЙ"
    
    def _estimate_timeline(self, element: ConfinementElement) -> Dict[str, str]:
        """Оценивает временные рамки для разных этапов"""
        timelines = {
            1: {'quick': '1-2 месяца', 'medium': '6 месяцев', 'full': '1-2 года'},
            2: {'quick': '1 месяц', 'medium': '6 месяцев', 'full': '1 год'},
            3: {'quick': '3 месяца', 'medium': '1 год', 'full': '2-3 года'},
            4: {'quick': '1-2 месяца', 'medium': '6-9 месяцев', 'full': '1.5 года'},
            5: {'quick': '2-3 месяца', 'medium': '6-9 месяцев', 'full': '1-1.5 года'},
            6: {'quick': '1 месяц', 'medium': '6 месяцев', 'full': '1 год'},
            7: {'quick': '3-4 месяца', 'medium': '1 год', 'full': '2 года'},
            8: {'quick': '3-6 месяцев', 'medium': '1-1.5 года', 'full': '2-3 года'},
            9: {'quick': '6 месяцев', 'medium': '1-1.5 года', 'full': '2-3 года'}
        }
        return timelines.get(element.id, {'quick': '3 месяца', 'medium': '1 год', 'full': '2 года'})
    
    def _identify_stakeholders(self, element: ConfinementElement) -> List[str]:
        """Определяет ключевых стейкхолдеров для работы с элементом"""
        stakeholders = {
            1: ['Администрация города', 'Эксперты', 'Активные жители'],
            2: ['Полиция', 'МЧС', 'Жители проблемных районов', 'Депутаты'],
            3: ['Предприниматели', 'Инвесторы', 'Экономический блок администрации'],
            4: ['Жители', 'Управляющие компании', 'Архитекторы', 'Экологи'],
            5: ['СМИ', 'Блогеры', 'Лидеры мнений', 'PR-отдел'],
            6: ['ТОСы', 'Старшие по домам', 'Управляющие компании'],
            7: ['Глава города', 'Депутаты', 'Профильные комитеты'],
            8: ['Губернатор', 'Правительство области', 'Соседние города'],
            9: ['Маркетологи', 'Бренд-менеджеры', 'Туристический бизнес']
        }
        return stakeholders.get(element.id, ['Все заинтересованные стороны'])
    
    def get_intervention_priority(self) -> List[Dict[str, Any]]:
        """
        Возвращает список интервенций в порядке приоритета
        """
        # Собираем все интервенции с оценками
        interventions = []
        
        for eid in range(1, 10):
            element = self.model.elements.get(eid)
            if not element:
                continue
            
            # Оцениваем важность
            score = (
                self._calculate_centrality().get(eid, 0) * 0.25 +
                self._calculate_loop_participation().get(eid, 0) * 0.35 +
                self._calculate_city_metrics_importance().get(eid, 0) * 0.40
            )
            
            interventions.append({
                'element_id': eid,
                'element_name': element.name,
                'priority_score': score,
                'priority_level': self._get_priority_level(score),
                'quick_win': self._get_quick_wins_for_element(element)[0] if self._get_quick_wins_for_element(element) else None,
                'estimated_time': self._estimate_timeline(element)['quick']
            })
        
        # Сортируем по убыванию приоритета
        interventions.sort(key=lambda x: x['priority_score'], reverse=True)
        
        return interventions


# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def format_city_key_confinement(key_confinement: Dict[str, Any]) -> str:
    """
    Форматирует ключевой конфайнмент для отображения
    
    Args:
        key_confinement: словарь с ключевым конфайнментом
        
    Returns:
        отформатированный текст
    """
    if not key_confinement:
        return "Ключевое ограничение не определено"
    
    text = f"""
⛓ **КЛЮЧЕВОЕ ОГРАНИЧЕНИЕ РАЗВИТИЯ**

{key_confinement.get('description', 'Нет описания')}

📊 **Приоритет:** {key_confinement.get('priority_level', 'Не определен')}
🎯 **Элемент:** {key_confinement.get('element_id', '?')}
📈 **Оценка важности:** {key_confinement.get('score', 0):.1%}

**⏱️ Временные рамки:**
• Быстрые победы: {key_confinement.get('estimated_timeline', {}).get('quick', 'Н/Д')}
• Среднесрочно: {key_confinement.get('estimated_timeline', {}).get('medium', 'Н/Д')}
• Полная трансформация: {key_confinement.get('estimated_timeline', {}).get('full', 'Н/Д')}

**👥 Ключевые стейкхолдеры:**
{', '.join(key_confinement.get('stakeholders', ['Не определены']))}
"""
    
    intervention = key_confinement.get('intervention', {})
    if intervention:
        text += f"""

💡 **РЕКОМЕНДУЕМАЯ ИНТЕРВЕНЦИЯ:**

**Подход:** {intervention.get('approach', 'Н/Д')}
**Метод:** {intervention.get('method', 'Н/Д')}
**Проект:** {intervention.get('project', 'Н/Д')}
**Сроки:** {intervention.get('duration', 'Н/Д')}
**Уровень:** {intervention.get('city_level', 'Н/Д')}

**🎯 Ключевые KPI для отслеживания:**
{chr(10).join(f'• {kpi}' for kpi in intervention.get('kpis', ['Нет данных']))}

**⚡ Быстрые победы (первые шаги):**
{chr(10).join(f'• {win}' for win in intervention.get('quick_wins', ['Нет данных']))}
"""
    
    return text


def get_intervention_roadmap(interventions_priority: List[Dict[str, Any]]) -> str:
    """
    Формирует дорожную карту интервенций
    
    Args:
        interventions_priority: список интервенций с приоритетами
        
    Returns:
        дорожная карта в виде текста
    """
    if not interventions_priority:
        return "Нет данных для формирования дорожной карты"
    
    lines = []
    lines.append("🗺️ **ДОРОЖНАЯ КАРТА ИНТЕРВЕНЦИЙ**\n")
    
    # Группируем по приоритету
    critical = [i for i in interventions_priority if i['priority_level'] == 'КРИТИЧЕСКИЙ']
    high = [i for i in interventions_priority if i['priority_level'] == 'ВЫСОКИЙ']
    medium = [i for i in interventions_priority if i['priority_level'] == 'СРЕДНИЙ']
    
    if critical:
        lines.append("🔴 **КРИТИЧЕСКИЙ ПРИОРИТЕТ (неотложные меры):**")
        for item in critical[:3]:
            lines.append(f"  • Элемент {item['element_id']}: {item['element_name']}")
            lines.append(f"    → Быстрая победа: {item.get('quick_win', 'Нет')}")
            lines.append(f"    → Срок: {item.get('estimated_time', 'Н/Д')}")
        lines.append("")
    
    if high:
        lines.append("🟠 **ВЫСОКИЙ ПРИОРИТЕТ (ближайший квартал):**")
        for item in high[:3]:
            lines.append(f"  • Элемент {item['element_id']}: {item['element_name']}")
        lines.append("")
    
    if medium:
        lines.append("🟡 **СРЕДНИЙ ПРИОРИТЕТ (плановые работы):**")
        for item in medium[:3]:
            lines.append(f"  • Элемент {item['element_id']}: {item['element_name']}")
    
    return "\n".join(lines)


# ============================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================

if __name__ == "__main__":
    print("🧪 Тестирование CityKeyConfinementDetector...")
    
    # Создаем тестовую модель города
    from confinement_model import ConfinementModel9
    
    test_model = ConfinementModel9(city_name="Тестовый Город", city_id=123)
    
    # Заполняем тестовыми данными
    test_metrics = {'СБ': 2.3, 'ТФ': 2.8, 'УБ': 3.2, 'ЧВ': 2.5}
    test_model.build_from_city_data(test_metrics, [])
    
    # Тестовые петли
    test_loops = [
        {
            'type': 'safety_economy_cycle',
            'description': 'Петля безопасности и экономики',
            'elements': [1, 2, 3],
            'strength': 0.8
        }
    ]
    
    # Создаем детектор
    detector = CityKeyConfinementDetector(test_model, test_loops)
    
    # Определяем ключевой конфайнмент
    key = detector.detect()
    
    if key:
        print("\n📋 КЛЮЧЕВОЙ КОНФАЙНМЕНТ:")
        print(format_city_key_confinement(key))
        
        print("\n📊 ПРИОРИТЕТЫ ИНТЕРВЕНЦИЙ:")
        priorities = detector.get_intervention_priority()
        for p in priorities[:3]:
            print(f"  {p['element_id']}. {p['element_name']} — {p['priority_level']} ({p['priority_score']:.1%})")
        
        print("\n🗺️ ДОРОЖНАЯ КАРТА:")
        print(get_intervention_roadmap(priorities))
    else:
        print("❌ Не удалось определить ключевой конфайнмент")
    
    print("\n✅ Тест завершен")
