"""Cross-city benchmark (ТЗ §7, MVP).

Takes a list of city snapshots and ranks the 6 pilot cities side-by-side
on the 4 Meister vectors (СБ / ТФ / УБ / ЧВ) plus a composite. Pure, no
I/O — the caller (routes) fetches `latest_metrics` for each city and
hands the snapshots in. Keeps the legacy `city_benchmark.py` (sklearn /
numpy / pandas clustering) untouched; that 50+ metric multi-dim
comparison is overkill for the pilot set, and the dashboard just needs
"who's leader / who's laggard / how big is the spread".

Input snapshot shape (all values in the native 1..6 scale where relevant):
    {
        "slug": "kolomna", "name": "Коломна", "emoji": "🏰",
        "population": 140000,
        "sb": 4.2, "tf": 3.7, "ub": 4.1, "chv": 4.0,
        "trust_index": 0.55, "happiness_index": 0.61,   # optional, 0..1
    }

Missing metric values (None) are treated as "no data" — the city gets a
null rank for that vector and drops out of avg/leader computation. The
composite falls back to the average of whatever vectors are present.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


# (key, label, db column) — single source of truth for the 4 vectors.
_VECTORS: List[Dict[str, str]] = [
    {"key": "safety",  "label": "Безопасность",      "db": "sb"},
    {"key": "economy", "label": "Экономика",         "db": "tf"},
    {"key": "quality", "label": "Качество жизни",    "db": "ub"},
    {"key": "social",  "label": "Социальный капитал", "db": "chv"},
]

_SCALE_MIN = 1.0
_SCALE_MAX = 6.0


@dataclass
class CityMetric:
    value: Optional[float]
    rank: Optional[int]           # 1-based, None when value is None
    delta_vs_avg: Optional[float]  # signed diff in 1..6 scale

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": round(self.value, 2) if self.value is not None else None,
            "rank": self.rank,
            "delta_vs_avg": round(self.delta_vs_avg, 2) if self.delta_vs_avg is not None else None,
        }


@dataclass
class CityRow:
    slug: str
    name: str
    emoji: str
    population: Optional[int]
    composite: Optional[float]
    composite_rank: Optional[int]
    metrics: Dict[str, CityMetric]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "emoji": self.emoji,
            "population": self.population,
            "composite": round(self.composite, 2) if self.composite is not None else None,
            "composite_rank": self.composite_rank,
            "metrics": {k: m.to_dict() for k, m in self.metrics.items()},
        }


@dataclass
class VectorStat:
    key: str
    label: str
    avg: Optional[float]
    min: Optional[float]
    max: Optional[float]
    spread: Optional[float]
    leader_slug: Optional[str]
    laggard_slug: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        def _r(v: Optional[float]) -> Optional[float]:
            return round(v, 2) if v is not None else None

        return {
            "key": self.key,
            "label": self.label,
            "avg": _r(self.avg),
            "min": _r(self.min),
            "max": _r(self.max),
            "spread": _r(self.spread),
            "leader_slug": self.leader_slug,
            "laggard_slug": self.laggard_slug,
        }


@dataclass
class BenchmarkResult:
    vectors: List[Dict[str, str]]
    cities: List[CityRow]
    vector_stats: List[VectorStat]
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vectors": [{"key": v["key"], "label": v["label"]} for v in self.vectors],
            "cities": [c.to_dict() for c in self.cities],
            "vector_stats": [s.to_dict() for s in self.vector_stats],
            "note": self.note,
        }


def benchmark(snapshots: Iterable[Dict[str, Any]]) -> BenchmarkResult:
    """Rank cities on the 4 vectors + composite score.

    Returns a `BenchmarkResult` with rows sorted by composite rank (leader
    first). Cities with no data at all keep a composite of None and sink
    to the bottom of the list.
    """
    snapshots = list(snapshots or [])
    if not snapshots:
        return BenchmarkResult(vectors=_VECTORS, cities=[], vector_stats=[], note="нет данных")

    # 1) Pull raw values per vector, clamped to the 1..6 scale.
    per_vector: Dict[str, List[tuple]] = {v["key"]: [] for v in _VECTORS}
    rows_by_slug: Dict[str, Dict[str, Any]] = {}
    for snap in snapshots:
        slug = str(snap.get("slug") or "").lower()
        if not slug:
            continue
        rows_by_slug[slug] = snap
        for v in _VECTORS:
            val = snap.get(v["db"])
            if val is None:
                continue
            try:
                clamped = max(_SCALE_MIN, min(_SCALE_MAX, float(val)))
            except (TypeError, ValueError):
                continue
            per_vector[v["key"]].append((slug, clamped))

    # 2) Per-vector stats: avg, leader, laggard, spread.
    vector_stats: List[VectorStat] = []
    ranks_per_vector: Dict[str, Dict[str, int]] = {}
    values_per_vector: Dict[str, Dict[str, float]] = {}
    avgs: Dict[str, float] = {}
    for v in _VECTORS:
        pairs = per_vector[v["key"]]
        values_per_vector[v["key"]] = {slug: val for slug, val in pairs}
        if not pairs:
            vector_stats.append(
                VectorStat(
                    key=v["key"], label=v["label"],
                    avg=None, min=None, max=None, spread=None,
                    leader_slug=None, laggard_slug=None,
                )
            )
            ranks_per_vector[v["key"]] = {}
            continue

        pairs_sorted = sorted(pairs, key=lambda pv: pv[1], reverse=True)
        rank_map: Dict[str, int] = {}
        for idx, (slug, _val) in enumerate(pairs_sorted, start=1):
            rank_map[slug] = idx
        ranks_per_vector[v["key"]] = rank_map

        values = [p[1] for p in pairs]
        avg = sum(values) / len(values)
        avgs[v["key"]] = avg
        vector_stats.append(
            VectorStat(
                key=v["key"], label=v["label"],
                avg=avg,
                min=min(values), max=max(values),
                spread=max(values) - min(values),
                leader_slug=pairs_sorted[0][0],
                laggard_slug=pairs_sorted[-1][0],
            )
        )

    # 3) Build per-city rows with the metrics dict.
    city_rows: List[CityRow] = []
    for slug, snap in rows_by_slug.items():
        metrics: Dict[str, CityMetric] = {}
        present: List[float] = []
        for v in _VECTORS:
            val = values_per_vector[v["key"]].get(slug)
            if val is None:
                metrics[v["key"]] = CityMetric(value=None, rank=None, delta_vs_avg=None)
                continue
            avg = avgs.get(v["key"])
            delta = (val - avg) if avg is not None else None
            metrics[v["key"]] = CityMetric(
                value=val,
                rank=ranks_per_vector[v["key"]].get(slug),
                delta_vs_avg=delta,
            )
            present.append(val)

        composite = (sum(present) / len(present)) if present else None
        city_rows.append(
            CityRow(
                slug=slug,
                name=str(snap.get("name") or slug),
                emoji=str(snap.get("emoji") or "🏙️"),
                population=_safe_int(snap.get("population")),
                composite=composite,
                composite_rank=None,  # filled after sorting
                metrics=metrics,
            )
        )

    # 4) Rank composite (cities with None composite sink to the bottom).
    scored = [c for c in city_rows if c.composite is not None]
    scored.sort(key=lambda c: c.composite, reverse=True)
    for idx, row in enumerate(scored, start=1):
        row.composite_rank = idx
    unscored = [c for c in city_rows if c.composite is None]
    ordered = scored + unscored

    return BenchmarkResult(vectors=_VECTORS, cities=ordered, vector_stats=vector_stats)


def _safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
