#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
МОДУЛЬ 14: КОМАНДА И ПОРУЧЕНИЯ (Task Manager)
Система контроля исполнения поручений мэра и управления командой

Основан на методах:
- Управление проектами (PMBOK)
- Система контроля сроков и качества
- Матрица ответственности (RACI)
- Автоматическое напоминание и эскалация
- Анализ исполнительской дисциплины
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


# ==================== МОДЕЛИ ДАННЫХ ====================

class TaskStatus(Enum):
    """Статусы задач"""
    DRAFT = "draft"                 # Черновик
    ASSIGNED = "assigned"           # Назначена
    IN_PROGRESS = "in_progress"     # В работе
    REVIEW = "review"               # На проверке
    COMPLETED = "completed"         # Выполнена
    CANCELLED = "cancelled"         # Отменена
    OVERDUE = "overdue"             # Просрочена


class TaskPriority(Enum):
    """Приоритеты поручений"""
    URGENT = "urgent"       # Срочно (24 часа)
    HIGH = "high"           # Высокий (3 дня)
    MEDIUM = "medium"       # Средний (7 дней)
    LOW = "low"             # Низкий (14 дней)
    PLANNED = "planned"     # Плановый (30 дней)


class Role(Enum):
    """Роли в команде"""
    MAYOR = "mayor"                 # Мэр
    DEPUTY = "deputy"               # Заместитель мэра
    HEAD = "head"                   # Начальник департамента
    SPECIALIST = "specialist"       # Специалист
    EXPERT = "expert"               # Внешний эксперт


@dataclass
class TeamMember:
    """Член команды"""
    id: str
    name: str
    role: Role
    department: str
    email: str
    phone: str
    telegram_id: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True
    assigned_tasks: List[str] = field(default_factory=list)
    completed_tasks: int = 0
    performance_score: float = 0.5  # 0-1
    joined_at: datetime = field(default_factory=datetime.now)


@dataclass
class MayorTask:
    """Поручение мэра"""
    id: str
    title: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    created_by: str                    # ID создателя
    assigned_to: str                   # ID исполнителя
    created_at: datetime
    deadline: datetime
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Дополнительные поля
    dependencies: List[str] = field(default_factory=list)  # ID зависимых задач
    attachments: List[str] = field(default_factory=list)   # ссылки на файлы
    comments: List[Dict] = field(default_factory=list)     # комментарии
    history: List[Dict] = field(default_factory=list)      # история изменений
    quality_score: Optional[float] = None                  # оценка качества (0-1)
    is_overdue: bool = False
    overdue_days: int = 0


@dataclass
class WeeklyReport:
    """Еженедельный отчёт"""
    id: str
    author_id: str
    week_start: datetime
    week_end: datetime
    completed_tasks: List[Dict]
    in_progress_tasks: List[Dict]
    planned_tasks: List[Dict]
    issues: List[str]
    achievements: List[str]
    next_week_plan: List[str]
    created_at: datetime
    status: str = "draft"  # draft/submitted/approved


# ==================== КОНФИГУРАЦИЯ ====================

class TaskManagerConfig:
    """Конфигурация системы поручений"""
    
    # Сроки по приоритетам (дни)
    DEADLINES = {
        TaskPriority.URGENT: 1,
        TaskPriority.HIGH: 3,
        TaskPriority.MEDIUM: 7,
        TaskPriority.LOW: 14,
        TaskPriority.PLANNED: 30
    }
    
    # Напоминания (часы до дедлайна)
    REMINDER_HOURS = [48, 24, 12, 6, 1]
    
    # Цвета для дашборда
    COLORS = {
        TaskPriority.URGENT: "#DC3545",
        TaskPriority.HIGH: "#FD7E14",
        TaskPriority.MEDIUM: "#FFC107",
        TaskPriority.LOW: "#28A745",
        TaskPriority.PLANNED: "#6C757D",
        TaskStatus.OVERDUE: "#DC3545",
        TaskStatus.COMPLETED: "#28A745",
        TaskStatus.IN_PROGRESS: "#17A2B8"
    }


