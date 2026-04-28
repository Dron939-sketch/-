"""Crisis predictor (ТЗ §10, MVP adapter).

Pure rules-based early warning over the signals we actually have:
    - 4 Meister metric trajectories (СБ / ТФ / УБ / ЧВ) over the last 7 days
    - news items from the last 24h with enrichment (sentiment, severity, category)
    - appeals volume (last 24h vs 7-day baseline)

Four detectors:
    1. metric_drop      — vector fell by ≥0.5 on 1..6 scale vs 7-day mean
    2. sentiment_spike  — negative-news count ≥max(3, 2× baseline neg count)
    3. high_severity    — any news with enrichment.severity ≥ 0.5
    4. complaint_surge  — appeals_24h ≥ max(5, 2 × 7d daily average)

The legacy `crisis_predictor.py` brings numpy + sklearn + (optional) TensorFlow
LSTM for ML-based forecasting. Overkill for the MVP and the 6-city pilot where
we simply don't have enough labelled history. Pure rules keep the code
explainable, fast, and deterministic (easy to test). When real historic
crises accumulate, we can revisit the ML path.

Output: a `CrisisReport` with
    status: "ok" | "watch" | "attention"
    headline: short human summary
    alerts:  ordered by severity (critical → high → medium → watch)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


# Severity ordering (higher = worse). Used to sort alerts + roll up status.
_LEVEL_RANK = {"critical": 4, "high": 3, "medium": 2, "watch": 1}

_VECTOR_LABELS = {
    "safety":  "Безопасность",
    "economy": "Экономика",
    "quality": "Качество жизни",
    "social":  "Социальный капитал",
}

# Maps the 4 vector keys ↔ their DB column names.
_METRIC_COLUMN = {
    "sb": "safety", "tf": "economy", "ub": "quality", "chv": "social",
}


@dataclass
class Alert:
    level: str                    # critical | high | medium | watch
    kind: str                     # metric_drop | sentiment_spike | high_severity | complaint_surge
    title: str
    description: str
    horizon: str                  # 24-48ч | 3-7 дней | 1-4 недели | мониторинг
    probability: float            # 0..1 — how confident we are the crisis is real
    vector: Optional[str] = None  # safety | economy | quality | social (when applicable)
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "horizon": self.horizon,
            "probability": round(self.probability, 2),
            "vector": self.vector,
            "evidence": self.evidence,
        }


@dataclass
class CrisisReport:
    status: str            # ok | watch | attention
    headline: str
    alerts: List[Alert]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "headline": self.headline,
            "alerts": [a.to_dict() for a in self.alerts],
        }


def detect_crises(
    current_metrics: Optional[Dict[str, float]] = None,
    metrics_history_7d: Optional[Dict[str, List[float]]] = None,
    news_24h: Optional[Iterable[Dict[str, Any]]] = None,
    news_7d_neg_count: Optional[int] = None,
    appeals_24h: int = 0,
    appeals_7d_avg: float = 0.0,
) -> CrisisReport:
    """Run all four detectors and roll up an overall status.

    Every argument is optional — missing signals silently skip their detector
    rather than raising. That keeps this robust to DB outages / missing
    enrichment.
    """
    alerts: List[Alert] = []

    alerts.extend(
        _detect_metric_drops(current_metrics or {}, metrics_history_7d or {})
    )
    news_list = list(news_24h or [])
    alerts.extend(_detect_sentiment_spike(news_list, news_7d_neg_count))
    alerts.extend(_detect_high_severity(news_list))
    alerts.extend(_detect_complaint_surge(appeals_24h, appeals_7d_avg))

    # Sort: highest severity first, then by probability desc.
    alerts.sort(key=lambda a: (_LEVEL_RANK.get(a.level, 0), a.probability), reverse=True)

    status = _rollup_status(alerts)
    headline = _headline_for(status, alerts)
    return CrisisReport(status=status, headline=headline, alerts=alerts)


# ---------------------------------------------------------------------------
# Detector 1: metric_drop
# ---------------------------------------------------------------------------

def _detect_metric_drops(
    current_metrics: Dict[str, float],
    history: Dict[str, List[float]],
) -> List[Alert]:
    alerts: List[Alert] = []
    for db_key, vector_key in _METRIC_COLUMN.items():
        latest = current_metrics.get(db_key)
        series = history.get(db_key) or []
        if latest is None or len(series) < 2:
            continue
        # Mean over the historic window excluding the very latest sample if
        # it's already in the series. Robust to either convention.
        older = series[:-1] if len(series) > 1 else series
        if not older:
            continue
        avg = sum(older) / len(older)
        drop = avg - float(latest)
        if drop < 0.5:
            continue

        if drop >= 1.0:
            level, horizon, prob = "critical", "24-48ч", 0.85
        elif drop >= 0.7:
            level, horizon, prob = "high", "3-7 дней", 0.7
        else:
            level, horizon, prob = "medium", "1-4 недели", 0.55

        label = _VECTOR_LABELS.get(vector_key, vector_key)
        alerts.append(
            Alert(
                level=level,
                kind="metric_drop",
                vector=vector_key,
                title=f"Падение: {label}",
                description=(
                    f"{label} упал с {avg:.1f} до {float(latest):.1f} "
                    f"(–{drop:.1f} за 7 дней)."
                ),
                horizon=horizon,
                probability=prob,
                evidence={
                    "metric": db_key,
                    "latest": round(float(latest), 2),
                    "avg_7d": round(avg, 2),
                    "drop": round(drop, 2),
                },
            )
        )
    return alerts


# ---------------------------------------------------------------------------
# Detector 2: sentiment_spike
# ---------------------------------------------------------------------------

def _detect_sentiment_spike(
    news: List[Dict[str, Any]],
    baseline_neg_count_7d: Optional[int],
) -> List[Alert]:
    if not news:
        return []
    neg = 0
    for item in news:
        sent = _sentiment_of(item)
        if sent is not None and sent < -0.3:
            neg += 1
    if neg < 3:
        return []

    # Baseline: average daily negative count over last 7 days. Fallback to
    # a conservative "3 negatives per day" floor when we have no history.
    baseline_daily = None
    if baseline_neg_count_7d is not None and baseline_neg_count_7d >= 0:
        baseline_daily = baseline_neg_count_7d / 7
    threshold = max(3.0, 2.0 * (baseline_daily if baseline_daily is not None else 1.5))
    if neg < threshold:
        return []

    ratio = neg / max(1.0, (baseline_daily or 1.5))
    if ratio >= 4.0:
        level, horizon, prob = "critical", "24-48ч", 0.8
    elif ratio >= 2.5:
        level, horizon, prob = "high", "3-7 дней", 0.65
    else:
        level, horizon, prob = "medium", "1-4 недели", 0.5

    return [
        Alert(
            level=level,
            kind="sentiment_spike",
            title="Всплеск негативного фона",
            description=(
                f"{neg} негативных публикаций за 24ч — "
                f"в {ratio:.1f}× выше обычного."
            ),
            horizon=horizon,
            probability=prob,
            evidence={
                "negative_24h": neg,
                "baseline_daily": round(baseline_daily, 2) if baseline_daily is not None else None,
                "ratio": round(ratio, 2),
            },
        )
    ]


# ---------------------------------------------------------------------------
# Detector 3: high_severity
# ---------------------------------------------------------------------------

def _detect_high_severity(news: List[Dict[str, Any]]) -> List[Alert]:
    if not news:
        return []
    top: List[tuple] = []  # (severity, title, url)
    for item in news:
        sev = _severity_of(item)
        if sev is None or sev < 0.5:
            continue
        title = item.get("title") or item.get("summary") or "Без заголовка"
        top.append((sev, str(title)[:120], item.get("url")))
    if not top:
        return []

    top.sort(key=lambda t: t[0], reverse=True)
    max_sev = top[0][0]
    if max_sev >= 0.8:
        level, horizon, prob = "critical", "24-48ч", 0.9
    elif max_sev >= 0.65:
        level, horizon, prob = "high", "3-7 дней", 0.75
    else:
        level, horizon, prob = "medium", "1-4 недели", 0.55

    return [
        Alert(
            level=level,
            kind="high_severity",
            title="Событие высокой серьёзности",
            description=(
                f"{len(top)} публикаций с severity ≥ 0.5. "
                f"Худшая: «{top[0][1]}» (severity {max_sev:.2f})."
            ),
            horizon=horizon,
            probability=prob,
            evidence={
                "count": len(top),
                "max_severity": round(float(max_sev), 2),
                "top": [
                    {"title": t, "severity": round(float(s), 2), "url": u}
                    for s, t, u in top[:3]
                ],
            },
        )
    ]


# ---------------------------------------------------------------------------
# Detector 4: complaint_surge
# ---------------------------------------------------------------------------

def _detect_complaint_surge(
    appeals_24h: int, appeals_7d_avg: float
) -> List[Alert]:
    if appeals_24h < 5:
        return []
    baseline = max(0.0, float(appeals_7d_avg))
    threshold = max(5.0, 2.0 * baseline)
    if appeals_24h < threshold:
        return []
    ratio = appeals_24h / max(1.0, baseline) if baseline > 0 else float("inf")

    if ratio >= 5.0 or (baseline > 0 and appeals_24h >= 30):
        level, horizon, prob = "critical", "24-48ч", 0.8
    elif ratio >= 3.0:
        level, horizon, prob = "high", "3-7 дней", 0.65
    else:
        level, horizon, prob = "medium", "1-4 недели", 0.5

    ratio_desc = "×∞" if ratio == float("inf") else f"в {ratio:.1f}× выше"
    return [
        Alert(
            level=level,
            kind="complaint_surge",
            title="Рост числа обращений",
            description=(
                f"{appeals_24h} обращений за сутки — {ratio_desc} среднего."
            ),
            horizon=horizon,
            probability=prob,
            evidence={
                "appeals_24h": int(appeals_24h),
                "baseline_daily": round(baseline, 2),
                "ratio": None if ratio == float("inf") else round(ratio, 2),
            },
        )
    ]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _sentiment_of(item: Dict[str, Any]) -> Optional[float]:
    for key in ("sentiment",):
        v = item.get(key)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    enr = item.get("enrichment") or {}
    if isinstance(enr, dict):
        v = enr.get("sentiment")
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def _severity_of(item: Dict[str, Any]) -> Optional[float]:
    for key in ("severity",):
        v = item.get(key)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    enr = item.get("enrichment") or {}
    if isinstance(enr, dict):
        v = enr.get("severity")
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def _rollup_status(alerts: List[Alert]) -> str:
    if not alerts:
        return "ok"
    top = max(_LEVEL_RANK.get(a.level, 0) for a in alerts)
    if top >= _LEVEL_RANK["high"]:
        return "attention"
    if top >= _LEVEL_RANK["medium"]:
        return "watch"
    return "watch"


def _headline_for(status: str, alerts: List[Alert]) -> str:
    if not alerts or status == "ok":
        return "Всё в норме — кризисных сигналов нет"
    top = alerts[0]
    if status == "attention":
        return f"Требует внимания: {top.title.lower()}"
    return f"Под наблюдением: {top.title.lower()}"
