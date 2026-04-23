"""Knowledge bank + case recommender (ТЗ §16 + §19, MVP adapter).

Curated library of 15 generic best-practice cases (типичные практики городов
РФ и Московской области) plus a pure rule-based recommender that picks the
3 most relevant given the current city's weakest vectors and any active
crisis signals.

The legacy `knowledge_bank.py` (FAISS + sentence-transformers for vector
search) and `learning_recommender.py` (sklearn RandomForest over historical
outcomes) are out of scope for the MVP — neither a vector index nor a
labelled-outcome corpus exists yet. The adapter uses tag + vector overlap
scoring, which is transparent and trivially testable.

Cases are clearly labelled as "типичные практики" (generic patterns), not
specific city claims — the mayor sees directions she could try, not
verified case-study citations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set


@dataclass(frozen=True)
class Case:
    id: str
    title: str
    vectors: tuple                    # which Meister vectors it helps
    tags: tuple                       # topical keywords
    problem: str                      # what problem this addresses
    approach: str                     # how cities typically solve it
    evidence_level: str = "practice"  # practice | documented | proven

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "vectors": list(self.vectors),
            "tags": list(self.tags),
            "problem": self.problem,
            "approach": self.approach,
            "evidence_level": self.evidence_level,
        }


# Curated library — generic patterns, not claims about any specific city.
_LIBRARY: List[Case] = [
    Case(
        id="safety_street_light",
        title="Уличное освещение как базовая безопасность",
        vectors=("safety",),
        tags=("безопасность", "инцидент", "ЖКХ", "освещение", "ночь"),
        problem="Рост ночных инцидентов и жалоб на тёмные дворы.",
        approach="Аудит карты освещения по геообращениям, замена ламп на LED, "
                 "частота обхода ЖЭК + прозрачный дашборд по исправленным точкам.",
        evidence_level="practice",
    ),
    Case(
        id="safety_school_patrol",
        title="Пеший маршрут «школа-дом»",
        vectors=("safety", "social"),
        tags=("безопасность", "дети", "школа", "социальное"),
        problem="Жалобы на безопасность маршрута детей в школу.",
        approach="Волонтёрские дежурства + брендированные переходы + камеры на "
                 "узловых точках. Снижает инциденты без крупных затрат.",
        evidence_level="practice",
    ),
    Case(
        id="safety_hotline",
        title="Единый номер ЖКХ-инцидента",
        vectors=("safety", "quality"),
        tags=("ЖКХ", "инцидент", "обращения", "связь"),
        problem="Обращения теряются между УК, муниципалитетом и регионом.",
        approach="Единое окно 24/7 с SLA-таймером. Публичная статистика решённых "
                 "заявок на сайте администрации.",
        evidence_level="documented",
    ),
    Case(
        id="economy_local_fair",
        title="Фермерская ярмарка + поддержка МСП",
        vectors=("economy", "social"),
        tags=("бизнес", "малый", "сельское", "рынок"),
        problem="Низкая заметность местных производителей, отток денег в "
                "сетевые магазины.",
        approach="Еженедельная ярмарка в центре + субсидирование аренды + "
                 "маркетплейс «Сделано у нас».",
        evidence_level="practice",
    ),
    Case(
        id="economy_industrial_park",
        title="Индустриальный парк с налоговыми каникулами",
        vectors=("economy",),
        tags=("инвестиции", "промышленность", "налоги", "производство"),
        problem="Нет резидентов под новые рабочие места, отток молодёжи.",
        approach="Зона с налоговыми льготами на 5 лет + подключение инфраструктуры "
                 "за счёт региона. Требует координации с ОЭЗ МО.",
        evidence_level="documented",
    ),
    Case(
        id="economy_tourism",
        title="Фестивальный туризм",
        vectors=("economy", "quality"),
        tags=("туризм", "культура", "бренд", "фестиваль"),
        problem="Город воспринимается как «транзитный», нет удержания туристов.",
        approach="Один флагманский фестиваль (3-4 дня) + 5-6 малых по сезонам. "
                 "Бронирование гостиниц растёт на 30-50% в пиковые выходные.",
        evidence_level="practice",
    ),
    Case(
        id="quality_yards",
        title="Благоустройство дворов по запросу жителей",
        vectors=("quality", "social"),
        tags=("благоустройство", "дворы", "участие", "голосование"),
        problem="Дворы в новых районах устарели, жалобы на отсутствие детских "
                "площадок.",
        approach="Ежегодное публичное голосование за 5-10 дворов на ремонт. "
                 "Прозрачная смета + фото до/после на сайте.",
        evidence_level="proven",
    ),
    Case(
        id="quality_transport",
        title="Оптимизация маршрутов общественного транспорта",
        vectors=("quality", "economy"),
        tags=("транспорт", "маршруты", "автобус"),
        problem="Переполненность утренних маршрутов + долгий интервал.",
        approach="Анализ GPS-треков + опрос пассажиров. Перераспределение "
                 "автобусов по потоку, выделенка на узких участках.",
        evidence_level="documented",
    ),
    Case(
        id="quality_greenery",
        title="Зелёный каркас города",
        vectors=("quality",),
        tags=("экология", "парки", "зелень"),
        problem="Массовое строительство без компенсации зелёных зон.",
        approach="Норматив: 6 м² зелени на жителя. Инвентаризация + защита "
                 "существующих + точечные скверы в плотных кварталах.",
        evidence_level="documented",
    ),
    Case(
        id="social_volunteers",
        title="Муниципальный штаб волонтёров",
        vectors=("social",),
        tags=("волонтёры", "сообщество", "молодёжь"),
        problem="Низкая вовлечённость молодёжи в городскую жизнь.",
        approach="Физический штаб + система бонусов (от льготного транспорта до "
                 "рекомендаций в ВУЗы). ROI — отложенный, но устойчивый.",
        evidence_level="practice",
    ),
    Case(
        id="social_elderly_clubs",
        title="Клубы активного долголетия",
        vectors=("social", "quality"),
        tags=("пожилые", "здоровье", "сообщество"),
        problem="Изоляция пожилых, нагрузка на соцзащиту.",
        approach="Клубы при библиотеках + занятия по расписанию (танцы, "
                 "компьютерная грамотность, ЗОЖ). Федеральная поддержка по "
                 "программе «Активное долголетие».",
        evidence_level="documented",
    ),
    Case(
        id="social_feedback_hub",
        title="Единая платформа обратной связи",
        vectors=("social", "safety"),
        tags=("обращения", "связь", "прозрачность"),
        problem="Недоверие к власти из-за ощущения «обращения не доходят».",
        approach="Портал типа Госуслуги/ПОС с публичным SLA на каждый тип "
                 "обращения. Рейтинг ответственных подразделений.",
        evidence_level="proven",
    ),
    Case(
        id="safety_cameras",
        title="Видеонаблюдение «Безопасный город»",
        vectors=("safety",),
        tags=("безопасность", "камеры", "инцидент"),
        problem="Низкая раскрываемость мелких правонарушений.",
        approach="Сеть из 200-500 камер (зависит от размера) с интеграцией в "
                 "региональный центр мониторинга. ФЗ-152 по персданным.",
        evidence_level="documented",
    ),
    Case(
        id="quality_waste",
        title="Раздельный сбор мусора с воспитанием",
        vectors=("quality",),
        tags=("экология", "мусор", "воспитание"),
        problem="Переполненные баки, жалобы на зловоние.",
        approach="3-корзинная система + уроки в школах + публичная инфографика. "
                 "Работает при условии реального раздельного вывоза.",
        evidence_level="practice",
    ),
    Case(
        id="economy_digital_services",
        title="Цифровые муниципальные сервисы",
        vectors=("economy", "quality"),
        tags=("цифровизация", "госуслуги", "бизнес"),
        problem="Долгие очереди в МФЦ по типовым обращениям.",
        approach="Электронные заявки на все типовые процедуры (разрешения, "
                 "справки, лицензии). Сокращает время обработки в 3-5 раз.",
        evidence_level="proven",
    ),
]


@dataclass
class Recommendation:
    case: Case
    score: float
    matched_vectors: List[str] = field(default_factory=list)
    matched_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case": self.case.to_dict(),
            "score": round(self.score, 3),
            "matched_vectors": self.matched_vectors,
            "matched_tags": self.matched_tags,
        }


def recommend(
    weak_vectors: Optional[Iterable[str]] = None,
    *,
    crisis_vectors: Optional[Iterable[str]] = None,
    extra_tags: Optional[Iterable[str]] = None,
    limit: int = 3,
) -> List[Recommendation]:
    """Score every case and return the top N matches.

    Scoring:
        vector overlap          * 3   — primary driver
        crisis-vector boost     * 2   — urgent vectors outweigh merely weak
        tag overlap             * 1   — topical secondary signal
        evidence level bonus    +0.5 proven / +0.2 documented / 0 practice

    Returns at most `limit` recommendations, sorted by score desc.
    When no signals are provided, falls back to highest-evidence cases
    across all vectors.
    """
    weak: Set[str] = _clean(weak_vectors)
    crisis: Set[str] = _clean(crisis_vectors)
    tags: Set[str] = _clean(extra_tags)

    scored: List[Recommendation] = []
    for case in _LIBRARY:
        case_vectors = set(case.vectors)
        matched_vectors = list((weak | crisis) & case_vectors)
        matched_tags = list(tags & set(case.tags))

        overlap_score = (
            3.0 * len(weak & case_vectors)
            + 2.0 * len(crisis & case_vectors)
            + 1.0 * len(matched_tags)
        )

        if overlap_score == 0.0 and (weak or crisis or tags):
            continue  # signals given but no overlap — drop

        evidence_bonus = (
            0.5 if case.evidence_level == "proven"
            else 0.2 if case.evidence_level == "documented"
            else 0.0
        )
        score = overlap_score + evidence_bonus

        scored.append(
            Recommendation(
                case=case,
                score=score,
                matched_vectors=matched_vectors,
                matched_tags=matched_tags,
            )
        )

    scored.sort(
        key=lambda r: (r.score, r.case.evidence_level == "proven",
                       r.case.evidence_level == "documented"),
        reverse=True,
    )
    return scored[: max(1, int(limit))]


def library_size() -> int:
    """Total number of cases available (for UI hints)."""
    return len(_LIBRARY)


def _clean(items: Optional[Iterable[str]]) -> Set[str]:
    if not items:
        return set()
    return {str(i).strip().lower() for i in items if i}
