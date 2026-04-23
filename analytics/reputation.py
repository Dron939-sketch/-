"""Reputation guard (ТЗ §21, MVP adapter).

Lightweight rules-based summary of what the city's media field looked
like over a rolling window (default: last 24h). Answers three questions
a mayor asks every morning:

    1. Насколько нам всыпали за сутки? (avg_sentiment, negative_share vs 7d)
    2. Кто громче всего ругается?     (top_negative_authors)
    3. Что именно сейчас выстрелило?   (viral_negative — neg + high-severity)

Inputs are plain dicts so the module is trivially testable. The route
layer adapts rows from `db.queries.news_window` + baseline counters.

The legacy `reputation_guard.py` ships its own ReputationRisk / ThreatType
enums and a threat-classifier keyed on regex matches; that file stays as
reference material — we only reuse the spirit of the rules here.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional


_NEG_SENTIMENT = -0.3   # threshold for "negative" post
_POS_SENTIMENT = +0.3


@dataclass
class AuthorStat:
    author: str
    source_kind: Optional[str]
    mentions: int
    negative: int
    avg_sentiment: float
    worst_severity: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "author": self.author,
            "source_kind": self.source_kind,
            "mentions": int(self.mentions),
            "negative": int(self.negative),
            "avg_sentiment": round(self.avg_sentiment, 3),
            "worst_severity": round(self.worst_severity, 2),
        }


@dataclass
class ViralPost:
    title: str
    url: Optional[str]
    author: Optional[str]
    source_kind: Optional[str]
    category: Optional[str]
    sentiment: Optional[float]
    severity: Optional[float]
    score: float   # internal impact score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "author": self.author,
            "source_kind": self.source_kind,
            "category": self.category,
            "sentiment": round(self.sentiment, 3) if self.sentiment is not None else None,
            "severity": round(self.severity, 2) if self.severity is not None else None,
            "score": round(self.score, 2),
        }


@dataclass
class ReputationReport:
    total_mentions: int
    avg_sentiment: Optional[float]
    negative_share: Optional[float]
    prior_negative_share: Optional[float]   # 7-day baseline
    risk: str                                # low | medium | high
    top_negative_authors: List[AuthorStat] = field(default_factory=list)
    viral_negative: List[ViralPost] = field(default_factory=list)
    by_source: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_mentions": self.total_mentions,
            "avg_sentiment": round(self.avg_sentiment, 3) if self.avg_sentiment is not None else None,
            "negative_share": round(self.negative_share, 3) if self.negative_share is not None else None,
            "prior_negative_share": (
                round(self.prior_negative_share, 3) if self.prior_negative_share is not None else None
            ),
            "risk": self.risk,
            "top_negative_authors": [a.to_dict() for a in self.top_negative_authors],
            "viral_negative": [v.to_dict() for v in self.viral_negative],
            "by_source": dict(self.by_source),
        }


def analyze(
    mentions: Iterable[Dict[str, Any]],
    *,
    prior_negative_share: Optional[float] = None,
    top_k_authors: int = 5,
    top_k_viral: int = 3,
) -> ReputationReport:
    """Run the rollup + ranker over a list of mentions.

    Each mention is expected to have (all optional):
        author, source_kind, title, url, category,
        sentiment (float -1..1), severity (float 0..1).
    Missing sentiment/severity values are simply skipped for averages.
    """
    items = list(mentions or [])
    if not items:
        return ReputationReport(
            total_mentions=0,
            avg_sentiment=None,
            negative_share=None,
            prior_negative_share=prior_negative_share,
            risk="low",
        )

    sentiments: List[float] = []
    neg_count = 0
    worst_severity = 0.0
    by_source: Dict[str, int] = defaultdict(int)

    author_bucket: Dict[str, Dict[str, Any]] = {}

    for m in items:
        source_kind = m.get("source_kind")
        if source_kind:
            by_source[str(source_kind)] += 1

        sent = _coerce_float(m.get("sentiment"))
        if sent is not None:
            sentiments.append(sent)
            if sent <= _NEG_SENTIMENT:
                neg_count += 1
        sev = _coerce_float(m.get("severity"))
        if sev is not None and sev > worst_severity:
            worst_severity = sev

        author = (m.get("author") or m.get("source_handle") or "").strip() or None
        if author:
            slot = author_bucket.setdefault(
                author,
                {
                    "mentions": 0, "negative": 0,
                    "sent_sum": 0.0, "sent_count": 0,
                    "worst_severity": 0.0,
                    "source_kind": source_kind,
                },
            )
            slot["mentions"] += 1
            if sent is not None:
                slot["sent_sum"] += sent
                slot["sent_count"] += 1
                if sent <= _NEG_SENTIMENT:
                    slot["negative"] += 1
            if sev is not None and sev > slot["worst_severity"]:
                slot["worst_severity"] = sev

    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else None
    negative_share = (neg_count / len(items)) if items else None

    # --- risk rollup (simple, monotone rules) -----------------------------
    risk = "low"
    if negative_share is not None:
        if negative_share >= 0.5 or worst_severity >= 0.8:
            risk = "high"
        elif negative_share >= 0.3 or worst_severity >= 0.6:
            risk = "medium"
        elif (
            prior_negative_share is not None
            and prior_negative_share > 0
            and negative_share >= prior_negative_share * 1.5
            and negative_share >= 0.2
        ):
            risk = "medium"

    # --- top negative authors --------------------------------------------
    author_stats: List[AuthorStat] = []
    for author, slot in author_bucket.items():
        if slot["negative"] == 0:
            continue
        avg = (slot["sent_sum"] / slot["sent_count"]) if slot["sent_count"] else 0.0
        author_stats.append(
            AuthorStat(
                author=author,
                source_kind=slot["source_kind"],
                mentions=slot["mentions"],
                negative=slot["negative"],
                avg_sentiment=avg,
                worst_severity=slot["worst_severity"],
            )
        )
    # Impact = negative_count * (1 + worst_severity) — prioritises authors
    # that have BOTH volume and intensity, not just one of them.
    author_stats.sort(
        key=lambda a: a.negative * (1.0 + a.worst_severity), reverse=True,
    )
    author_stats = author_stats[:top_k_authors]

    # --- viral negative posts --------------------------------------------
    scored: List[ViralPost] = []
    for m in items:
        sent = _coerce_float(m.get("sentiment"))
        sev = _coerce_float(m.get("severity"))
        is_neg = sent is not None and sent <= _NEG_SENTIMENT
        if not is_neg and (sev is None or sev < 0.5):
            continue
        # Blend negativity magnitude and severity into one sortable score.
        neg_mag = max(0.0, -sent) if sent is not None else 0.0
        score = neg_mag + (sev or 0.0)
        scored.append(
            ViralPost(
                title=str(m.get("title") or "(без заголовка)")[:200],
                url=m.get("url"),
                author=m.get("author") or m.get("source_handle"),
                source_kind=m.get("source_kind"),
                category=m.get("category"),
                sentiment=sent,
                severity=sev,
                score=score,
            )
        )
    scored.sort(key=lambda v: v.score, reverse=True)
    viral = scored[:top_k_viral]

    return ReputationReport(
        total_mentions=len(items),
        avg_sentiment=avg_sentiment,
        negative_share=negative_share,
        prior_negative_share=prior_negative_share,
        risk=risk,
        top_negative_authors=author_stats,
        viral_negative=viral,
        by_source=dict(by_source),
    )


def _coerce_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
