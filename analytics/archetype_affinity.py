"""Affinity 12 архетипов — насколько посты депутата близки к каждому.

Для каждого архетипа считаем средний archetype_match_score по её
постам, переводим в %, сортируем. На выход: top-12 (или меньше, если
постов нет) с процентом близости.

Используется в кабинете для блока «Образ к которому ты очень близок»:
показываем top-3 со шкалами и подсветкой текущего main-архетипа.
"""

from __future__ import annotations

from statistics import mean
from typing import Any, Dict, List


def compute_affinity(audit: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Возвращает 12 архетипов с процентом близости.

    Использует _raw_posts, если они есть в audit (сохраняются для
    downstream-анализа). Если их нет — fallback к alignment_score
    единственного архетипа.
    """
    from config.archetypes import ARCHETYPES, archetype_match_score

    raw_posts = audit.get("_raw_posts") or []
    posts_with_text = [p for p in (audit.get("_posts_text") or []) if p.get("text")]

    out: List[Dict[str, Any]] = []
    if not posts_with_text:
        # Без сырых текстов работать нечем — возвращаем шаблон с равными %
        # с поднятым main-архетипом из аудита.
        main_code = audit.get("archetype_code")
        for a in ARCHETYPES:
            score = 100 if a["code"] == main_code else 30
            out.append({
                "code":      a["code"],
                "name":      a["name"],
                "short":     a.get("short", ""),
                "affinity":  score,
                "is_main":   a["code"] == main_code,
            })
        return out

    main_code = audit.get("archetype_code")
    for a in ARCHETYPES:
        scores = [archetype_match_score(p["text"], a) for p in posts_with_text]
        avg = mean(scores) if scores else 0
        out.append({
            "code":     a["code"],
            "name":     a["name"],
            "short":    a.get("short", ""),
            "affinity": round(avg * 100, 1),
            "is_main":  a["code"] == main_code,
        })
    out.sort(key=lambda x: -x["affinity"])
    return out
