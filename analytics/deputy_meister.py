"""Алгоритм Мейстера для депутата — 4-векторная модель личного бренда.

Адаптация городской 4-векторной модели (СБ/ТФ/УБ/ЧВ) под депутата.
4 вектора депутатского бренда:
  CO  — Соответствие (Coherence)     — голос совпадает с архетипом
  RE  — Регулярность (Regularity)    — частота публикаций
  EN  — Вовлечение (Engagement)       — лайки/просмотры/комменты
  RP  — Отзывчивость (Responsiveness) — ответы на жалобы / время реакции

Каждый вектор по шкале 0..6 (как у Мейстера). Сумма + связи между
ними → personal Meister index. Прогноз — простая линейная экстраполяция
на 4 недели вперёд от текущих метрик с учётом миссий: если миссия
выполнена, соответствующий вектор подрастёт.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# Целевые значения для шкалы 0..6 (когда вектор = 6)
_TARGET_PP_WEEK = 3.0     # 3 поста / неделю = 6
_TARGET_LIKES   = 50.0    # 50 лайков в среднем = 6
_TARGET_ALIGN   = 100.0   # 100% соответствие = 6
_TARGET_REPLY   = 80.0    # 80% ответов на жалобы = 6 (на demo — синтетика)


VECTORS = [
    {"code": "CO", "emoji": "🎭", "name": "Голос",   "color": "#5EA8FF",
     "what":  "Звучит ли архетип — насколько посты совпадают с твоим голосом."},
    {"code": "RE", "emoji": "📅", "name": "Ритм",    "color": "#FFD89B",
     "what":  "Постоянство присутствия в ленте — посты в неделю."},
    {"code": "EN", "emoji": "❤",  "name": "Отклик",  "color": "#B0F0C0",
     "what":  "Реакция аудитории — лайки, просмотры, комментарии."},
    {"code": "RP", "emoji": "💬", "name": "Связь",   "color": "#FF9F4A",
     "what":  "Скорость и доля ответов на обращения жителей."},
]


def build_meister(
    audit: Dict[str, Any],
    rating_factors: Dict[str, Any],
    missions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Считаем 4 вектора (0..6) и прогноз на 4 недели."""
    metrics = audit.get("metrics") or {}
    align    = float(audit.get("alignment_score") or 0)
    pp_week  = float(metrics.get("posts_per_week") or 0)
    avg_likes = float(metrics.get("avg_likes") or 0)

    co = round(min(align / _TARGET_ALIGN, 1.0) * 6, 1)
    re_ = round(min(pp_week / _TARGET_PP_WEEK, 1.0) * 6, 1)
    en = round(min(avg_likes / _TARGET_LIKES, 1.0) * 6, 1)
    # Отзывчивость — на demo константа с синтетикой; в real-mode будет
    # доля ответов на комменты ≤ 24ч из VK API.
    rp_pct = float(rating_factors.get("responsiveness") or 35)
    rp = round(min(rp_pct / _TARGET_REPLY, 1.0) * 6, 1)

    current = [
        {**VECTORS[0], "value": co, "raw": round(align, 1), "unit": "%"},
        {**VECTORS[1], "value": re_, "raw": round(pp_week, 1), "unit": "/нед"},
        {**VECTORS[2], "value": en, "raw": round(avg_likes), "unit": "ср.лайков"},
        {**VECTORS[3], "value": rp, "raw": round(rp_pct), "unit": "% ответов"},
    ]

    # Прогноз: если миссии есть — каждый вектор подтянется в сторону
    # цели на 0.5..1.0 за неделю. Если миссий нет — ничего не растёт.
    forecast = _forecast(current, missions or [])
    composite_now    = round(sum(v["value"] for v in current) / 4, 2)
    composite_4w     = round(sum(p["value"] for p in forecast[-1]) / 4, 2)

    summary = _make_summary(current, forecast)

    return {
        "current":         current,
        "forecast":        forecast,
        "composite_now":   composite_now,
        "composite_4w":    composite_4w,
        "delta":           round(composite_4w - composite_now, 2),
        "summary":         summary,
    }


def _forecast(
    current: List[Dict[str, Any]], missions: List[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    """4 недели вперёд. Каждая неделя — список из 4 векторов."""
    # Какие миссии бьют по каким векторам
    mission_codes = {m.get("code") for m in missions if m.get("code")}
    impact = {
        "CO": 0.6 if "alignment" in mission_codes else 0.0,
        "RE": 0.7 if "frequency"  in mission_codes else 0.0,
        "EN": 0.4 if "engagement" in mission_codes else 0.0,
        "RP": 0.3,  # допускаем что отзывчивость постепенно растёт фоном
    }
    weeks: List[List[Dict[str, Any]]] = []
    prev = [dict(v) for v in current]
    for w in range(1, 5):
        nxt: List[Dict[str, Any]] = []
        for v in prev:
            growth = impact.get(v["code"], 0.0)
            new_val = min(6, round(v["value"] + growth, 2))
            nxt.append({**v, "value": new_val, "week": w})
        weeks.append(nxt)
        prev = nxt
    return weeks


def _make_summary(
    current: List[Dict[str, Any]], forecast: List[List[Dict[str, Any]]],
) -> str:
    """Короткий вывод: что вырастет / что просядет / общий тренд."""
    if not forecast:
        return "Прогноз недоступен."
    last = forecast[-1]
    deltas = [(c["code"], c["name"], last[i]["value"] - c["value"]) for i, c in enumerate(current)]
    deltas.sort(key=lambda x: -x[2])
    biggest = deltas[0]
    if biggest[2] <= 0.1:
        return ("Текущий курс — без изменений. Возьми хотя бы одну миссию недели, "
                "чтобы график пошёл вверх.")
    if biggest[2] >= 1.5:
        return f"Самый сильный рост — «{biggest[1]}» (+{biggest[2]:.1f}). Удержи темп."
    return f"Главный рывок — «{biggest[1]}» (+{biggest[2]:.1f}) за 4 недели."
