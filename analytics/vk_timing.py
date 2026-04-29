"""Анализ времени публикаций — какие дни недели и часы дают engagement.

На вход — список постов из vk_audit._fetch_recent_posts (с published_at
и likes/views/reposts). На выход — heatmap day_of_week × time_band
с агрегатом среднего engagement, а также рекомендации best_day /
best_hour / sweet_spot для UI.

Engagement = likes (взвешенно — главное что видно в UI). views/reposts
тоже учитываются как доп.факторы. На пустом списке — пустой dict
с понятным state="no_data".
"""

from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional


_DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
_BANDS = [
    ("утро",   6, 11),    # 06:00-11:59
    ("день",   12, 16),   # 12:00-16:59
    ("вечер",  17, 22),   # 17:00-22:59
    ("ночь",   23, 5),    # 23:00-05:59 (wraps)
]


def build_timing_heatmap(posts: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Строит heatmap. posts — список dict с published_at + likes."""
    posts = list(posts or [])
    if not posts:
        return {"state": "no_data"}

    # cells[day][band] = list of likes
    cells: Dict[int, Dict[str, List[int]]] = {
        d: {b[0]: [] for b in _BANDS} for d in range(7)
    }

    parsed_count = 0
    for p in posts:
        ts_raw = p.get("published_at")
        if not ts_raw:
            continue
        try:
            dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        # local hour — берём как есть из исходной TZ; для русских постов
        # обычно UTC+3, но это deterministic относительно постов.
        dow = dt.weekday()
        hour = dt.hour
        band = _band_for_hour(hour)
        likes = int(p.get("likes") or 0)
        cells[dow][band].append(likes)
        parsed_count += 1

    if parsed_count == 0:
        return {"state": "no_data"}

    # Собираем сводку по ячейкам + best_day / best_hour
    matrix: List[Dict[str, Any]] = []
    best_avg = -1.0
    best_cell = None
    by_day_avg: Dict[int, float] = {}
    by_band_avg: Dict[str, List[float]] = {b[0]: [] for b in _BANDS}

    for dow in range(7):
        day_likes_all: List[int] = []
        for band_name, _, _ in _BANDS:
            arr = cells[dow][band_name]
            avg_likes = round(mean(arr), 1) if arr else 0
            count = len(arr)
            matrix.append({
                "dow":       dow,
                "day":       _DAYS_RU[dow],
                "band":      band_name,
                "count":     count,
                "avg_likes": avg_likes,
            })
            day_likes_all.extend(arr)
            by_band_avg[band_name].extend(arr)
            if count >= 1 and avg_likes > best_avg:
                best_avg = avg_likes
                best_cell = (dow, band_name, count, avg_likes)

        by_day_avg[dow] = round(mean(day_likes_all), 1) if day_likes_all else 0

    # Лучший день — с max average likes
    best_day_idx = max(by_day_avg, key=lambda d: by_day_avg[d]) if by_day_avg else 0
    best_band = max(
        by_band_avg, key=lambda b: mean(by_band_avg[b]) if by_band_avg[b] else 0,
    ) if any(by_band_avg.values()) else _BANDS[0][0]

    return {
        "state":       "ok",
        "matrix":      matrix,         # 28 ячеек 7×4
        "days":        _DAYS_RU,
        "bands":       [b[0] for b in _BANDS],
        "best_day":    _DAYS_RU[best_day_idx],
        "best_band":   best_band,
        "best_cell":   {
            "day":       _DAYS_RU[best_cell[0]],
            "band":      best_cell[1],
            "count":     best_cell[2],
            "avg_likes": best_cell[3],
        } if best_cell else None,
        "totals":      {
            "posts_with_time": parsed_count,
            "by_day_avg":      {_DAYS_RU[k]: v for k, v in by_day_avg.items()},
        },
    }


def _band_for_hour(hour: int) -> str:
    if 6 <= hour <= 11:
        return "утро"
    if 12 <= hour <= 16:
        return "день"
    if 17 <= hour <= 22:
        return "вечер"
    return "ночь"


def heatmap_advice(heatmap: Dict[str, Any]) -> Optional[str]:
    """Короткая рекомендация по best-cell / best_day."""
    if not heatmap or heatmap.get("state") != "ok":
        return None
    bc = heatmap.get("best_cell") or {}
    if not bc:
        return None
    return (
        f"Лучшее окно — {bc.get('day')}, {bc.get('band')} "
        f"(в среднем {bc.get('avg_likes')} лайков). "
        f"Планируй важные посты сюда."
    )
