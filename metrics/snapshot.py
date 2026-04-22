"""Pure function: collected news window → 4 vectors + trust + happiness.

No I/O, no DB. Consumes a sequence of CollectedItem objects (already
enriched by `ai.enricher`) and returns a dict ready to write into the
`metrics` table.

Category → vector mapping is intentionally conservative; when we don't
have enough signal for a vector the value is clamped to the mid-point
(3.5/6) so the UI trend arrows stay flat instead of lying.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional

from collectors.base import CollectedItem


# Categories that move each vector. A news item contributes to a vector
# proportionally to the AI-assigned sentiment (-1..+1).
_VECTOR_CATEGORIES = {
    "sb":  {"incidents", "utilities"},            # Безопасность
    "tf":  {"business", "official"},              # Экономика
    "ub":  {"transport", "culture", "complaints"}, # Качество жизни
    "chv": {"culture", "sport"},                  # Соц. капитал
}

# Categories that count as negative or positive for the trust / happiness
# aggregates — these live a level above the per-vector signal.
_NEGATIVE_CATS = {"complaints", "utilities", "incidents"}
_POSITIVE_CATS = {"culture", "sport", "official"}


def _item_category(item: CollectedItem) -> Optional[str]:
    enr = item.enrichment or {}
    return enr.get("category") or item.category


def _item_sentiment(item: CollectedItem) -> Optional[float]:
    enr = item.enrichment or {}
    s = enr.get("sentiment")
    try:
        return float(s) if s is not None else None
    except (TypeError, ValueError):
        return None


def _vector_score(items: Iterable[CollectedItem], cats: set) -> float:
    """Return a 1..6 score from the mean sentiment of relevant items."""
    rel = [
        s for s in (
            _item_sentiment(it) for it in items if _item_category(it) in cats
        )
        if s is not None
    ]
    if not rel:
        return 3.5  # "no signal" baseline
    mean = sum(rel) / len(rel)  # [-1, 1]
    # Map [-1, 1] → [1, 6] centred at 3.5 with a ±2.5 span.
    score = 3.5 + mean * 2.5
    return round(max(1.0, min(6.0, score)), 2)


def snapshot_from_news(items: Iterable[CollectedItem]) -> Dict[str, float]:
    """Aggregate a news window into the six metric fields written to DB."""
    items_list = list(items)
    total = len(items_list)

    vectors = {
        key: _vector_score(items_list, cats)
        for key, cats in _VECTOR_CATEGORIES.items()
    }

    negative = sum(1 for it in items_list if _item_category(it) in _NEGATIVE_CATS)
    positive = sum(1 for it in items_list if _item_category(it) in _POSITIVE_CATS)

    # Trust index — fewer complaints → higher trust. Same formula as the
    # live /all_metrics endpoint so dashboard and DB snapshots agree.
    if total:
        ratio = negative / total
        trust_index = round(max(0.0, min(1.0, 0.8 - ratio * 0.6)), 3)
    else:
        trust_index = 0.58

    # Happiness — balance of positive vs negative, recentred at 0.5.
    if total:
        delta = (positive - negative) / total
        happiness_index = round(max(0.0, min(1.0, 0.5 + delta * 0.4)), 3)
    else:
        happiness_index = 0.62

    return {
        **vectors,
        "trust_index": trust_index,
        "happiness_index": happiness_index,
    }
