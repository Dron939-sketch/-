"""Авто-генерация тем для Совета депутатов из метрик и потока жалоб.

Соединяет три раздельных модуля в один pipeline:
  1. снимок городских векторов (`metrics`) — сигнал «вектор провален»
  2. поток новостей и жалоб (`news`) — сигнал «концентрация недовольства
     в категории»
  3. реестр депутатов (`deputies` + `DeputyAgendaManager`) — кому это
     закрывать постами

Чистая функция: на вход — данные, на выход — список candidate'ов в
формате, который понимает `db.deputy_queries.insert_topic()`. Никаких
обращений к БД, чтобы было удобно тестировать и dry-run'ить из роута.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from collectors.base import CollectedItem


# ---------------------------------------------------------------------------
# Маппинг категории новостей → сектор депутата
# (имена секторов совпадают с config/deputies.py)
# ---------------------------------------------------------------------------

CATEGORY_TO_SECTORS: Dict[str, List[str]] = {
    "utilities":   ["ЖКХ"],
    "incidents":   ["ЖКХ", "благоустройство"],
    "complaints":  ["благоустройство", "общая_повестка"],
    "transport":   ["транспорт"],
    "healthcare":  ["здравоохранение"],
    "education":   ["образование"],
    "social":      ["соцзащита"],
    "culture":     ["культура"],
    "sport":       ["спорт"],
    "youth":       ["молодёжь"],
}

# Человекочитаемое название категории для заголовков тем.
CATEGORY_LABELS: Dict[str, str] = {
    "utilities":  "ЖКХ",
    "incidents":  "Происшествия и безопасность",
    "complaints": "Жалобы горожан",
    "transport":  "Транспорт",
    "healthcare": "Здравоохранение",
    "education":  "Образование",
    "social":     "Социальная политика",
    "culture":    "Культура",
    "sport":      "Спорт",
    "youth":      "Молодёжь",
}

# Минимум жалоб одной категории за окно, чтобы поднять тему.
MIN_COMPLAINTS_FOR_TOPIC = 3

# Минимум среднего negative-сентимента, чтобы засчитать «всплеск
# недовольства» (если у новостей нет sentiment'а — учитываем только
# количество).
NEGATIVE_SENTIMENT_THRESHOLD = -0.2

# Пороги для метрик (1..6 шкала). Срабатывают, когда вектор «провален».
METRIC_LOW_THRESHOLD = 3.0
METRIC_CRITICAL_THRESHOLD = 2.5

# Маппинг кода метрики → (вектор, сектор-кандидат, тон, заголовок).
METRIC_TOPIC_MAP: Dict[str, Dict[str, Any]] = {
    "ub": {
        "label": "Уровень благополучия (УБ)",
        "sectors": ["соцзащита", "ЖКХ", "благоустройство"],
        "tone": "explanatory",
        "title_low": "Снижение уровня благополучия — нужна разъяснительная работа",
        "title_critical": "Критическое падение уровня благополучия — срочная коммуникация",
    },
    "chv": {
        "label": "Человек-Власть (ЧВ)",
        "sectors": ["общая_повестка", "соцзащита"],
        "tone": "protective",
        "title_low": "Снижение доверия граждан к власти — защитная коммуникация",
        "title_critical": "Критическое падение доверия — экстренная разъяснительная работа",
    },
    "sb": {
        "label": "Социально-бытовой вектор (СБ)",
        "sectors": ["соцзащита", "благоустройство", "ЖКХ"],
        "tone": "protective",
        "title_low": "Социально-бытовые проблемы требуют внимания",
        "title_critical": "Критическое ухудшение социально-бытовой обстановки",
    },
    "tf": {
        "label": "Транспортно-финансовый вектор (ТФ)",
        "sectors": ["транспорт", "экономика"],
        "tone": "explanatory",
        "title_low": "Экономические/транспортные сложности — разъяснить решения",
        "title_critical": "Серьёзные экономические трудности — поддерживающая коммуникация",
    },
}


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------

def _is_negative(item: CollectedItem) -> bool:
    """Жалоба или негативная новость? Идём по категории + sentiment'у."""
    cat = (item.category or "").lower()
    if cat in {"complaints", "incidents", "utilities"}:
        return True
    sentiment = None
    if item.enrichment:
        sentiment = item.enrichment.get("sentiment")
    if sentiment is not None and float(sentiment) <= NEGATIVE_SENTIMENT_THRESHOLD:
        return True
    return False


