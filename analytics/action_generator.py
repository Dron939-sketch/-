"""Action Generator - преобразует аномалии и проблемы в конкретные поручения.

Генерирует структурированные задачи с указанием:
- исполнителей (должности/отделы)
- сроков исполнения
- приоритета
- ожидаемого результата
- метрик успеха
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import Dict, List, Optional


class Priority(str, Enum):
    CRITICAL = "critical"  # Немедленно (24-48 часов)
    HIGH = "high"          # 3-7 дней
    MEDIUM = "medium"      # 1-2 недели
    LOW = "low"            # 1 месяц+


class ActionType(str, Enum):
    INSPECTION = "inspection"        # Проверка/инспекция
    REPAIR = "repair"                # Ремонт/восстановление
    MEETING = "meeting"              # Совещание
    DOCUMENT = "document"            # Подготовка документа
    COMMUNICATION = "communication"  # Работа с населением
    INFRASTRUCTURE = "infrastructure"# Инфраструктурный проект
    SOCIAL = "social"                # Социальная программа
    ECONOMIC = "economic"            # Экономическая мера


@dataclass
class ResponsibleParty:
    """Ответственный исполнитель."""
    role: str  # Должность или отдел
    name: Optional[str] = None  # Конкретное имя (если известно)
    backup: Optional[str] = None  # Заместитель
    
    def to_dict(self) -> Dict:
        return {
            "role": self.role,
            "name": self.name,
            "backup": self.backup,
        }


@dataclass
class ActionItem:
    """Конкретное поручение."""
    title: str
    description: str
    action_type: ActionType
    priority: Priority
    responsible: ResponsibleParty
    deadline_days: int
    expected_outcome: str
    success_metrics: List[str] = field(default_factory=list)
    related_vector: Optional[str] = None  # СБ/ТФ/УБ/ЧВ
    estimated_cost_rub: int = 0
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "description": self.description,
            "action_type": self.action_type.value,
            "priority": self.priority.value,
            "responsible": self.responsible.to_dict(),
            "deadline_days": self.deadline_days,
            "expected_outcome": self.expected_outcome,
            "success_metrics": self.success_metrics,
            "related_vector": self.related_vector,
            "estimated_cost_rub": self.estimated_cost_rub,
            "dependencies": self.dependencies,
            "tags": self.tags,
        }


@dataclass
class ActionPlan:
    """План действий на день/неделю."""
    city: str
    generated_at: date
    horizon_days: int
    actions: List[ActionItem] = field(default_factory=list)
    summary: str = ""
    total_estimated_cost_rub: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "city": self.city,
            "generated_at": self.generated_at.isoformat(),
            "horizon_days": self.horizon_days,
            "actions": [a.to_dict() for a in self.actions],
            "summary": self.summary,
            "total_estimated_cost_rub": self.total_estimated_cost_rub,
        }


# База знаний типовых проблем и решений
PROBLEM_PATTERNS: Dict[str, Dict] = {
    # Безопасность
    "crime_increase": {
        "keywords": ["преступность", "кража", "грабёж", "насилие", "ДТП"],
        "vector": "safety",
        "default_actions": [
            {
                "title": "Организовать усиленное патрулирование",
                "type": ActionType.INSPECTION,
                "priority": Priority.HIGH,
                "role": "Начальник отдела полиции",
                "deadline": 3,
                "outcome": "Снижение уличной преступности на 15%",
                "metrics": ["Количество патрулей в сутки", "Число раскрытых преступлений"],
            },
            {
                "title": "Проверить работу камер видеонаблюдения",
                "type": ActionType.INSPECTION,
                "priority": Priority.MEDIUM,
                "role": "Отдел ЖКХ и благоустройства",
                "deadline": 7,
                "outcome": "100% работоспособность камер в проблемных зонах",
                "metrics": ["Доля работающих камер", "Зоны покрытия"],
            },
        ],
    },
    
    # Экономика
    "business_complaints": {
        "keywords": ["бизнес", "предприниматель", "налог", "проверка", "закрытие"],
        "vector": "economy",
        "default_actions": [
            {
                "title": "Провести встречу с представителями малого бизнеса",
                "type": ActionType.MEETING,
                "priority": Priority.HIGH,
                "role": "Заместитель главы по экономике",
                "deadline": 5,
                "outcome": "Выявление ключевых проблем бизнеса",
                "metrics": ["Количество участников", "Список проблем"],
            },
            {
                "title": "Подготовить предложения по налоговым льготам",
                "type": ActionType.DOCUMENT,
                "priority": Priority.MEDIUM,
                "role": "Финансовое управление",
                "deadline": 14,
                "outcome": "Проект постановления о льготах",
                "metrics": ["Количество受益ющих предприятий", "Объём льгот"],
            },
        ],
    },
    
    # Качество жизни
    "utilities_failure": {
        "keywords": ["ЖКХ", "отопление", "вода", "свет", "канализация", "авария"],
        "vector": "quality",
        "default_actions": [
            {
                "title": "Немедленно устранить аварию",
                "type": ActionType.REPAIR,
                "priority": Priority.CRITICAL,
                "role": "Главный инженер УК / Теплосети",
                "deadline": 1,
                "outcome": "Восстановление нормального предоставления услуг",
                "metrics": ["Время восстановления", "Количество пострадавших домов"],
            },
            {
                "title": "Проверить состояние инфраструктуры",
                "type": ActionType.INSPECTION,
                "priority": Priority.HIGH,
                "role": "Отдел ЖКХ",
                "deadline": 7,
                "outcome": "Акт технического состояния",
                "metrics": ["Износ сетей", "План замены"],
            },
        ],
    },
    
    "roads_bad": {
        "keywords": ["дорога", "яма", "асфальт", "ремонт дорог", "транспорт"],
        "vector": "quality",
        "default_actions": [
            {
                "title": "Составить дефектную ведомость",
                "type": ActionType.INSPECTION,
                "priority": Priority.HIGH,
                "role": "Дорожное управление",
                "deadline": 5,
                "outcome": "Перечень участков для ремонта",
                "metrics": ["Площадь повреждений", "Категория дорог"],
            },
            {
                "title": "Запланировать ямочный ремонт",
                "type": ActionType.REPAIR,
                "priority": Priority.MEDIUM,
                "role": "Подрядная организация",
                "deadline": 14,
                "outcome": "Устранение критических дефектов",
                "metrics": ["Количество отремонтированных м²"],
            },
        ],
    },
    
    # Социальный капитал
    "social_tension": {
        "keywords": ["митинг", "протест", "недовольство", "жалоба массовая"],
        "vector": "social",
        "default_actions": [
            {
                "title": "Организовать встречу с активными гражданами",
                "type": ActionType.COMMUNICATION,
                "priority": Priority.CRITICAL,
                "role": "Глава города",
                "deadline": 2,
                "outcome": "Снижение социальной напряжённости",
                "metrics": ["Количество участников", "Резолюция встречи"],
            },
            {
                "title": "Подготовить официальный ответ",
                "type": ActionType.DOCUMENT,
                "priority": Priority.HIGH,
                "role": "Пресс-служба",
                "deadline": 3,
                "outcome": "Публикация разъяснений",
                "metrics": ["Охват публикации", "Тональность комментариев"],
            },
        ],
    },
    
    "culture_events": {
        "keywords": ["культура", "фестиваль", "концерт", "выставка", "мероприятие"],
        "vector": "social",
        "default_actions": [
            {
                "title": "Разработать план мероприятий",
                "type": ActionType.DOCUMENT,
                "priority": Priority.MEDIUM,
                "role": "Управление культуры",
                "deadline": 10,
                "outcome": "Календарь событий на квартал",
                "metrics": ["Количество мероприятий", "Ожидаемая посещаемость"],
            },
        ],
    },
}


class ActionGenerator:
    """Генератор конкретных действий на основе проблем."""
    
    def __init__(self, city_name: str):
        self.city_name = city_name
        self.default_responsibles: Dict[str, str] = {
            "safety": "Начальник отдела полиции",
            "economy": "Заместитель главы по экономике",
            "quality": "Заместитель главы по ЖКХ",
            "social": "Заместитель главы по социальным вопросам",
        }
    
    def generate_from_problem(
        self,
        problem_text: str,
        category: Optional[str] = None,
        severity: float = 0.5,
    ) -> List[ActionItem]:
        """Генерирует действия на основе текста проблемы."""
        
        actions: List[ActionItem] = []
        problem_lower = problem_text.lower()
        
        # Поиск паттерна
        matched_pattern = None
        for pattern_key, pattern_data in PROBLEM_PATTERNS.items():
            if any(kw in problem_lower for kw in pattern_data["keywords"]):
                matched_pattern = pattern_data
                break
        
        if matched_pattern:
            # Создаём действия из паттерна
            for action_template in matched_pattern["default_actions"]:
                priority = self._adjust_priority(
                    action_template["priority"], 
                    severity
                )
                
                action = ActionItem(
                    title=action_template["title"],
                    description=f"По проблеме: {problem_text[:200]}",
                    action_type=action_template["type"],
                    priority=priority,
                    responsible=ResponsibleParty(role=action_template["role"]),
                    deadline_days=action_template["deadline"],
                    expected_outcome=action_template["outcome"],
                    success_metrics=action_template.get("metrics", []),
                    related_vector=matched_pattern.get("vector"),
                    tags=[matched_pattern.get("vector", "general"), pattern_key],
                )
                actions.append(action)
        else:
            # Действие по умолчанию для нераспознанных проблем
            vector = self._detect_vector(problem_text)
            action = ActionItem(
                title="Проанализировать проблему и подготовить предложения",
                description=f"Требуется проработка: {problem_text[:200]}",
                action_type= ActionType.INSPECTION,
                priority=Priority.MEDIUM if severity < 0.7 else Priority.HIGH,
                responsible=ResponsibleParty(
                    role=self.default_responsibles.get(vector, "Профильный отдел")
                ),
                deadline_days=7,
                expected_outcome="Доклад с анализом и планом мер",
                success_metrics=["Доклад представлен", "Меры согласованы"],
                related_vector=vector,
                tags=["unclassified"],
            )
            actions.append(action)
        
        return actions
    
    def generate_from_metrics(
        self,
        metrics: Dict[str, float],
        trends: Dict[str, float],
        threshold_decline: float = -0.05,
    ) -> List[ActionItem]:
        """Генерирует превентивные действия на основе метрик."""
        
        actions: List[ActionItem] = []
        vector_names = {
            "safety": "Безопасность",
            "economy": "Экономика",
            "quality": "Качество жизни",
            "social": "Социальный капитал",
        }
        
        for vector, value in metrics.items():
            trend = trends.get(vector, 0)
            
            # Критическое падение
            if trend < threshold_decline:
                action = ActionItem(
                    title=f"Срочно выявить причины падения по вектору «{vector_names.get(vector, vector)}»",
                    description=f"Текущее значение: {value:.2%}, тренд: {trend:.2%} за неделю",
                    action_type=ActionType.MEETING,
                    priority=Priority.HIGH,
                    responsible=ResponsibleParty(
                        role=self.default_responsibles.get(vector, "Профильный отдел")
                    ),
                    deadline_days=5,
                    expected_outcome="Выявлены и устранены ключевые факторы негативного тренда",
                    success_metrics=["Тренд остановлен", "Показатель стабилизирован"],
                    related_vector=vector,
                    tags=["metric_alert", "preventive"],
                )
                actions.append(action)
            
            # Низкий абсолютный уровень
            elif value < 0.4:
                action = ActionItem(
                    title=f"Разработать программу улучшения по вектору «{vector_names.get(vector, vector)}»",
                    description=f"Текущее значение {value:.2%} требует системной работы",
                    action_type=ActionType.DOCUMENT,
                    priority=Priority.MEDIUM,
                    responsible=ResponsibleParty(
                        role=self.default_responsibles.get(vector, "Профильный отдел")
                    ),
                    deadline_days=14,
                    expected_outcome="Комплексная программа развития направления",
                    success_metrics=["Программа утверждена", "Определены источники финансирования"],
                    related_vector=vector,
                    tags=["strategic", "low_baseline"],
                )
                actions.append(action)
        
        return actions
    
    def create_daily_plan(
        self,
        problems: List[str],
        metrics: Optional[Dict[str, float]] = None,
        trends: Optional[Dict[str, float]] = None,
    ) -> ActionPlan:
        """Создаёт сводный план действий на день."""
        
        all_actions: List[ActionItem] = []
        
        # Действия из проблем
        for problem in problems:
            all_actions.extend(self.generate_from_problem(problem))
        
        # Превентивные действия из метрик
        if metrics and trends:
            all_actions.extend(self.generate_from_metrics(metrics, trends))
        
        # Сортировка по приоритету
        priority_order = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3,
        }
        all_actions.sort(key=lambda a: priority_order[a.priority])
        
        # Расчёт стоимости
        total_cost = sum(a.estimated_cost_rub for a in all_actions)
        
        # Формирование резюме
        critical_count = sum(1 for a in all_actions if a.priority == Priority.CRITICAL)
        high_count = sum(1 for a in all_actions if a.priority == Priority.HIGH)
        
        summary_parts = []
        if critical_count > 0:
            summary_parts.append(f"⚡ {critical_count} критических задач")
        if high_count > 0:
            summary_parts.append(f"❗ {high_count} важных задач")
        summary_parts.append(f"Всего: {len(all_actions)} поручений")
        
        return ActionPlan(
            city=self.city_name,
            generated_at=date.today(),
            horizon_days=7,
            actions=all_actions,
            summary="; ".join(summary_parts),
            total_estimated_cost_rub=total_cost,
        )
    
    @staticmethod
    def _adjust_priority(base_priority: Priority, severity: float) -> Priority:
        """Корректирует приоритет на основе серьёзности."""
        if severity >= 0.8:
            return Priority.CRITICAL
        elif severity >= 0.6:
            if base_priority in (Priority.MEDIUM, Priority.LOW):
                return Priority.HIGH
        elif severity < 0.3:
            if base_priority == Priority.HIGH:
                return Priority.MEDIUM
        return base_priority
    
    @staticmethod
    def _detect_vector(text: str) -> str:
        """Определяет вектор по тексту."""
        text_lower = text.lower()
        
        if any(kw in text_lower for kw in ["преступность", "полиция", "безопасность", "ДТП"]):
            return "safety"
        if any(kw in text_lower for kw in ["бизнес", "экономика", "работа", "налог"]):
            return "economy"
        if any(kw in text_lower for kw in ["ЖКХ", "дорога", "больница", "школа", "транспорт"]):
            return "quality"
        
        return "social"
