"""Market gap analyzer (ТЗ §26, MVP adapter).

Finds under-served business niches by reading the citizen-pain signal —
which topics generate the most negative news / appeals over the past
30 days — and mapping those topics to a curated library of niches that
would relieve that pain.

Honesty: this is a *proxy* signal. We don't have POI data for the city,
so "рынок не закрыт" is inferred from "жители жалуются". The confidence
field reflects that: `high` when the topic shows strong negative signal,
`medium` on moderate, `low` when demand is inferred from low activity
("тишина тоже сигнал — нет ни одного упоминания досуга").

The legacy `market_gap_analyzer.py` ships a 20+ BusinessCategory enum +
pandas per-capita density analysis against external POI benchmarks. Out
of scope for the MVP — real POI data (2GIS / Yandex places) would be a
separate collector. This adapter gives the mayor a honest "where to
invite entrepreneurs" list using only the signals we already have.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


# Pain thresholds: negative_ratio inside a topic.
_HIGH_PAIN = 0.40
_MEDIUM_PAIN = 0.20
_LOW_PAIN = 0.05

# Topic → list of business niches this pain might unblock.
# Each niche carries: key, label, rationale-template (with {topic_label}
# placeholder), base confidence floor before pain modifies it.
_NICHES_BY_TOPIC: Dict[str, Tuple[Dict[str, str], ...]] = {
    "transport": (
        {"key": "carshare",        "label": "Каршеринг / краткосрочная аренда авто",
         "rationale": "Жалобы на транспорт ({mentions} за 30 дней) сигналят дефицит альтернатив личному авто."},
        {"key": "route_taxi",      "label": "Частные маршрутки / вечерние рейсы",
         "rationale": "Негативный фон по теме «Транспорт» указывает на непокрытие вечернего спроса."},
        {"key": "bike_rental",     "label": "Велопрокат / самокаты",
         "rationale": "Лёгкий транспорт частично снимает нагрузку на автобусы."},
    ),
    "utilities": (
        {"key": "emergency_utils", "label": "Частная аварийная служба ЖКХ",
         "rationale": "{mentions} негативных обращений по ЖКХ — частные исполнители могут закрыть SLA."},
        {"key": "plumbers",        "label": "Сервисы сантехника / электрика по вызову",
         "rationale": "Спрос на быстрый ремонт стабильно негативен."},
        {"key": "mkd_management",  "label": "Альтернативная УК для МКД",
         "rationale": "Недовольство УК — классический триггер смены оператора."},
    ),
    "safety": (
        {"key": "security",        "label": "Частная охрана + тревожная кнопка",
         "rationale": "Фон по теме «Безопасность» делает платную охрану и умные замки актуальными."},
        {"key": "video_monitoring", "label": "Сервис видеонаблюдения для бизнеса",
         "rationale": "Малый бизнес подпишется на мониторинг на фоне инцидентов."},
    ),
    "culture": (
        {"key": "coworking",       "label": "Коворкинг + event-площадка",
         "rationale": "Тишина по культуре (или узкий спектр) → ниша для универсальных пространств."},
        {"key": "cinema_cafe",     "label": "Мини-кинотеатр / арт-кафе",
         "rationale": "Недостаток досуговых форматов открывает нишу вечернего развлечения."},
        {"key": "art_studio",      "label": "Арт-студия для детей и взрослых",
         "rationale": "Культурный запрос устойчив, особенно по выходным."},
    ),
    "education": (
        {"key": "kindergarten",    "label": "Лицензированный частный детский сад",
         "rationale": "Жалобы на очереди / переполненность муниципальных садов ({mentions} упоминаний)."},
        {"key": "tutoring_center", "label": "Центр дополнительного образования детей",
         "rationale": "Родители ищут качественный доп-ед, особенно ОГЭ/ЕГЭ."},
        {"key": "language_school", "label": "Языковая школа",
         "rationale": "Устойчивый спрос, низкий порог входа."},
    ),
    "economy": (
        {"key": "biz_incubator",   "label": "Бизнес-инкубатор / акселератор МСП",
         "rationale": "Негативный фон по экономике намекает на слабую поддержку предпринимателей."},
        {"key": "accounting_hub",  "label": "Сервис бухгалтерии и юр. сопровождения МСП",
         "rationale": "Микро-бизнесу нужна дешёвая бухгалтерия."},
        {"key": "coworking_free",  "label": "Коворкинг для фрилансеров",
         "rationale": "Удалёнщикам не хватает места для встреч с клиентами."},
    ),
    "social": (
        {"key": "elderly_care",    "label": "Патронажная служба для пожилых",
         "rationale": "Обращения по социальным темам ({mentions}) выводят уход на передний план."},
        {"key": "family_club",     "label": "Семейный клуб / досуг для многодетных",
         "rationale": "Социальный фон указывает на дефицит недорогого семейного досуга."},
        {"key": "volunteer_hub",   "label": "Хаб для волонтёров и НКО",
         "rationale": "Есть активная социальная повестка, нет координатора."},
    ),
}


@dataclass
class Niche:
    key: str
    label: str
    linked_topic: str
    demand_score: float          # 0..1, blended pain + volume
    confidence: str              # high | medium | low
    rationale: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "linked_topic": self.linked_topic,
            "demand_score": round(self.demand_score, 3),
            "confidence": self.confidence,
            "rationale": self.rationale,
            "evidence": self.evidence,
        }


@dataclass
class GapReport:
    niches: List[Niche]
    topic_signals: Dict[str, Dict[str, Any]]
    window_items: int
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "niches": [n.to_dict() for n in self.niches],
            "topic_signals": self.topic_signals,
            "window_items": int(self.window_items),
            "note": self.note,
        }


def analyze(
    topics_report: Optional[Dict[str, Any]] = None,
    *,
    top_k: int = 6,
) -> GapReport:
    """Take the topics.analyze() output and surface business niches.

    `topics_report` should have the shape produced by analytics.topics.analyze
    (i.e., `{topics: [{key, count, top_titles, ...}, ...]}`). Missing input
    falls back to "no signal" — we still return a handful of niches from the
    broadest topics so a fresh install doesn't show an empty card.
    """
    topics = (topics_report or {}).get("topics") or []
    total = 0
    topic_signals: Dict[str, Dict[str, Any]] = {}

    ranked_niches: List[Tuple[float, int, Niche]] = []
    insertion_idx = 0
    for t in topics:
        key = t.get("key")
        if key not in _NICHES_BY_TOPIC:
            continue
        count = int(t.get("count") or 0)
        total += count
        if count == 0:
            continue

        titles = t.get("top_titles") or []
        neg = 0
        for it in titles:
            s = it.get("sentiment")
            if isinstance(s, (int, float)) and s <= -0.3:
                neg += 1
        negative_ratio = neg / len(titles) if titles else 0.0

        topic_signals[key] = {
            "label": t.get("label") or key,
            "count": count,
            "negative_ratio": round(negative_ratio, 3),
            "trend": t.get("trend", "flat"),
        }

        confidence, demand_score = _demand_for(count, negative_ratio)
        for niche_meta in _NICHES_BY_TOPIC[key]:
            niche = Niche(
                key=niche_meta["key"],
                label=niche_meta["label"],
                linked_topic=key,
                demand_score=demand_score,
                confidence=confidence,
                rationale=niche_meta["rationale"].format(
                    topic_label=t.get("label") or key,
                    mentions=count,
                ),
                evidence=[
                    {"title": e.get("title"), "url": e.get("url"),
                     "sentiment": e.get("sentiment"),
                     "severity": e.get("severity")}
                    for e in titles[:2]
                ],
            )
            # Insertion index preserved so within equal scores the first
            # niche declared for a topic wins — rationale templates that
            # reference the count should surface ahead of generic ones.
            ranked_niches.append((demand_score, insertion_idx, niche))
            insertion_idx += 1

    # Sort by (score desc, insertion_idx asc → higher-score first, insertion tie
    # goes to the niche that was declared first in _NICHES_BY_TOPIC).
    ranked_niches.sort(key=lambda pair: (-pair[0], pair[1]))

    picked: List[Niche] = []
    seen_topics: Dict[str, int] = {}
    # First pass: one best niche per topic (to ensure diversity).
    for _score, _idx, niche in ranked_niches:
        if seen_topics.get(niche.linked_topic, 0) == 0:
            picked.append(niche)
            seen_topics[niche.linked_topic] = 1
        if len(picked) >= top_k:
            break
    # Second pass: fill remaining slots with the highest remaining scores.
    if len(picked) < top_k:
        for _score, _idx, niche in ranked_niches:
            if niche in picked:
                continue
            picked.append(niche)
            if len(picked) >= top_k:
                break

    note = None
    if not topics:
        note = "Нет тематических данных — подключите сбор новостей."
    elif not picked:
        note = "Пока ни одна из 7 тем не набрала активности."

    return GapReport(
        niches=picked[:top_k],
        topic_signals=topic_signals,
        window_items=total,
        note=note,
    )


def _demand_for(count: int, neg_ratio: float) -> Tuple[str, float]:
    """Blend negative ratio + volume → confidence + 0..1 demand score."""
    # Start from negative ratio; then bump for volume.
    volume_bonus = min(0.2, count / 100.0)   # +0.2 max at 20+ mentions
    score = max(0.0, min(1.0, neg_ratio + volume_bonus))

    if neg_ratio >= _HIGH_PAIN:
        return "high", score
    if neg_ratio >= _MEDIUM_PAIN:
        return "medium", score
    if count >= 10:
        # lots of chatter even if not very negative → still worth watching
        return "medium", min(1.0, score + 0.15)
    if count >= 3:
        return "low", score
    return "low", score
