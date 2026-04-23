"""Task derivation (ТЗ §14, MVP adapter).

Pure, no-I/O transformer that turns the mayor's *current signals*
(daily agenda actions + crisis alerts + roadmap milestones) into a
prioritised task list. Each task carries:

    id            — stable sha1 of (title + source)
    title         — one-line imperative
    priority      — urgent | high | medium | low
    deadline_days — how many calendar days the SLA allows
    source        — agenda | crisis | roadmap
    rationale     — short explanation of why this task matters
    suggested_owner — best-guess department / role
    tags          — for UI filtering

The legacy `task_manager.py` ships PMBOK project mgmt + RACI matrix +
auto-escalation. Out of scope for the MVP — we don't have a real team
roster. The adapter gives the mayor a honest "вот что надо сделать
прямо сейчас" derived from live signals.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


_PRIORITY_DAYS = {"urgent": 1, "high": 3, "medium": 7, "low": 14}

_CRISIS_LEVEL_TO_PRIORITY = {
    "critical": "urgent",
    "high":     "urgent",
    "medium":   "high",
    "watch":    "medium",
}

_VECTOR_TO_OWNER = {
    "safety":  "Безопасность / УВД",
    "economy": "Экономразвитие",
    "quality": "ЖКХ / Благоустройство",
    "social":  "Соцзащита / Молодёжная политика",
}

_AGENDA_DEFAULT_OWNER = "Администрация"
_ROADMAP_DEFAULT_OWNER = "Департамент развития"


@dataclass
class Task:
    id: str
    title: str
    priority: str
    deadline_days: int
    source: str
    rationale: str
    suggested_owner: str
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority,
            "deadline_days": int(self.deadline_days),
            "source": self.source,
            "rationale": self.rationale,
            "suggested_owner": self.suggested_owner,
            "tags": list(self.tags),
        }


@dataclass
class TaskList:
    tasks: List[Task]
    counts_by_priority: Dict[str, int]
    counts_by_source: Dict[str, int]
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tasks": [t.to_dict() for t in self.tasks],
            "counts_by_priority": dict(self.counts_by_priority),
            "counts_by_source": dict(self.counts_by_source),
            "note": self.note,
        }


def derive(
    agenda: Optional[Dict[str, Any]] = None,
    crisis: Optional[Dict[str, Any]] = None,
    roadmap: Optional[Dict[str, Any]] = None,
    *,
    max_tasks: int = 20,
) -> TaskList:
    """Return a prioritised task list from current signals.

    Accepts the payloads produced by `/api/city/{name}/agenda`, /crisis,
    and a roadmap response (or the raw Roadmap.to_dict() output). Any of
    them can be None; derivation continues on whichever signals exist.
    """
    tasks: List[Task] = []

    for t in _tasks_from_agenda(agenda or {}):
        tasks.append(t)
    for t in _tasks_from_crisis(crisis or {}):
        tasks.append(t)
    for t in _tasks_from_roadmap(roadmap or {}):
        tasks.append(t)

    # Deduplicate by title (case-insensitive). Earlier = higher priority wins.
    seen: Dict[str, Task] = {}
    for t in tasks:
        key = t.title.strip().lower()
        if key not in seen or _priority_rank(t.priority) > _priority_rank(seen[key].priority):
            seen[key] = t
    deduped = list(seen.values())

    deduped.sort(key=lambda t: (_priority_rank(t.priority), t.deadline_days), reverse=True)
    deduped = deduped[: max(1, int(max_tasks))]

    counts_priority: Dict[str, int] = {}
    counts_source: Dict[str, int] = {}
    for t in deduped:
        counts_priority[t.priority] = counts_priority.get(t.priority, 0) + 1
        counts_source[t.source] = counts_source.get(t.source, 0) + 1

    note = None
    if not deduped:
        note = "Нет активных поручений — все сигналы в норме."

    return TaskList(
        tasks=deduped,
        counts_by_priority=counts_priority,
        counts_by_source=counts_source,
        note=note,
    )


# ---------------------------------------------------------------------------
# source-specific task builders
# ---------------------------------------------------------------------------

def _tasks_from_agenda(agenda: Dict[str, Any]) -> Iterable[Task]:
    actions = agenda.get("actions") or []
    headline = agenda.get("headline") or "Приоритет дня"
    for idx, action in enumerate(actions):
        if not isinstance(action, str) or not action.strip():
            continue
        title = action.strip()
        priority = "high" if idx == 0 else "medium"
        yield Task(
            id=_task_id(title, "agenda"),
            title=title,
            priority=priority,
            deadline_days=_PRIORITY_DAYS[priority],
            source="agenda",
            rationale=f"Из приоритета дня: {headline}",
            suggested_owner=_AGENDA_DEFAULT_OWNER,
            tags=["повестка"],
        )


def _tasks_from_crisis(crisis: Dict[str, Any]) -> Iterable[Task]:
    alerts = crisis.get("alerts") or []
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        level = alert.get("level") or "watch"
        priority = _CRISIS_LEVEL_TO_PRIORITY.get(level, "medium")
        kind = alert.get("kind", "signal")
        vector = alert.get("vector")
        owner = _VECTOR_TO_OWNER.get(vector, "Штаб по ЧС")
        title = f"Реагирование: {alert.get('title') or kind}"
        horizon = alert.get("horizon") or ""
        rationale_parts = [alert.get("description") or "Активный кризисный сигнал."]
        if horizon:
            rationale_parts.append(f"Горизонт: {horizon}")
        yield Task(
            id=_task_id(title, "crisis"),
            title=title,
            priority=priority,
            deadline_days=_PRIORITY_DAYS[priority],
            source="crisis",
            rationale=" · ".join(rationale_parts),
            suggested_owner=owner,
            tags=["кризис", kind, level],
        )


def _tasks_from_roadmap(roadmap: Dict[str, Any]) -> Iterable[Task]:
    # Accept either the full /roadmap response or a bare Roadmap.to_dict().
    data = roadmap.get("roadmap", roadmap) if "roadmap" in roadmap else roadmap
    milestones = (data or {}).get("milestones") or []
    vector = (data or {}).get("vector", "")
    owner = _VECTOR_TO_OWNER.get(_vector_to_key(vector), _ROADMAP_DEFAULT_OWNER)

    for idx, m in enumerate(milestones):
        if not isinstance(m, dict):
            continue
        interventions = m.get("interventions") or []
        if not interventions:
            continue
        first_intervention = interventions[0]
        if not isinstance(first_intervention, str) or not first_intervention.strip():
            continue
        title = first_intervention.strip()
        # Q1 → medium, rest → low — the earliest quarter is most urgent.
        priority = "medium" if idx == 0 else "low"
        yield Task(
            id=_task_id(title, "roadmap"),
            title=title,
            priority=priority,
            deadline_days=_PRIORITY_DAYS[priority],
            source="roadmap",
            rationale=(
                f"Дорожная карта «{vector or 'вектор'}» — квартал {idx + 1}, "
                f"цель {m.get('target_level', '?')}"
            ),
            suggested_owner=owner,
            tags=["дорожная-карта", f"q{idx + 1}"],
        )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _task_id(title: str, source: str) -> str:
    basis = f"{source}:{title.strip().lower()}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def _priority_rank(priority: str) -> int:
    order = {"urgent": 4, "high": 3, "medium": 2, "low": 1}
    return order.get(priority, 0)


def _vector_to_key(vector_label: str) -> str:
    v = (vector_label or "").strip().upper()
    return {"СБ": "safety", "ТФ": "economy", "УБ": "quality", "ЧВ": "social"}.get(v, "")