def _topic_external_id(prefix: str, key: str, day: datetime) -> str:
    """Стабильный id (prefix + ключ + дата-день), чтобы не плодить дубли."""
    basis = f"{prefix}:{key}:{day:%Y-%m-%d}"
    digest = hashlib.md5(basis.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def _top_titles(items: Iterable[CollectedItem], limit: int = 3) -> List[str]:
    """Достаём короткие заголовки самых заметных жалоб для talking_points."""
    seen: List[str] = []
    for it in items:
        title = (it.title or "").strip()
        if not title or title in seen:
            continue
        seen.append(title[:140])
        if len(seen) >= limit:
            break
    return seen


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_topics_from_signals(
    *,
    news: List[CollectedItem],
    metrics: Optional[Dict[str, Any]] = None,
    deadline_days: int = 5,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Собрать список candidate'ов в `deputy_topics` для записи в БД.

    Параметры:
      news     — новости/жалобы за окно (например, последние 24 часа).
      metrics  — снимок векторов (`{"sb":..,"tf":..,"ub":..,"chv":..}`),
                 None если БД пустая.
      deadline_days — сколько дней дать депутатам на покрытие темы.
      now      — точка отсчёта (для детерминированных тестов).

    Возвращает: список dict, каждый совместим с `insert_topic(..)` плюс
    дополнительное поле `target_sectors` для дальнейшего auto-assign.
    """
    now = now or datetime.now(tz=timezone.utc)
    deadline = now + timedelta(days=deadline_days)
    candidates: List[Dict[str, Any]] = []

    # ----- 1. Кластеры жалоб по категории -----
    by_category: Dict[str, List[CollectedItem]] = defaultdict(list)
    for it in news:
        if not _is_negative(it):
            continue
        cat = (it.category or "complaints").lower()
        if cat not in CATEGORY_TO_SECTORS:
            cat = "complaints"
        by_category[cat].append(it)

    for cat, items in by_category.items():
        if len(items) < MIN_COMPLAINTS_FOR_TOPIC:
            continue
        sectors = CATEGORY_TO_SECTORS[cat]
        label = CATEGORY_LABELS.get(cat, cat)
        top_titles = _top_titles(items, limit=3)
        title = f"{label}: всплеск жалоб ({len(items)} сигналов)"
        priority = "high" if len(items) >= 6 else "medium"
        candidates.append({
            "external_id": _topic_external_id("complaints", cat, now),
            "title": title,
            "description": (
                f"За последние сутки — {len(items)} сигналов в категории «{label}». "
                f"Депутатам профильных секторов нужно отработать тему публикациями: "
                f"объяснить причину, рассказать о предпринятых мерах, обозначить сроки."
            ),
            "priority": priority,
            "target_tone": "explanatory",
            "key_messages": [
                f"Власть в курсе ситуации в сфере «{label}» и работает над решением",
                "Конкретные действия и сроки — в публичных каналах",
            ],
            "talking_points": top_titles,
            "target_audience": ["all"],
            "deadline": deadline,
            "required_posts": 5 if priority == "high" else 3,
            "status": "active",
            "source": "auto_complaints",
            "target_sectors": sectors,  # подсказка auto-assign'у
        })

    # ----- 2. Просевшие метрики -----
    if metrics:
        for code, cfg in METRIC_TOPIC_MAP.items():
            value = metrics.get(code)
            if value is None:
                continue
            try:
                v = float(value)
            except (TypeError, ValueError):
                continue
            if v >= METRIC_LOW_THRESHOLD:
                continue
            is_critical = v < METRIC_CRITICAL_THRESHOLD
            title = cfg["title_critical"] if is_critical else cfg["title_low"]
            priority = "critical" if is_critical else "high"
            candidates.append({
                "external_id": _topic_external_id("metric", code, now),
                "title": title,
                "description": (
                    f"Текущий показатель «{cfg['label']}» = {v:.1f}/6 "
                    f"({'критически ниже' if is_critical else 'ниже'} нормы 3.0). "
                    f"Профильные депутаты выводят разъяснительные публикации по принятым "
                    f"и планируемым мерам."
                ),
                "priority": priority,
                "target_tone": cfg["tone"],
                "key_messages": [
                    f"Показатель «{cfg['label']}» снизился — администрация знает о проблеме",
                    "Принимаемые меры публично обсуждаются и контролируются Советом депутатов",
                ],
                "talking_points": [
                    f"Текущий уровень: {v:.1f}/6 (норма ≥ 3.0)",
                ],
                "target_audience": ["all"],
                "deadline": deadline,
                "required_posts": 7 if is_critical else 5,
                "status": "active",
                "source": "auto_metrics",
                "target_sectors": cfg["sectors"],
            })

    return candidates


def auto_assign_deputies(
    candidate: Dict[str, Any],
    deputies: List[Dict[str, Any]],
    *,
    max_assignees: int = 5,
) -> List[int]:
    """Подобрать deputy.id'ы для темы по target_sectors + role.

    Совместимо с тем, что отдаёт `db.deputy_queries.list_deputies()` —
    каждый депутат это dict с полями `id`, `role`, `sectors` (list[str]),
    `district` (str), `enabled` (bool).

    Логика:
      1. На critical/high priority обязательно подключаем всех
         руководителей Совета (role=speaker).
      2. Депутаты, в чьих секторах есть пересечение с `target_sectors`.
      3. Срез до max_assignees.
    """
    target = {s.lower() for s in (candidate.get("target_sectors") or [])}
    priority = candidate.get("priority", "medium")
    chosen: List[int] = []

    # 1. Speakers на high/critical
    if priority in ("critical", "high"):
        for d in deputies:
            if not d.get("enabled", True):
                continue
            if d.get("role") == "speaker":
                chosen.append(int(d["id"]))

    # 2. По секторам
    for d in deputies:
        if not d.get("enabled", True):
            continue
        did = int(d["id"])
        if did in chosen:
            continue
        d_sectors = {s.lower() for s in (d.get("sectors") or [])}
        if target and d_sectors & target:
            chosen.append(did)

    return chosen[:max_assignees]