# ==================== ОСНОВНОЙ КЛАСС ====================

class TaskManager:
    """
    Система управления поручениями мэра и контроля команды
    
    Позволяет мэру:
    - Ставить поручения с контролем сроков
    - Отслеживать исполнение в реальном времени
    - Получать автоматические напоминания
    - Анализировать эффективность команды
    """
    
    def __init__(self, city_name: str, config: TaskManagerConfig = None):
        self.city_name = city_name
        self.config = config or TaskManagerConfig()
        
        # Хранилище
        self.tasks: Dict[str, MayorTask] = {}
        self.team_members: Dict[str, TeamMember] = {}
        self.weekly_reports: Dict[str, WeeklyReport] = {}
        
        # Уведомления
        self.notifications: List[Dict] = []
        
        # Статистика
        self.statistics = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'overdue_tasks': 0,
            'average_completion_time': 0
        }
        
        # Фоновые задачи
        self.reminder_task = None
        self.is_running = False
        
        logger.info(f"TaskManager инициализирован для города {city_name}")
    
    # ==================== 1. УПРАВЛЕНИЕ КОМАНДОЙ ====================
    
    async def add_team_member(self,
                               name: str,
                               role: Role,
                               department: str,
                               email: str,
                               phone: str,
                               telegram_id: str = None) -> TeamMember:
        """
        Добавление члена команды
        """
        member_id = f"member_{hashlib.md5(f'{name}_{datetime.now().isoformat()}'.encode()).hexdigest()[:8]}"
        
        member = TeamMember(
            id=member_id,
            name=name,
            role=role,
            department=department,
            email=email,
            phone=phone,
            telegram_id=telegram_id
        )
        
        self.team_members[member_id] = member
        
        logger.info(f"Добавлен член команды: {name} ({role.value}) - {department}")
        return member
    
    async def update_performance(self, member_id: str, task_quality: float) -> float:
        """
        Обновление показателя эффективности сотрудника
        """
        member = self.team_members.get(member_id)
        if not member:
            return 0.0
        
        # Экспоненциальное скользящее среднее
        member.performance_score = member.performance_score * 0.7 + task_quality * 0.3
        member.completed_tasks += 1
        
        logger.info(f"Обновлена эффективность {member.name}: {member.performance_score:.0%}")
        return member.performance_score
    
    # ==================== 2. УПРАВЛЕНИЕ ПОРУЧЕНИЯМИ ====================
    
    async def create_task(self,
                           title: str,
                           description: str,
                           priority: TaskPriority,
                           assigned_to: str,
                           created_by: str = "mayor",
                           dependencies: List[str] = None) -> MayorTask:
        """
        Создание нового поручения
        """
        task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hashlib.md5(title.encode()).hexdigest()[:4]}"
        
        # Расчёт дедлайна
        days = self.config.DEADLINES.get(priority, 7)
        deadline = datetime.now() + timedelta(days=days)
        
        task = MayorTask(
            id=task_id,
            title=title,
            description=description,
            priority=priority,
            status=TaskStatus.ASSIGNED,
            created_by=created_by,
            assigned_to=assigned_to,
            created_at=datetime.now(),
            deadline=deadline,
            dependencies=dependencies or [],
            history=[{
                'action': 'created',
                'timestamp': datetime.now().isoformat(),
                'user': created_by
            }]
        )
        
        self.tasks[task_id] = task
        
        # Добавляем задачу в список сотрудника
        if assigned_to in self.team_members:
            self.team_members[assigned_to].assigned_tasks.append(task_id)
        
        # Создаём уведомление
        await self._create_notification(assigned_to, f"Вам назначено поручение: {title}", task_id)
        
        self.statistics['total_tasks'] += 1
        
        logger.info(f"Создано поручение '{title}' для {self.team_members.get(assigned_to, assigned_to).name if assigned_to in self.team_members else assigned_to}")
        
        return task
    
    async def update_task_status(self, task_id: str, new_status: TaskStatus, comment: str = None) -> bool:
        """
        Обновление статуса поручения
        """
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        old_status = task.status
        task.status = new_status
        task.updated_at = datetime.now()
        
        # Логируем изменение
        task.history.append({
            'action': 'status_change',
            'from': old_status.value,
            'to': new_status.value,
            'comment': comment,
            'timestamp': datetime.now().isoformat(),
            'user': task.assigned_to
        })
        
        # Если задача выполнена
        if new_status == TaskStatus.COMPLETED:
            task.completed_at = datetime.now()
            
            # Обновляем эффективность сотрудника (если есть оценка качества)
            if task.quality_score:
                await self.update_performance(task.assigned_to, task.quality_score)
            
            # Уведомляем создателя
            await self._create_notification(task.created_by, f"Поручение '{task.title}' выполнено", task_id)
        
        # Если задача просрочена
        if datetime.now() > task.deadline and new_status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
            task.is_overdue = True
            task.overdue_days = (datetime.now() - task.deadline).days
            
            # Эскалация (уведомляем руководителя)
            await self._escalate_overdue(task)
        
        logger.info(f"Статус задачи {task_id} изменён: {old_status.value} -> {new_status.value}")
        return True
    
    async def add_comment(self, task_id: str, comment: str, author_id: str) -> bool:
        """
        Добавление комментария к поручению
        """
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        task.comments.append({
            'author': author_id,
            'text': comment,
            'timestamp': datetime.now().isoformat()
        })
        
        # Уведомляем исполнителя и создателя
        recipients = {task.assigned_to, task.created_by}
        for recipient in recipients:
            if recipient != author_id:
                await self._create_notification(recipient, f"Новый комментарий к '{task.title}': {comment[:50]}...", task_id)
        
        return True
    
    # ==================== 3. ОЦЕНКА КАЧЕСТВА ====================
    
    async def rate_task_quality(self, task_id: str, quality_score: float, feedback: str) -> bool:
        """
        Оценка качества выполненного поручения (мэром)
        """
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task.status != TaskStatus.COMPLETED:
            logger.warning(f"Нельзя оценить незавершённую задачу {task_id}")
            return False
        
        task.quality_score = min(1.0, max(0.0, quality_score))
        
        task.history.append({
            'action': 'quality_assessed',
            'score': quality_score,
            'feedback': feedback,
            'timestamp': datetime.now().isoformat(),
            'user': task.created_by
        })
        
        # Обновляем эффективность сотрудника
        await self.update_performance(task.assigned_to, quality_score)
        
        logger.info(f"Задача {task_id} оценена: {quality_score:.0%}")
        return True
    
    # ==================== 4. ЕЖЕНЕДЕЛЬНЫЕ ОТЧЁТЫ ====================
    
    async def create_weekly_report(self, author_id: str) -> WeeklyReport:
        """
        Создание еженедельного отчёта
        """
        week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        
        # Задачи сотрудника за неделю
        member_tasks = [t for t in self.tasks.values() if t.assigned_to == author_id]
        
        completed = []
        in_progress = []
        
        for task in member_tasks:
            if task.completed_at and task.completed_at >= week_start:
                completed.append({
                    'id': task.id,
                    'title': task.title,
                    'completed_at': task.completed_at.isoformat(),
                    'quality_score': task.quality_score
                })
            elif task.status in [TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS] and task.created_at >= week_start:
                in_progress.append({
                    'id': task.id,
                    'title': task.title,
                    'deadline': task.deadline.isoformat(),
                    'priority': task.priority.value
                })
        
        report_id = f"report_{author_id}_{week_start.strftime('%Y%m%d')}"
        
        report = WeeklyReport(
            id=report_id,
            author_id=author_id,
            week_start=week_start,
            week_end=week_end,
            completed_tasks=completed,
            in_progress_tasks=in_progress,
            planned_tasks=[],
            issues=[],
            achievements=[],
            next_week_plan=[],
            created_at=datetime.now()
        )
        
        self.weekly_reports[report_id] = report
        
        logger.info(f"Создан недельный отчёт для {self.team_members.get(author_id, author_id).name if author_id in self.team_members else author_id}")
        
        return report
    
    async def submit_weekly_report(self, report_id: str, 
                                    achievements: List[str],
                                    issues: List[str],
                                    next_week_plan: List[str]) -> bool:
        """
        Подача еженедельного отчёта
        """
        report = self.weekly_reports.get(report_id)
        if not report:
            return False
        
        report.achievements = achievements
        report.issues = issues
        report.next_week_plan = next_week_plan
        report.status = "submitted"
        
        # Уведомляем мэра
        await self._create_notification(
            "mayor",
            f"Поступил недельный отчёт от {self.team_members.get(report.author_id, report.author_id).name if report.author_id in self.team_members else report.author_id}",
            report_id
        )
        
        logger.info(f"Подан недельный отчёт {report_id}")
        return True
    
    # ==================== 5. УВЕДОМЛЕНИЯ И НАПОМИНАНИЯ ====================
    
    async def _create_notification(self, user_id: str, message: str, reference_id: str = None) -> None:
        """
        Создание уведомления
        """
        notification = {
            'id': f"notif_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hashlib.md5(message.encode()).hexdigest()[:4]}",
            'user_id': user_id,
            'message': message,
            'reference_id': reference_id,
            'created_at': datetime.now().isoformat(),
            'is_read': False
        }
        
        self.notifications.append(notification)
        
        # В реальной системе здесь отправка в Telegram/Email
        logger.info(f"Уведомление для {user_id}: {message[:100]}")
    
    async def _escalate_overdue(self, task: MayorTask) -> None:
        """
        Эскалация просроченной задачи
        """
        # Уведомляем руководителя
        await self._create_notification(
            "mayor",
            f"⚠️ ПРОСРОЧКА: поручение '{task.title}' просрочено на {task.overdue_days} дней. Исполнитель: {self.team_members.get(task.assigned_to, task.assigned_to).name if task.assigned_to in self.team_members else task.assigned_to}",
            task.id
        )
        
        # Отмечаем в истории
        task.history.append({
            'action': 'escalated',
            'reason': f'overdue_{task.overdue_days}_days',
            'timestamp': datetime.now().isoformat()
        })
    
    async def check_overdue_tasks(self) -> List[MayorTask]:
        """
        Проверка просроченных задач
        """
        overdue = []
        
        for task in self.tasks.values():
            if task.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                if datetime.now() > task.deadline and not task.is_overdue:
                    task.is_overdue = True
                    task.overdue_days = (datetime.now() - task.deadline).days
                    task.status = TaskStatus.OVERDUE
                    overdue.append(task)
                    
                    # Эскалация
                    await self._escalate_overdue(task)
        
        self.statistics['overdue_tasks'] = len([t for t in self.tasks.values() if t.is_overdue])
        
        return overdue
    
    async def send_reminders(self) -> List[Dict]:
        """
        Отправка напоминаний о приближающихся дедлайнах
        """
        reminders = []
        now = datetime.now()
        
        for task in self.tasks.values():
            if task.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
                continue
            
            hours_until = (task.deadline - now).total_seconds() / 3600
            
            for reminder_hour in self.config.REMINDER_HOURS:
                if abs(hours_until - reminder_hour) < 0.5:  # +/- 30 минут
                    # Отправляем напоминание
                    message = f"🔔 Напоминание: поручение '{task.title}' должно быть выполнено через {reminder_hour} часов"
                    await self._create_notification(task.assigned_to, message, task.id)
                    
                    reminders.append({
                        'task_id': task.id,
                        'title': task.title,
                        'hours_before': reminder_hour,
                        'sent_at': datetime.now().isoformat()
                    })
                    
                    logger.info(f"Отправлено напоминание по задаче '{task.title}' за {reminder_hour} ч")
        
        return reminders
    
    # ==================== 6. АНАЛИТИКА И СТАТИСТИКА ====================
    
    async def get_team_performance(self) -> Dict[str, Any]:
        """
        Анализ эффективности команды
        """
        if not self.team_members:
            return {'error': 'Нет членов команды'}
        
        performance = []
        
        for member in self.team_members.values():
            # Задачи члена команды
            member_tasks = [t for t in self.tasks.values() if t.assigned_to == member.id]
            
            completed = [t for t in member_tasks if t.status == TaskStatus.COMPLETED]
            overdue = [t for t in member_tasks if t.is_overdue]
            in_progress = [t for t in member_tasks if t.status == TaskStatus.IN_PROGRESS]
            
            # Среднее качество
            quality_scores = [t.quality_score for t in completed if t.quality_score is not None]
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
            
            performance.append({
                'id': member.id,
                'name': member.name,
                'role': member.role.value,
                'department': member.department,
                'performance_score': member.performance_score,
                'completed_tasks': len(completed),
                'overdue_tasks': len(overdue),
                'in_progress_tasks': len(in_progress),
                'avg_quality': avg_quality,
                'total_assigned': len(member_tasks)
            })
        
        # Сортировка по эффективности
        performance.sort(key=lambda x: x['performance_score'], reverse=True)
        
        return {
            'team_size': len(self.team_members),
            'members': performance,
            'best_performer': performance[0]['name'] if performance else None,
            'worst_performer': performance[-1]['name'] if performance else None
        }
    
    async def get_mayor_dashboard(self) -> Dict[str, Any]:
        """
        Дашборд мэра по поручениям
        """
        # Все активные задачи
        active_tasks = [t for t in self.tasks.values() 
                       if t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]]
        
        # Просроченные
        overdue_tasks = [t for t in active_tasks if t.is_overdue]
        
        # По приоритетам
        by_priority = defaultdict(int)
        for task in active_tasks:
            by_priority[task.priority.value] += 1
        
        # По исполнителям
        by_assignee = defaultdict(int)
        for task in active_tasks:
            assignee = self.team_members.get(task.assigned_to)
            if assignee:
                by_assignee[assignee.name] += 1
        
        # Последние выполненные
        completed = [t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]
        completed.sort(key=lambda x: x.completed_at or datetime.min, reverse=True)
        
        # Непрочитанные уведомления
        unread_notifications = [n for n in self.notifications if not n.get('is_read', False)]
        
        return {
            'timestamp': datetime.now().isoformat(),
            'city': self.city_name,
            'statistics': {
                'total_tasks': len(self.tasks),
                'active_tasks': len(active_tasks),
                'overdue_tasks': len(overdue_tasks),
                'completed_tasks': self.statistics['completed_tasks'],
                'completion_rate': len(completed) / len(self.tasks) if self.tasks else 0
            },
            'by_priority': dict(by_priority),
            'by_assignee': dict(by_assignee),
            'overdue_tasks': [
                {
                    'id': t.id,
                    'title': t.title,
                    'assignee': self.team_members.get(t.assigned_to, t.assigned_to).name if t.assigned_to in self.team_members else t.assigned_to,
                    'overdue_days': t.overdue_days,
                    'deadline': t.deadline.isoformat()
                }
                for t in overdue_tasks[:10]
            ],
            'recent_completed': [
                {
                    'title': t.title,
                    'assignee': self.team_members.get(t.assigned_to, t.assigned_to).name if t.assigned_to in self.team_members else t.assigned_to,
                    'quality': t.quality_score,
                    'completed_at': t.completed_at.isoformat() if t.completed_at else None
                }
                for t in completed[:5]
            ],
            'unread_notifications': len(unread_notifications),
            'notifications': unread_notifications[:10]
        }
    
    # ==================== 7. ФОНОВЫЙ МОНИТОРИНГ ====================
    
    async def start_monitoring(self, interval_minutes: int = 60):
        """
        Запуск фонового мониторинга задач
        """
        self.is_running = True
        logger.info(f"Запуск фонового мониторинга поручений с интервалом {interval_minutes} минут")
        
        while self.is_running:
            try:
                # Проверка просроченных задач
                overdue = await self.check_overdue_tasks()
                if overdue:
                    logger.warning(f"Обнаружено {len(overdue)} просроченных задач")
                
                # Отправка напоминаний
                reminders = await self.send_reminders()
                if reminders:
                    logger.info(f"Отправлено {len(reminders)} напоминаний")
                
            except Exception as e:
                logger.error(f"Ошибка в фоновом мониторинге: {e}")
            
            await asyncio.sleep(interval_minutes * 60)
    
    async def stop_monitoring(self):
        """Остановка фонового мониторинга"""
        self.is_running = False
        logger.info("Фоновый мониторинг остановлен")
    
    # ==================== 8. ЭКСПОРТ ОТЧЁТОВ ====================
    
    async def export_performance_report(self, period_days: int = 30) -> Dict[str, Any]:
        """
        Экспорт отчёта по эффективности команды
        """
        cutoff = datetime.now() - timedelta(days=period_days)
        
        # Задачи за период
        period_tasks = [t for t in self.tasks.values() if t.created_at >= cutoff]
        completed_period = [t for t in period_tasks if t.status == TaskStatus.COMPLETED]
        
        # Эффективность по департаментам
        dept_performance = defaultdict(lambda: {'total': 0, 'completed': 0, 'quality': []})
        
        for task in period_tasks:
            assignee = self.team_members.get(task.assigned_to)
            if assignee:
                dept_performance[assignee.department]['total'] += 1
                if task.status == TaskStatus.COMPLETED:
                    dept_performance[assignee.department]['completed'] += 1
                if task.quality_score:
                    dept_performance[assignee.department]['quality'].append(task.quality_score)
        
        # Агрегируем
        dept_summary = []
        for dept, data in dept_performance.items():
            dept_summary.append({
                'department': dept,
                'total_tasks': data['total'],
                'completed_tasks': data['completed'],
                'completion_rate': data['completed'] / data['total'] if data['total'] > 0 else 0,
                'avg_quality': sum(data['quality']) / len(data['quality']) if data['quality'] else 0
            })
        
        dept_summary.sort(key=lambda x: x['completion_rate'], reverse=True)
        
        return {
            'report_id': f"perf_report_{datetime.now().strftime('%Y%m%d')}",
            'period_days': period_days,
            'generated_at': datetime.now().isoformat(),
            'city': self.city_name,
            'summary': {
                'total_tasks': len(period_tasks),
                'completed_tasks': len(completed_period),
                'completion_rate': len(completed_period) / len(period_tasks) if period_tasks else 0,
                'avg_completion_time': self.statistics['average_completion_time'],
                'overdue_count': len([t for t in period_tasks if t.is_overdue])
            },
            'department_performance': dept_summary,
            'top_performers': await self.get_team_performance(),
            'recommendations': self._generate_performance_recommendations(dept_summary)
        }
    
    def _generate_performance_recommendations(self, dept_summary: List[Dict]) -> List[str]:
        """Генерация рекомендаций по эффективности"""
        recommendations = []
        
        for dept in dept_summary:
            if dept['completion_rate'] < 0.5:
                recommendations.append(f"⚠️ Департамент {dept['department']} имеет низкий процент выполнения ({dept['completion_rate']:.0%}). Требуется анализ причин.")
            elif dept['completion_rate'] > 0.9:
                recommendations.append(f"🏆 Департамент {dept['department']} показывает отличные результаты ({dept['completion_rate']:.0%})")
        
        if not recommendations:
            recommendations.append("✅ Все департаменты показывают хорошие результаты")
        
        return recommendations


