"""What-if симулятор для депутата.

Интерактивный «Что если…»: пользователь крутит ползунки (постов в
неделю, средняя длина, ответы на комменты) — видит как меняется
прогнозный рейтинг и 4 вектора.

Расчёт deterministic, без LLM. Использует те же формулы что
deputy_meister + composite rating (вес 0.4 / 0.35 / 0.25).
"""

from __future__ import annotations

from typing import Any, Dict, Optional


_PARAMS = {
    "posts_per_week": {
        "label":   "Постов в неделю",
        "min":     0, "max": 7, "step": 1,
        "default": 1,
        "unit":    "/нед",
        "axis":    "RE",
    },
    "alignment_pct": {
        "label":   "Соответствие архетипу",
        "min":     0, "max": 100, "step": 5,
        "default": 50,
        "unit":    "%",
        "axis":    "CO",
    },
    "avg_likes": {
        "label":   "Средние лайки",
        "min":     0, "max": 100, "step": 5,
        "default": 10,
        "unit":    "лайков",
        "axis":    "EN",
    },
    "reply_rate": {
        "label":   "Ответы на жалобы",
        "min":     0, "max": 100, "step": 10,
        "default": 35,
        "unit":    "%",
        "axis":    "RP",
    },
}


def params_meta() -> Dict[str, Any]:
    """Описание ползунков для UI."""
    return {"params": _PARAMS}


def simulate(
    posts_per_week: float = 1,
    alignment_pct: float = 50,
    avg_likes:     float = 10,
    reply_rate:    float = 35,
) -> Dict[str, Any]:
    """Прогноз 4 векторов и composite-рейтинга по 4 ползункам."""
    posts_per_week = max(0, min(7, float(posts_per_week)))
    alignment_pct  = max(0, min(100, float(alignment_pct)))
    avg_likes      = max(0, min(100, float(avg_likes)))
    reply_rate     = max(0, min(100, float(reply_rate)))

    co = round(min(alignment_pct / 100.0, 1.0) * 6, 1)
    re_ = round(min(posts_per_week / 3.0, 1.0) * 6, 1)
    en = round(min(avg_likes / 50.0, 1.0) * 6, 1)
    rp = round(min(reply_rate / 80.0, 1.0) * 6, 1)

    # Composite — как в _build_deputy_cabinet
    rating_align    = min(alignment_pct / 100, 1.0)
    rating_freq     = min(posts_per_week / 3.0, 1.0)
    rating_engage   = min(avg_likes / 50.0, 1.0)
    rating_value    = round((rating_align * 0.4 + rating_freq * 0.35
                             + rating_engage * 0.25) * 5, 1)

    vectors = [
        {"code": "CO", "name": "Соответствие", "value": co},
        {"code": "RE", "name": "Регулярность", "value": re_},
        {"code": "EN", "name": "Вовлечение",   "value": en},
        {"code": "RP", "name": "Отзывчивость", "value": rp},
    ]
    composite = round(sum(v["value"] for v in vectors) / 4, 2)

    return {
        "vectors":   vectors,
        "rating":    rating_value,
        "composite": composite,
        "input": {
            "posts_per_week": posts_per_week,
            "alignment_pct":  alignment_pct,
            "avg_likes":      avg_likes,
            "reply_rate":     reply_rate,
        },
    }


def from_audit(audit: Dict[str, Any], reply_rate: Optional[float] = None) -> Dict[str, Any]:
    """Стартовые значения ползунков из текущего аудита."""
    metrics = audit.get("metrics") or {}
    return {
        "posts_per_week": float(metrics.get("posts_per_week") or 0),
        "alignment_pct":  float(audit.get("alignment_score") or 0),
        "avg_likes":      float(metrics.get("avg_likes") or 0),
        "reply_rate":     reply_rate if reply_rate is not None else 35,
    }
