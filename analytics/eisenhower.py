"""Eisenhower matrix over tasks (ТЗ §9 — troubleshooter view).

Re-buckets the prioritised task list from `analytics.tasks.derive` into
classical Эйзенхауэр-квадранты:

    Q1 do_first   — срочно + важно   (делать лично сейчас)
    Q2 schedule   — не срочно + важно (планировать с горизонтом)
    Q3 delegate   — срочно + не важно (передать заместителю)
    Q4 eliminate  — не срочно + не важно (отбросить / минимизировать)

Классификация:
    urgent      = priority in {urgent, high} OR deadline_days ≤ 3
    important   = priority in {urgent, high, medium}
                  OR source in {crisis, roadmap}

Кризисы всегда important (их нельзя «отбросить»). Пункты повестки,
связанные с агендой дня, важны пока приоритет ≥ medium; низкий
приоритет из повестки дрейфует в delegate/eliminate.

Pure, no I/O — потребляет уже готовый `tasks` list из TaskList.to_dict().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


_QUADRANT_META: Dict[str, Dict[str, str]] = {
    "do_first": {
        "label": "Сделать сейчас",
        "description": "Срочно и важно — личное внимание мэра.",
    },
    "schedule": {
        "label": "Запланировать",
        "description": "Важно, но не срочно — поставить в план.",
    },
    "delegate": {
        "label": "Делегировать",
        "description": "Срочно, но не критично — передать исполнителю.",
    },
    "eliminate": {
        "label": "Отбросить",
        "description": "Ни срочно, ни важно — снять с повестки.",
    },
}


@dataclass
class Quadrant:
    key: str
    label: str
    description: str
    tasks: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "count": len(self.tasks),
            "tasks": list(self.tasks),
        }


@dataclass
class EisenhowerReport:
    quadrants: Dict[str, Quadrant]
    total: int
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quadrants": {k: q.to_dict() for k, q in self.quadrants.items()},
            "total": int(self.total),
            "note": self.note,
        }


_URGENT_PRIORITIES = {"urgent", "high"}
_IMPORTANT_PRIORITIES = {"urgent", "high", "medium"}
_IMPORTANT_SOURCES = {"crisis", "roadmap"}


def classify(task: Dict[str, Any]) -> str:
    """Return one of do_first / schedule / delegate / eliminate for a task."""
    priority = str(task.get("priority") or "").lower()
    source = str(task.get("source") or "").lower()
    try:
        deadline_days = int(task.get("deadline_days") or 99)
    except (TypeError, ValueError):
        deadline_days = 99

    is_urgent = priority in _URGENT_PRIORITIES or deadline_days <= 3
    is_important = (priority in _IMPORTANT_PRIORITIES) or (source in _IMPORTANT_SOURCES)

    if is_urgent and is_important:
        return "do_first"
    if is_important and not is_urgent:
        return "schedule"
    if is_urgent and not is_important:
        return "delegate"
    return "eliminate"


def bucket(tasks: Optional[Iterable[Dict[str, Any]]] = None) -> EisenhowerReport:
    """Re-bucket a list of tasks into the four quadrants."""
    tasks = list(tasks or [])
    quadrants = {
        key: Quadrant(key=key, label=meta["label"], description=meta["description"])
        for key, meta in _QUADRANT_META.items()
    }
    for t in tasks:
        if not isinstance(t, dict):
            continue
        target = classify(t)
        quadrants[target].tasks.append(t)

    note = None
    if not tasks:
        note = "Нет активных поручений — все квадранты пусты."

    return EisenhowerReport(quadrants=quadrants, total=len(tasks), note=note)