# ==================== ИНТЕГРАЦИЯ С ОСНОВНЫМ ПРИЛОЖЕНИЕМ ====================

async def create_task_manager(city_name: str) -> TaskManager:
    """Фабричная функция для создания менеджера поручений"""
    return TaskManager(city_name)


# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("🧪 Тестирование TaskManager...")
        
        # Создаём менеджер
        manager = TaskManager("Коломна")
        
        # 1. Добавляем команду
        print("\n👥 ДОБАВЛЕНИЕ КОМАНДЫ:")
        
        ivanov = await manager.add_team_member(
            name="Иванов Иван",
            role=Role.HEAD,
            department="Безопасность",
            email="ivanov@kolomna.ru",
            phone="+7XXX"
        )
        print(f"  + {ivanov.name} ({ivanov.role.value}) - {ivanov.department}")
        
        petrov = await manager.add_team_member(
            name="Петров Пётр",
            role=Role.SPECIALIST,
            department="Инфраструктура",
            email="petrov@kolomna.ru",
            phone="+7XXX"
        )
        print(f"  + {petrov.name} ({petrov.role.value}) - {petrov.department}")
        
        # 2. Создаём поручения
        print("\n📋 СОЗДАНИЕ ПОРУЧЕНИЙ:")
        
        task1 = await manager.create_task(
            title="Усилить патрулирование в Колычёво",
            description="Увеличить количество патрулей в 2 раза, установить камеры",
            priority=TaskPriority.URGENT,
            assigned_to=ivanov.id
        )
        print(f"  + {task1.title} (срок: {task1.deadline.strftime('%d.%m.%Y')})")
        
        task2 = await manager.create_task(
            title="Подготовить отчёт по дорогам",
            description="Анализ состояния дорог и план ремонта на 2026 год",
            priority=TaskPriority.HIGH,
            assigned_to=petrov.id
        )
        print(f"  + {task2.title} (срок: {task2.deadline.strftime('%d.%m.%Y')})")
        
        # 3. Обновление статуса
        print("\n🔄 ОБНОВЛЕНИЕ СТАТУСОВ:")
        
        await manager.update_task_status(task1.id, TaskStatus.IN_PROGRESS, "Приступил к выполнению")
        print(f"  {task1.title} -> В работе")
        
        # Имитация выполнения
        await asyncio.sleep(0.5)
        
        await manager.update_task_status(task1.id, TaskStatus.COMPLETED, "Задача выполнена")
        print(f"  {task1.title} -> Выполнена")
        
        # 4. Оценка качества
        print("\n⭐ ОЦЕНКА КАЧЕСТВА:")
        
        await manager.rate_task_quality(task1.id, 0.85, "Хорошая работа, но камеры нужно добавить")
        print(f"  {task1.title} оценена на 85%")
        
        # 5. Еженедельный отчёт
        print("\n📊 ЕЖЕНЕДЕЛЬНЫЙ ОТЧЁТ:")
        
        report = await manager.create_weekly_report(petrov.id)
        await manager.submit_weekly_report(
            report.id,
            achievements=["Подготовлен план ремонта дорог", "Проведены встречи с жителями"],
            issues=["Нехватка техники", "Задержки согласований"],
            next_week_plan=["Завершить отчёт", "Провести тендер"]
        )
        print(f"  Отчёт {report.id} подан")
        
        # 6. Дашборд мэра
        print("\n📋 ДАШБОРД МЭРА:")
        
        dashboard = await manager.get_mayor_dashboard()
        print(f"  Всего задач: {dashboard['statistics']['total_tasks']}")
        print(f"  Активных: {dashboard['statistics']['active_tasks']}")
        print(f"  Просроченных: {dashboard['statistics']['overdue_tasks']}")
        print(f"  Выполнено: {dashboard['statistics']['completed_tasks']}")
        
        # 7. Эффективность команды
        print("\n📊 ЭФФЕКТИВНОСТЬ КОМАНДЫ:")
        
        performance = await manager.get_team_performance()
        print(f"  Размер команды: {performance['team_size']}")
        for member in performance['members']:
            print(f"    • {member['name']} — эффективность {member['performance_score']:.0%}, "
                  f"выполнено {member['completed_tasks']} задач")
        
        print("\n✅ Тест завершен")
    
    asyncio.run(demo())
