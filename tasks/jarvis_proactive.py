"""Проактивная проверка состояния города для Джарвиса.

Раз в N минут scheduler вызывает `check_city(city_name)` — он смотрит
кризис-радар + метрики + тренды и решает, нужен ли алерт. Дедупликация
по (city_id, key) на стороне БД: один и тот же триггер каждые 15 минут
не плодит дублей, просто обновляет last_triggered_at.

Все источники fail-safe: если кризис-роут или метрики недоступны —
выходим без записи, не падаем.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Пороги триггеров — те же, что в analytics/deputy_topic_generator.
_METRIC_LOW = 3.0
_METRIC_CRITICAL = 2.5

_VECTOR_LABELS = {
    "sb": "Социально-бытовой",
    "tf": "Транспортно-финансовый",
    "ub": "Уровень благополучия",
    "chv": "Человек-Власть",
}


async def check_city(city_name: str) -> List[Dict[str, Any]]:
    """Прогнать все проверки для одного города. Возвращает список
    upsert'нутых alert id (для логов)."""
    from db.jarvis_alerts_queries import upsert_alert
    from db.queries import latest_metrics, metrics_trend_7d
    from db.seed import city_id_by_name

    cid: Optional[int] = await city_id_by_name(city_name)
    if cid is None:
        return []

    upserts: List[Dict[str, Any]] = []

    # 1. Кризис-радар
    try:
        from api.routes import city_crisis  # type: ignore
        crisis = await city_crisis(city_name)
        level = (crisis or {}).get("level") or (crisis or {}).get("status")
        alerts = (crisis or {}).get("alerts") or []
        if level in {"high", "critical"} and alerts:
            top_titles = [
                (a.get("title") if isinstance(a, dict) else str(a)) for a in alerts[:3]
            ]
            row_id = await upsert_alert(
                city_id=cid, key="crisis_high",
                level="critical" if level == "critical" else "warning",
                title=f"Кризис-радар: {len(alerts)} алертов",
                summary="Топ: " + "; ".join(top_titles),
                payload={"city": city_name, "level": level, "top": top_titles},
                ttl_hours=12,
            )
            if row_id:
                upserts.append({"id": row_id, "key": "crisis_high"})
    except Exception:  # noqa: BLE001
        logger.debug("crisis check failed for %s", city_name, exc_info=False)

    # 2. Просевшие метрики
    try:
        m = await latest_metrics(cid)
        if m:
            for code, label in _VECTOR_LABELS.items():
                v = m.get(code)
                if v is None:
                    continue
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    continue
                if fv >= _METRIC_LOW:
                    continue
                is_critical = fv < _METRIC_CRITICAL
                row_id = await upsert_alert(
                    city_id=cid,
                    key=f"metric_{code}_low",
                    level="critical" if is_critical else "warning",
                    title=f"Просел вектор «{label}»",
                    summary=f"Текущее значение {fv:.1f} из 6 ({'критически' if is_critical else 'ниже'} нормы)",
                    payload={"vector": code, "value": fv, "threshold": _METRIC_LOW},
                    ttl_hours=12,
                )
                if row_id:
                    upserts.append({"id": row_id, "key": f"metric_{code}_low"})
    except Exception:  # noqa: BLE001
        logger.debug("metric check failed for %s", city_name, exc_info=False)

    # 3. Тренды — резкое падение более чем на 1.0 за 7 дней
    try:
        t = await metrics_trend_7d(cid)
        if t:
            for code, label in _VECTOR_LABELS.items():
                v = t.get(code)
                if v is None:
                    continue
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    continue
                if fv > -0.7:
                    continue  # либо рост, либо незначительное падение
                row_id = await upsert_alert(
                    city_id=cid,
                    key=f"trend_{code}_drop",
                    level="warning",
                    title=f"Резкое падение «{label}» за неделю",
                    summary=f"Δ за 7 дней: {fv:+.1f}",
                    payload={"vector": code, "delta_7d": fv},
                    ttl_hours=24,
                )
                if row_id:
                    upserts.append({"id": row_id, "key": f"trend_{code}_drop"})
    except Exception:  # noqa: BLE001
        logger.debug("trend check failed for %s", city_name, exc_info=False)

    return upserts


async def cleanup_expired_alerts() -> int:
    from db.jarvis_alerts_queries import cleanup_expired
    return await cleanup_expired()
