"""Недельные миссии для депутата — превращаем метрики в action-list.

Из существующих audit/timing/rating строим 3-5 конкретных задач на
неделю, каждая с видимым «приростом» (заявленным эффектом). Без LLM —
deterministic эвристика, чтобы вычислялось мгновенно и попадало в
кэш кабинета.

Каждая миссия — словарь:
  code:    ID для UI (frequency / alignment / engagement / heatmap / story)
  title:   что сделать (императив)
  why:     зачем — заявленный прирост («рейтинг +0.3»)
  hint:    конкретный приём
  effort:  S / M / L (примерная нагрузка)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


_TARGET_PP_WEEK = 3.0
_TARGET_LIKES   = 50.0
_TARGET_ALIGN   = 70.0


def build_weekly_missions(
    audit: Dict[str, Any],
    archetype: Dict[str, Any],
    timing: Optional[Dict[str, Any]] = None,
    rating_value: float = 0,
) -> List[Dict[str, Any]]:
    """Собираем 3-5 миссий по приоритету (worst-first)."""
    missions: List[Dict[str, Any]] = []
    metrics = audit.get("metrics") or {}
    pp_week = float(metrics.get("posts_per_week") or 0)
    avg_likes = float(metrics.get("avg_likes") or 0)
    avg_length = float(metrics.get("avg_length") or 0)
    align = float(audit.get("alignment_score") or 0)
    arch_name = archetype.get("name") or "—"
    do_first = (archetype.get("do") or [""])[0]

    # 1. Регулярность — самое больное, ставим первым если просело
    if pp_week < _TARGET_PP_WEEK:
        gap = max(0, int(_TARGET_PP_WEEK - pp_week))
        plus = round(((_TARGET_PP_WEEK - pp_week) / _TARGET_PP_WEEK) * 0.35 * 5, 1)
        missions.append({
            "code":   "frequency",
            "title":  f"Опубликовать ещё {gap} {_plural(gap)} на этой неделе",
            "why":    f"Рейтинг +{plus} ⭐ за выполнение цели регулярности",
            "hint":   "Проще всего — короткий пост-репортаж по жалобе или субботнему обходу.",
            "effort": "M",
        })

    # 2. Соответствие архетипу
    if align < _TARGET_ALIGN:
        plus = round(((_TARGET_ALIGN - align) / _TARGET_ALIGN) * 0.4 * 5, 1)
        missions.append({
            "code":   "alignment",
            "title":  f"1 пост строго в голосе «{arch_name}»",
            "why":    f"Соответствие архетипу +{int(_TARGET_ALIGN - align)}%, рейтинг +{plus} ⭐",
            "hint":   f"Возьми приём: {do_first.lower() if do_first else 'история из округа'}",
            "effort": "S",
        })

    # 3. Engagement — фото / истории
    if avg_likes < 10:
        missions.append({
            "code":   "engagement",
            "title":  "Добавь фото к следующему посту",
            "why":    "Посты с фото берут в среднем +40% лайков",
            "hint":   "1 фото с места события, естественный свет, ты в кадре + контекст.",
            "effort": "S",
        })

    # 4. Heatmap-based — лучшее окно
    if timing and timing.get("heatmap", {}).get("state") == "ok":
        bc = timing["heatmap"].get("best_cell") or {}
        if bc.get("avg_likes", 0) > 0:
            missions.append({
                "code":   "heatmap",
                "title":  f"Главный пост недели — {bc.get('day')}, {bc.get('band')}",
                "why":    f"Это твоё лучшее окно — в среднем {bc.get('avg_likes')} лайков",
                "hint":   "Запланируй заранее: тема, фото, текст готовы за день до.",
                "effort": "S",
            })

    # 5. Длина текстов
    if avg_length and avg_length < 150:
        missions.append({
            "code":   "length",
            "title":  "Сделай 1 содержательный пост на 600+ знаков",
            "why":    "Алгоритм VK выше показывает посты с фактурой — больше охвата",
            "hint":   "Структура: история → цифра/факт → конкретный шаг и срок.",
            "effort": "M",
        })

    # 6. Архетип-история (общий, если миссий мало)
    if len(missions) < 3 and archetype.get("sample_post"):
        missions.append({
            "code":   "story",
            "title":  "История из округа: что увидела, что сделала",
            "why":    "Истории — самый сильный жанр для архетипа доверия",
            "hint":   archetype.get("sample_post", "")[:160] + "…",
            "effort": "M",
        })

    return missions[:5]


def _plural(n: int) -> str:
    """пост / поста / постов"""
    n = abs(n)
    if 11 <= (n % 100) <= 14:
        return "постов"
    last = n % 10
    if last == 1:
        return "пост"
    if 2 <= last <= 4:
        return "поста"
    return "постов"
