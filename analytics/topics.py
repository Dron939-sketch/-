"""Topic intelligence (ТЗ §8, MVP adapter).

Groups news items into 7 keyword-defined topics and rolls up per-topic
stats (count, sentiment, trend vs previous week, top titles by severity).
Pure / no DB; the caller fetches items from news_window and hands them in.

Topic seeds below are hand-tuned for SE Moscow Oblast vocabulary. Each
item is assigned to the single topic with the most keyword matches;
ties broken by insertion order. Items matching nothing land in "other".

The legacy `opinion_intelligence.py` (networkx graphs + TF-IDF + DBSCAN
clustering for ЛОМ + radicalisation detection) is out of scope for the
MVP — keyword topics give a transparent view of "what's being discussed"
without sklearn or training data. The influence / radicalisation path
can come later when we have sufficient labelled history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


# Topic → list of keywords (lower-case, substring-match on title + content).
_TOPIC_SEEDS: Dict[str, Tuple[str, ...]] = {
    "transport":  ("дорог", "автобус", "трамв", "троллейб", "маршрут",
                   "пробк", "ремонт дорог", "тротуар", "парков", "трансп"),
    "utilities":  ("жкх", "тепл", "отоплен", "вод", "канализ",
                   "электр", "свет на", "авар", "коммун", "мусор", "отход"),
    "safety":     ("полици", "происшеств", "инцидент", "пожар",
                   "погиб", "ранен", "драк", "кража", "мошенн", "безопасн"),
    "culture":    ("фестивал", "выставк", "театр", "концерт", "музей",
                   "культур", "праздник", "день город", "экскурс"),
    "education":  ("школ", "гимназ", "лице", "детск сад", "детсад",
                   "университ", "колледж", "учащ", "учител", "учеб"),
    "economy":    ("бизнес", "предприн", "инвест", "завод", "фабри",
                   "производ", "рабоч мест", "зарплат", "налог", "мсп"),
    "social":     ("обращ", "жалоб", "волонтёр", "волонтер", "благотвор",
                   "пожил", "ветеран", "семь", "многодет", "поддержк"),
}

_MIN_SCORE_FOR_MATCH = 1      # need at least 1 keyword hit to tag a topic
_OTHER = "other"

_TOPIC_LABELS = {
    "transport":  "Транспорт",
    "utilities":  "ЖКХ",
    "safety":     "Безопасность",
    "culture":    "Культура",
    "education":  "Образование",
    "economy":    "Экономика",
    "social":     "Социальное",
    "other":      "Прочее",
}


@dataclass
class TopicRow:
    key: str
    label: str
    count: int
    count_prior: int              # same-sized window 7-14d ago (for trend)
    avg_sentiment: Optional[float]
    max_severity: Optional[float]
    trend: str                    # up | down | flat
    trend_ratio: Optional[float]  # (count - prior) / max(prior, 1); None when prior=0
    top_titles: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        def _r(v: Optional[float]) -> Optional[float]:
            return round(v, 3) if v is not None else None

        return {
            "key": self.key,
            "label": self.label,
            "count": int(self.count),
            "count_prior": int(self.count_prior),
            "avg_sentiment": _r(self.avg_sentiment),
            "max_severity": round(self.max_severity, 2) if self.max_severity is not None else None,
            "trend": self.trend,
            "trend_ratio": _r(self.trend_ratio),
            "top_titles": self.top_titles,
        }


@dataclass
class TopicReport:
    total_current: int
    total_prior: int
    topics: List[TopicRow]
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_current": self.total_current,
            "total_prior": self.total_prior,
            "topics": [t.to_dict() for t in self.topics],
            "note": self.note,
        }


def classify_item(item: Dict[str, Any]) -> str:
    """Return the single best-matching topic key for a news item."""
    text = (str(item.get("title") or "") + " " + str(item.get("content") or "")).lower()
    if not text.strip():
        return _OTHER
    best_key = _OTHER
    best_score = 0
    for key, keywords in _TOPIC_SEEDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_key = key
    if best_score < _MIN_SCORE_FOR_MATCH:
        return _OTHER
    return best_key


def analyze(
    current_window: Optional[Iterable[Dict[str, Any]]] = None,
    prior_window: Optional[Iterable[Dict[str, Any]]] = None,
    *,
    top_titles_per_topic: int = 3,
) -> TopicReport:
    """Roll up news into topic buckets with per-bucket stats.

    `current_window` and `prior_window` must be same-sized time slices
    (e.g. last 7 days vs 7-14 days ago). Both are lists of dicts with
    optional title / content / sentiment / severity / url / category /
    published_at keys — all fail-safe.
    """
    current = list(current_window or [])
    prior = list(prior_window or [])

    current_by_topic: Dict[str, List[Dict[str, Any]]] = {}
    for item in current:
        key = classify_item(item)
        current_by_topic.setdefault(key, []).append(item)

    prior_counts: Dict[str, int] = {}
    for item in prior:
        key = classify_item(item)
        prior_counts[key] = prior_counts.get(key, 0) + 1

    topics: List[TopicRow] = []
    # Include topics that have data in either window.
    seen_keys: List[str] = []
    for key in list(_TOPIC_SEEDS.keys()) + [_OTHER]:
        if key in current_by_topic or key in prior_counts:
            seen_keys.append(key)

    for key in seen_keys:
        items = current_by_topic.get(key, [])
        count = len(items)
        count_prior = prior_counts.get(key, 0)

        sentiments = [
            _to_float(it.get("sentiment"))
            for it in items
            if _to_float(it.get("sentiment")) is not None
        ]
        severities = [
            _to_float(it.get("severity"))
            for it in items
            if _to_float(it.get("severity")) is not None
        ]

        avg_sent = sum(sentiments) / len(sentiments) if sentiments else None
        max_sev = max(severities) if severities else None

        trend, trend_ratio = _trend_for(count, count_prior)

        # Top titles sorted by severity desc (nones last), then by -sentiment.
        items_sorted = sorted(
            items,
            key=lambda it: (
                -(_to_float(it.get("severity")) or 0.0),
                _to_float(it.get("sentiment")) or 0.0,
            ),
        )
        top_titles = []
        for it in items_sorted[:top_titles_per_topic]:
            top_titles.append(
                {
                    "title": (str(it.get("title") or "(без заголовка)"))[:200],
                    "url": it.get("url"),
                    "sentiment": _to_float(it.get("sentiment")),
                    "severity":  _to_float(it.get("severity")),
                }
            )

        topics.append(
            TopicRow(
                key=key,
                label=_TOPIC_LABELS.get(key, key),
                count=count,
                count_prior=count_prior,
                avg_sentiment=avg_sent,
                max_severity=max_sev,
                trend=trend,
                trend_ratio=trend_ratio,
                top_titles=top_titles,
            )
        )

    # Sort by count desc — the busiest topic rises to top.
    topics.sort(key=lambda t: t.count, reverse=True)

    note = None
    if not current and not prior:
        note = "Нет новостей в окне — подождите первого цикла сбора."

    return TopicReport(
        total_current=len(current),
        total_prior=len(prior),
        topics=topics,
        note=note,
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _trend_for(current: int, prior: int) -> Tuple[str, Optional[float]]:
    if prior == 0:
        # No baseline. Call it "up" if current > 0, "flat" otherwise.
        return ("up" if current > 0 else "flat"), None
    ratio = (current - prior) / prior
    if ratio >= 0.25:
        return "up", ratio
    if ratio <= -0.25:
        return "down", ratio
    return "flat", ratio
