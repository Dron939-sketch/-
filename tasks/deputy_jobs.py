"""Сервисный слой для авто-генерации тем депутатов.

Нужен, чтобы две точки запуска — HTTP-роут (`POST
/api/city/{name}/deputy-topics/auto-generate`) и шедулер
(`_deputy_topics_loop`) — делили общую логику без HTTP-зависимостей.

Ничего связанного с FastAPI/Pydantic — только async-вызовы
db.* helpers, чтобы можно было вызывать из background task'а.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


async def run_auto_generate(
    *,
    city_name: str,
    city_id: int,
    hours: int = 24,
    deadline_days: int = 5,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Сгенерировать темы для одного города.

    Steps:
      1. news_window(city_id, hours) — поток жалоб за окно.
      2. latest_metrics(city_id) — текущий снимок векторов.
      3. generate_topics_from_signals(...) — pure-функция генератора.
      4. dry_run=True → вернуть кандидатов без записи.
      5. dry_run=False → upsert + auto-assign + dedup по title.

    Возврат — тот же dict-формат, что отдаёт HTTP-роут, чтобы оба
    consumer'а не расходились в схеме ответа.
    """
    from analytics.deputy_topic_generator import (
        auto_assign_deputies,
        generate_topics_from_signals,
    )
    from db import deputy_queries as q
    from db.queries import latest_metrics, news_window

    news_items = await news_window(city_id, hours=hours)
    metric_row = await latest_metrics(city_id)
    metrics: Optional[Dict[str, Any]] = None
    if metric_row is not None:
        metrics = {
            "sb":  metric_row.get("sb"),
            "tf":  metric_row.get("tf"),
            "ub":  metric_row.get("ub"),
            "chv": metric_row.get("chv"),
        }

    candidates = generate_topics_from_signals(
        news=news_items,
        metrics=metrics,
        deadline_days=deadline_days,
    )

    if dry_run:
        return {
            "city": city_name,
            "dry_run": True,
            "found_signals": {
                "news_items_in_window": len(news_items),
                "metrics_present": metrics is not None,
            },
            "candidates": candidates,
        }

    # Запись + auto-assign + dedup по title против active topics
    deputies = await q.list_deputies(city_id)
    active_titles = {
        (t.get("title") or "").strip().lower()
        for t in await q.list_topics(city_id, status="active")
    }
    created: List[dict] = []
    skipped_duplicate = 0
    for cand in candidates:
        if cand["title"].strip().lower() in active_titles:
            skipped_duplicate += 1
            continue
        body = dict(cand)
        body.pop("target_sectors", None)
        body.pop("external_id", None)
        assignees = auto_assign_deputies(cand, deputies)
        body["assignees"] = assignees
        topic_id = await q.insert_topic(city_id, body)
        if topic_id is not None:
            created.append({
                "topic_id": topic_id,
                "title": cand["title"],
                "priority": cand["priority"],
                "source": cand["source"],
                "assigned_count": len(assignees),
            })

    return {
        "city": city_name,
        "dry_run": False,
        "created": created,
        "skipped_duplicate": skipped_duplicate,
        "failed_to_persist": len(candidates) - len(created) - skipped_duplicate,
    }
