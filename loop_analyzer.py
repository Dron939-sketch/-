#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 2: АНАЛИЗ ПЕТЕЛЬ ДЛЯ ГОРОДСКИХ СИСТЕМ (loop_analyzer.py)
Анализирует рекурсивные петли в конфайнтмент-модели города
Адаптировано для городского планирования и управления развитием
"""

from typing import List, Dict, Optional, Any, Set, Tuple
from datetime import datetime
import logging

from confinement_model import ConfinementModel9, ConfinementElement, VECTORS

# Настройка логирования
logger = logging.getLogger(__name__)


class CityLoopAnalyzer:
    """
    Анализирует рекурсивные петли (порочные круги) в городской системе
    """
    
    # Константы для типов городских петель
    LOOP_TYPE_FULL_VICIOUS = 'full_vicious_cycle'      # Полный порочный круг
    LOOP_TYPE_SAFETY_ECONOMY = 'safety_economy_cycle'  # Безопасность-экономика
    LOOP_TYPE_QUALITY_LIFE = 'quality_life_cycle'      # Качество жизни
    LOOP_TYPE_INSTITUTIONAL = 'institutional_cycle'    # Институциональная петля
    LOOP_TYPE_SOCIAL = 'social_cycle'                  # Социальная изоляция
    LOOP_TYPE_MINOR = 'minor_cycle'                    # Второстепенная
    
    # Описания типов городских петель
    LOOP_DESCRIPTIONS = {
        LOOP_TYPE_FULL_VICIOUS: {
            'name': 'Полный порочный круг',
            'description': '🔴 Полный порочный круг развития: проблемы → страхи → экономика → качество жизни → мифы → замыкание',
            'emoji': '🔴',
            'color': 'red',
            'advice': 'Это критическая системная ловушка. Требуется комплексное вмешательство и разрыв ключевого мифа.',
            'strategic_priority': 'КРИТИЧЕСКИЙ'
        },
        LOOP_TYPE_SAFETY_ECONOMY: {
            'name': 'Петля безопасности и экономики',
            'description': '🟠 Петля безопасности-экономики: страх → отток бизнеса → безработица → рост преступности',
            'emoji': '🟠',
            'color': 'orange',
            'advice': 'Начните с быстрых побед в безопасности: освещение, камеры, патрулирование.',
            'strategic_priority': 'ВЫСОКИЙ'
        },
        LOOP_TYPE_QUALITY_LIFE: {
            'name': 'Петля качества жизни',
            'description': '🟡 Петля качества жизни: низкий комфорт → отток активных жителей → снижение налогов → ухудшение среды',
            'emoji': '🟡',
            'color': 'yellow',
            'advice': 'Создайте общественные пространства. Быстрые победы в благоустройстве дадут импульс.',
            'strategic_priority': 'ВЫСОКИЙ'
        },
        LOOP_TYPE_INSTITUTIONAL: {
            'name': 'Институциональная петля',
            'description': '🔵 Институциональная петля: недоверие → низкая активность → неэффективные институты → падение доверия',
            'emoji': '🔵',
            'color': 'blue',
            'advice': 'Начните с малого: опубликуйте открытые данные, запустите обратную связь.',
            'strategic_priority': 'СРЕДНИЙ'
        },
        LOOP_TYPE_SOCIAL: {
            'name': 'Петля социальной изоляции',
            'description': '🟣 Социальная изоляция: нет мест встреч → нет сообществ → нет проектов → ухудшение среды',
            'emoji': '🟣',
            'color': 'purple',
            'advice': 'Создайте точки притяжения: коворкинги, соседские центры, дворовые праздники.',
            'strategic_priority': 'СРЕДНИЙ'
        },
        LOOP_TYPE_MINOR: {
            'name': 'Второстепенная петля',
            'description': '⚪ Второстепенная городская петля',
            'emoji': '⚪',
            'color': 'gray',
            'advice': 'Менее значимая, но тоже влияет на систему. Обратите внимание позже.',
            'strategic_priority': 'НИЗКИЙ'
        }
    }
    
    def __init__(self, model: ConfinementModel9):
        """
        Инициализация анализатора
        
        Args:
            model: построенная конфайнт-модель города
        """
        self.model = model
        self._visited: Set[int] = set()
        self._path: List[int] = []
        self._analysis_time: Optional[datetime] = None
        self.significant_loops: List[Dict[str, Any]] = []
        
        logger.info(f"CityLoopAnalyzer инициализирован для города {self.model.city_name}")
    
    def analyze(self) -> List[Dict[str, Any]]:
        """
        Главный метод анализа - возвращает все значимые городские петли
        
        Returns:
            list: список найденных петель с характеристиками
        """
        if not self.model or not hasattr(self.model, 'elements'):
            logger.error("❌ Модель города не инициализирована или не содержит elements")
            return []
        
        logger.info(f"Начинаю анализ петель для города {self.model.city_name}...")
        self.significant_loops = []
        self._analysis_time = datetime.now()
        
        self._find_all_cycles()
        self._rank_loops_by_impact()
        self._describe_city_loops()
        self._filter_insignificant_loops()
        self._add_city_context()
        
        logger.info(f"Анализ завершен. Найдено {len(self.significant_loops)} петель")
        return self.significant_loops.copy()
    
    def _find_all_cycles(self):
        """Находит все циклы в графе городской системы"""
        for start_id in list(self.model.elements.keys()):
            self._visited.clear()
            self._path.clear()
            self._dfs(start_id, 0)
    
    def _dfs(self, node_id: int, depth: int):
        """
        Поиск в глубину для нахождения циклов
        
        Args:
            node_id: текущий узел
            depth: глубина поиска
        """
        if node_id in self._path:
            cycle_start = self._path.index(node_id)
            cycle = self._path[cycle_start:] + [node_id]
            if len(cycle) >= 3:
                self._add_unique_cycle(cycle)
            return
        
        if node_id in self._visited or node_id not in self.model.elements:
            return
        
        element = self.model.elements.get(node_id)
        if not element:
            return
        
        self._visited.add(node_id)
        self._path.append(node_id)
        
        if hasattr(element, 'causes') and element.causes:
            for next_id in element.causes:
                if next_id in self.model.elements:
                    self._dfs(next_id, depth + 1)
        
        self._path.pop()
    
    def _add_unique_cycle(self, cycle: List[int]):
        """Добавляет уникальный цикл в список"""
        cycle_set = set(cycle)
        for existing in self.significant_loops:
            if set(existing['cycle']) == cycle_set:
                if len(existing['cycle']) == len(cycle):
                    return
        self.significant_loops.append({
            'cycle': cycle.copy(),
            'length': len(cycle),
            'raw_strength': self._calculate_raw_strength(cycle),
            'elements': [self.model.elements[eid] for eid in cycle if eid in self.model.elements]
        })
    
    def _calculate_raw_strength(self, cycle: List[int]) -> float:
        """
        Вычисляет сырую силу цикла
        
        Args:
            cycle: список ID элементов в цикле
            
        Returns:
            float: сила цикла от 0 до 1
        """
        if not cycle:
            return 0.0
        
        strength = 1.0
        n = len(cycle)
        
        for i in range(n):
            from_id = cycle[i]
            to_id = cycle[(i + 1) % n]
            
            found = False
            for link in getattr(self.model, 'links', []):
                if link.get('from') == from_id and link.get('to') == to_id:
                    strength *= link.get('strength', 0.5)
                    found = True
                    break
            
            if not found:
                strength *= 0.3
        
        return min(strength, 1.0)
    
    def _rank_loops_by_impact(self):
        """Ранжирует городские петли по силе и длине"""
        for loop in self.significant_loops:
            length_factor = loop['length'] / 9.0
            strength = loop['raw_strength']
            
            # В городских системах длинные петли (охватывающие много элементов) критичнее
            loop['impact'] = length_factor * strength * (1 + length_factor)
    
    def _describe_city_loops(self):
        """Добавляет человеко-читаемые описания городских петель"""
        for loop in self.significant_loops:
            elements = loop['cycle']
            
            # Определяем тип городской петли по составу элементов
            has_full = all(e in elements for e in [1, 2, 3, 4, 9]) or all(e in elements for e in [1, 2, 3, 4, 5, 9])
            has_safety_economy = 2 in elements and 3 in elements and (1 in elements or 5 in elements)
            has_quality_life = 4 in elements and 3 in elements and (1 in elements or 6 in elements)
            has_institutional = 7 in elements and 5 in elements and (6 in elements or 8 in elements)
            has_social = 4 in elements and 5 in elements and 7 in elements
            
            if has_full:
                loop['type'] = self.LOOP_TYPE_FULL_VICIOUS
            elif has_safety_economy:
                loop['type'] = self.LOOP_TYPE_SAFETY_ECONOMY
            elif has_quality_life:
                loop['type'] = self.LOOP_TYPE_QUALITY_LIFE
            elif has_institutional:
                loop['type'] = self.LOOP_TYPE_INSTITUTIONAL
            elif has_social:
                loop['type'] = self.LOOP_TYPE_SOCIAL
            else:
                loop['type'] = self.LOOP_TYPE_MINOR
            
            type_info = self.LOOP_DESCRIPTIONS.get(loop['type'], self.LOOP_DESCRIPTIONS[self.LOOP_TYPE_MINOR])
            loop['description'] = type_info['description']
            loop['color'] = type_info['color']
            loop['type_name'] = type_info['name']
            loop['advice'] = type_info['advice']
            loop['strategic_priority'] = type_info['strategic_priority']
    
    def _filter_insignificant_loops(self, threshold: float = 0.15):
        """Удаляет незначительные петли"""
        self.significant_loops = [l for l in self.significant_loops if l.get('impact', 0) >= threshold]
    
    def _add_city_context(self):
        """Добавляет городской контекст к петлям"""
        for loop in self.significant_loops:
            loop['city_name'] = self.model.city_name
            
            # Добавляем временные рамки для разрыва
            impact = loop.get('impact', 0)
            if impact > 0.7:
                loop['break_timeline'] = '12-24 месяца'
                loop['effort_required'] = 'Очень высокий'
            elif impact > 0.4:
                loop['break_timeline'] = '6-12 месяцев'
                loop['effort_required'] = 'Высокий'
            else:
                loop['break_timeline'] = '3-6 месяцев'
                loop['effort_required'] = 'Средний'
            
            # Добавляем рекомендованные ресурсы
            loop['recommended_resources'] = self._get_resources_for_loop(loop['type'])
    
    def _get_resources_for_loop(self, loop_type: str) -> List[str]:
        """Возвращает рекомендованные ресурсы для разрыва петли"""
        resources = {
            self.LOOP_TYPE_FULL_VICIOUS: [
                'Стратегическая сессия с экспертами',
                'Внешний консалтинг',
                'Бюджет на ребрендинг',
                'Медиа-кампания'
            ],
            self.LOOP_TYPE_SAFETY_ECONOMY: [
                'Инвестиции в безопасность',
                'Программа поддержки МСП',
                'Консультанты по экономике',
                'Оборудование для видеонаблюдения'
            ],
            self.LOOP_TYPE_QUALITY_LIFE: [
                'Бюджет на благоустройство',
                'Архитектурное бюро',
                'Опросы жителей',
                'Проектные офисы'
            ],
            self.LOOP_TYPE_INSTITUTIONAL: [
                'IT-специалисты для цифровизации',
                'Юристы для регламентов',
                'Тренинги для сотрудников',
                'Платформа обратной связи'
            ],
            self.LOOP_TYPE_SOCIAL: [
                'Помещения под соседские центры',
                'Гранты для НКО',
                'Модераторы сообществ',
                'Событийный менеджмент'
            ]
        }
        return resources.get(loop_type, ['Анализ ситуации', 'Консультации экспертов'])
    
    def get_strongest_loop(self) -> Optional[Dict[str, Any]]:
        """Возвращает самую сильную петлю (главный порочный круг)"""
        if not self.significant_loops:
            return None
        return max(self.significant_loops, key=lambda x: x.get('impact', 0))
    
    def get_weakest_loop(self) -> Optional[Dict[str, Any]]:
        """Возвращает самую слабую петлю"""
        if not self.significant_loops:
            return None
        return min(self.significant_loops, key=lambda x: x.get('impact', 0))
    
    def get_loops_by_type(self, loop_type: str) -> List[Dict[str, Any]]:
        """Возвращает петли определенного типа"""
        if not self.significant_loops:
            return []
        return [l for l in self.significant_loops if l.get('type') == loop_type]
    
    def get_loops_by_element(self, element_id: int) -> List[Dict[str, Any]]:
        """Возвращает все петли, содержащие указанный элемент"""
        if not self.significant_loops:
            return []
        return [l for l in self.significant_loops if element_id in l.get('cycle', [])]
    
    def get_critical_elements(self) -> List[Dict[str, Any]]:
        """
        Определяет критические элементы города (участвуют в многих петлях)
        """
        element_participation = {eid: 0 for eid in range(1, 10)}
        
        for loop in self.significant_loops:
            for eid in loop.get('cycle', []):
                if eid in element_participation:
                    element_participation[eid] += loop.get('impact', 0.5)
        
        critical = []
        for eid, score in element_participation.items():
            if score > 0:
                elem = self.model.elements.get(eid)
                if elem:
                    critical.append({
                        'element_id': eid,
                        'element_name': elem.name,
                        'participation_score': score,
                        'criticality': 'КРИТИЧЕСКИЙ' if score > 2 else 'ВЫСОКИЙ' if score > 1 else 'СРЕДНИЙ'
                    })
        
        return sorted(critical, key=lambda x: x['participation_score'], reverse=True)
    
    def get_intervention_points(self, loop: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Определяет точки разрыва городской петли"""
        elements = loop.get('cycle', [])
        intervention_points = []
        
        for elem_id in elements:
            elem = self.model.elements.get(elem_id)
            if not elem:
                continue
            
            changeability = self._calculate_changeability_for_city(elem)
            
            intervention_points.append({
                'element_id': elem_id,
                'element': elem,
                'element_name': elem.name,
                'element_type': getattr(elem, 'element_type', 'unknown'),
                'impact': getattr(elem, 'strength', 0.5) * changeability,
                'difficulty': 1 - changeability,
                'changeability': changeability,
                'quick_win_potential': changeability > 0.6,
                'description': getattr(elem, 'description', '')[:100]
            })
        
        return sorted(intervention_points, key=lambda x: x['impact'], reverse=True)
    
    def _calculate_changeability_for_city(self, element) -> float:
        """Вычисляет, насколько легко изменить элемент в городской системе"""
        elem_type = getattr(element, 'element_type', '')
        elem_id = getattr(element, 'id', 0)
        
        # В городе локальные и поведенческие элементы легче менять
        if elem_id in [2, 3, 4, 6]:  # безопасность, экономика, качество жизни, среда
            return 0.7
        elif elem_type in ['common_cause', 'closing']:  # нарративы и мифы
            return 0.3
        elif elem_type == 'upper_cause':  # институты и регион
            return 0.4
        elif elem_type == 'result':  # главная проблема
            return 0.5
        return 0.4
    
    def get_best_intervention_point(self, loop: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Возвращает лучшую точку для вмешательства"""
        points = self.get_intervention_points(loop)
        return points[0] if points else None
    
    def get_break_points_summary(self) -> str:
        """Возвращает краткое резюме по точкам разрыва"""
        strongest = self.get_strongest_loop()
        if not strongest:
            return "✨ В городской системе не обнаружено значительных порочных кругов."
        
        points = self.get_intervention_points(strongest)
        if not points:
            return "⚡ Петля обнаружена, но точки вмешательства не определены."
        
        best = points[0]
        
        if best['difficulty'] < 0.3:
            difficulty_text = "🟢 Легко изменить (быстрая победа)"
            timeline = "1-3 месяца"
        elif best['difficulty'] < 0.6:
            difficulty_text = "🟡 Средняя сложность"
            timeline = "3-6 месяцев"
        else:
            difficulty_text = "🔴 Сложно изменить (требуется стратегия)"
            timeline = "6-12 месяцев"
        
        return (f"🎯 *Лучшая точка вмешательства для города {self.model.city_name}*\n\n"
                f"📝 *{best['element_name']}*\n"
                f"{best['description']}\n\n"
                f"📊 Потенциал изменения: {best['impact']:.0%}\n"
                f"{difficulty_text}\n"
                f"⏱️ Временные рамки: {timeline}\n\n"
                f"💡 *Совет:* {strongest.get('advice', 'Начните с этого элемента.')}")
    
    def get_loop_description_for_stakeholders(self, loop: Dict[str, Any], audience: str = 'administration') -> str:
        """
        Возвращает понятное описание петли для разных аудиторий
        
        Args:
            loop: петля
            audience: 'administration', 'business', 'activists', 'residents'
        """
        elements = []
        for elem_id in loop['cycle']:
            elem = self.model.elements.get(elem_id)
            if elem:
                elements.append(elem.name)
        
        elements_str = " → ".join(elements)
        
        impact = loop.get('impact', 0)
        if impact > 0.7:
            strength_word = "🔴 КРИТИЧЕСКАЯ"
        elif impact > 0.4:
            strength_word = "🟠 ВЫСОКАЯ"
        elif impact > 0.2:
            strength_word = "🟡 СРЕДНЯЯ"
        else:
            strength_word = "🟢 НИЗКАЯ"
        
        audience_intros = {
            'administration': f"Уважаемые коллеги! В городе {self.model.city_name} обнаружен следующий порочный круг:",
            'business': f"Уважаемые предприниматели! В городе {self.model.city_name} существует системная проблема:",
            'activists': f"Друзья! Мы обнаружили ключевой механизм, который тормозит развитие города:",
            'residents': f"Уважаемые жители! В нашем городе есть замкнутый круг проблем:"
        }
        
        intro = audience_intros.get(audience, f"В городе {self.model.city_name}:")
        
        return (f"{intro}\n\n"
                f"{loop['description']}\n\n"
                f"{strength_word} (сила влияния {impact:.0%})\n"
                f"🔄 *Цепочка:* {elements_str}\n\n"
                f"💡 *Что делать:* {loop.get('advice', 'Требуется анализ')}")
    
    def get_all_loops_summary(self) -> str:
        """Возвращает сводку по всем петлям"""
        if not self.significant_loops:
            return "✅ В городской системе не обнаружено порочных кругов."
        
        lines = [f"🔄 *ПОРОЧНЫЕ КРУГИ ГОРОДА {self.model.city_name.upper()}*\n"]
        
        for i, loop in enumerate(self.significant_loops[:5], 1):
            impact = loop.get('impact', 0)
            bar = "█" * int(impact * 10) + "░" * (10 - int(impact * 10))
            priority = loop.get('strategic_priority', 'Н/Д')
            
            lines.append(f"{i}. {loop['description']}")
            lines.append(f"   {bar} {impact:.0%} | Приоритет: {priority}")
            lines.append(f"   💡 {loop.get('advice', '')[:60]}...")
            lines.append("")
        
        if len(self.significant_loops) > 5:
            lines.append(f"...и еще {len(self.significant_loops) - 5} петель")
        
        return "\n".join(lines)
    
    def get_strategic_recommendations(self) -> List[Dict[str, Any]]:
        """
        Возвращает стратегические рекомендации на основе анализа петель
        """
        recommendations = []
        
        for loop in self.significant_loops:
            if loop.get('strategic_priority') in ['КРИТИЧЕСКИЙ', 'ВЫСОКИЙ']:
                best_point = self.get_best_intervention_point(loop)
                if best_point:
                    recommendations.append({
                        'loop_type': loop['type'],
                        'loop_description': loop['description'],
                        'priority': loop['strategic_priority'],
                        'impact': loop['impact'],
                        'key_intervention': best_point['element_name'],
                        'intervention_description': best_point['description'],
                        'timeline': loop.get('break_timeline', 'Не определен'),
                        'resources': loop.get('recommended_resources', [])
                    })
        
        return sorted(recommendations, key=lambda x: x['impact'], reverse=True)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику по анализу"""
        return {
            'city_name': self.model.city_name,
            'total_loops': len(self.significant_loops),
            'strongest_impact': self.get_strongest_loop().get('impact', 0) if self.significant_loops else 0,
            'loops_by_type': {
                loop_type: len(self.get_loops_by_type(loop_type))
                for loop_type in self.LOOP_DESCRIPTIONS.keys()
            },
            'critical_elements': self.get_critical_elements(),
            'analysis_time': self._analysis_time.isoformat() if self._analysis_time else None
        }
    
    def visualize_loop(self, loop: Dict[str, Any]) -> str:
        """
        Возвращает текстовое представление петли для отображения
        
        Returns:
            str: ASCII-схема петли
        """
        elements = loop.get('cycle', [])
        if not elements:
            return "Петля не содержит элементов"
        
        lines = []
        lines.append("┌" + "─" * 60 + "┐")
        lines.append("│ " + loop['description'] + " │")
        lines.append("└" + "─" * 60 + "┘")
        lines.append("")
        
        # Цепочка элементов
        chain = []
        for elem_id in elements:
            elem = self.model.elements.get(elem_id)
            name = getattr(elem, 'name', f'Элемент {elem_id}')[:25]
            chain.append(name)
        
        lines.append("🔄 " + " → ".join(chain) + " →")
        lines.append("")
        
        # Сила петли
        impact = loop.get('impact', 0)
        bar = "█" * int(impact * 10) + "░" * (10 - int(impact * 10))
        lines.append(f"📊 Сила: {bar} {impact:.0%}")
        lines.append(f"🎯 Приоритет: {loop.get('strategic_priority', 'Н/Д')}")
        lines.append(f"⏱️ Время на разрыв: {loop.get('break_timeline', 'Н/Д')}")
        
        # Точки разрыва
        points = self.get_intervention_points(loop)
        if points:
            lines.append("")
            lines.append("🎯 Точки разрыва (от наиболее эффективных):")
            for p in points[:3]:
                quick = "⚡ БЫСТРАЯ ПОБЕДА! " if p.get('quick_win_potential') else ""
                difficulty_star = "🔴" if p['difficulty'] > 0.6 else "🟡" if p['difficulty'] > 0.3 else "🟢"
                lines.append(f"   • {difficulty_star} {quick}{p['element_name']}: потенциал {p['impact']:.0%}")
        
        return "\n".join(lines)
    
    def clear(self):
        """Очищает результаты анализа"""
        self.significant_loops = []
        self._visited.clear()
        self._path.clear()
        self._analysis_time = None
        logger.info(f"Результаты анализа для города {self.model.city_name} очищены")


# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def create_analyzer_from_city_model(model: ConfinementModel9) -> CityLoopAnalyzer:
    """Создает анализатор из модели города"""
    return CityLoopAnalyzer(model)


def format_loop_for_report(loop: Dict[str, Any], detailed: bool = False) -> str:
    """Форматирует петлю для отчета"""
    if detailed:
        return (f"**{loop['type_name']}**\n"
                f"{loop['description']}\n\n"
                f"📊 Сила: {loop['impact']:.0%}\n"
                f"🎯 Приоритет: {loop.get('strategic_priority', 'Н/Д')}\n"
                f"⏱️ Сроки: {loop.get('break_timeline', 'Н/Д')}\n\n"
                f"💡 {loop.get('advice', '')}")
    else:
        return f"{loop['description']} (сила {loop['impact']:.0%}, приоритет {loop.get('strategic_priority', 'Н/Д')})"


# ============================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================

if __name__ == "__main__":
    print("🧪 Тестирование CityLoopAnalyzer...")
    
    # Создаем тестовую модель города
    from confinement_model import ConfinementModel9
    
    test_metrics = {'СБ': 2.3, 'ТФ': 2.8, 'УБ': 3.2, 'ЧВ': 2.5}
    model = ConfinementModel9(city_name="Тестовый Город", city_id=1)
    model.build_from_city_data(test_metrics, [])
    
    # Создаем анализатор
    analyzer = CityLoopAnalyzer(model)
    
    # Анализируем
    loops = analyzer.analyze()
    
    print(f"\n📊 Найдено петель: {len(loops)}")
    
    if loops:
        strongest = analyzer.get_strongest_loop()
        print(f"\n🔴 САМАЯ СИЛЬНАЯ ПЕТЛЯ:")
        print(analyzer.visualize_loop(strongest))
        
        print(f"\n🎯 ЛУЧШАЯ ТОЧКА ВМЕШАТЕЛЬСТВА:")
        print(analyzer.get_break_points_summary())
        
        print(f"\n📊 СТАТИСТИКА:")
        stats = analyzer.get_statistics()
        print(f"  Город: {stats['city_name']}")
        print(f"  Всего петель: {stats['total_loops']}")
        print(f"  Критических элементов: {len(stats['critical_elements'])}")
    
    print("\n✅ Тест завершен")
