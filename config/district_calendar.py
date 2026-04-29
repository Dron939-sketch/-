"""Календарь поводов для постов депутатов.

Источник идей для контента: фиксированные даты (праздники), сезонные
поводы (сентябрь — школа, май — благоустройство), и общегородские
события Коломны (День города, Кремль и т.д.).

Возвращает события в окне [today, today+days] для блока «Поводы недели»
в кабинете депутата. Каждое событие — словарь с полями:
  date_iso:  YYYY-MM-DD (для текущего года) или паттерн "MM-DD"
  title:     краткое название
  hint:      идея, как обыграть в посте
  scope:     "all" / "Округ №N" / список секторов
  category:  holiday | season | city | health | civic
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

# Фиксированные годовые поводы — паттерн MM-DD, год берётся текущий
# при выдаче. Если повод уже прошёл в этом году, показываем на следующий.
_FIXED_OCCASIONS: List[Dict[str, Any]] = [
    {
        "pattern": "01-01", "title": "Новый год",
        "category": "holiday",
        "hint":     "Подведи итоги года: что сделано в округе, что в планах.",
    },
    {
        "pattern": "02-23", "title": "День защитника Отечества",
        "category": "holiday",
        "hint":     "Поздравь ветеранов округа, упомяни имена.",
    },
    {
        "pattern": "03-08", "title": "Международный женский день",
        "category": "holiday",
        "hint":     "Поздравление женщин округа — учителей, врачей, активистов.",
    },
    {
        "pattern": "04-12", "title": "День космонавтики",
        "category": "civic",
        "hint":     "Если в школах округа есть уроки — короткий репортаж.",
    },
    {
        "pattern": "05-01", "title": "Праздник весны и труда",
        "category": "holiday",
        "hint":     "Благодарность работникам ЖКХ, школ, благоустройства.",
    },
    {
        "pattern": "05-09", "title": "День Победы",
        "category": "holiday",
        "hint":     "Возложение цветов, встреча с ветеранами в округе. Важный пост.",
    },
    {
        "pattern": "06-01", "title": "День защиты детей",
        "category": "civic",
        "hint":     "Поздравь школьников, упомяни мероприятия в округе.",
    },
    {
        "pattern": "06-12", "title": "День России",
        "category": "holiday",
        "hint":     "Гражданская позиция + локальная фактура.",
    },
    {
        "pattern": "07-08", "title": "День семьи, любви и верности",
        "category": "civic",
        "hint":     "Истории семей округа — конкретные имена, конкретные истории.",
    },
    {
        "pattern": "08-22", "title": "День Государственного флага",
        "category": "civic",
        "hint":     "Короткий пост у флага в округе.",
    },
    {
        "pattern": "09-01", "title": "День знаний",
        "category": "season",
        "hint":     "Школы округа, поздравление учителям и ученикам.",
    },
    {
        "pattern": "10-05", "title": "День учителя",
        "category": "civic",
        "hint":     "Имена учителей школ округа, благодарность.",
    },
    {
        "pattern": "11-04", "title": "День народного единства",
        "category": "holiday",
        "hint":     "Локальные события, общая память города.",
    },
    {
        "pattern": "12-12", "title": "День Конституции",
        "category": "civic",
        "hint":     "Кратко о работе депутата — ответственность, отчётность.",
    },
]


# Город-специфичные даты (Коломна — приблизительные/типичные)
_KOLOMNA_OCCASIONS: List[Dict[str, Any]] = [
    {
        "pattern":  "07-13", "title": "День города Коломна",
        "category": "city",
        "hint":     "Главное событие года: репортаж, история улицы округа, поздравление.",
    },
    {
        "pattern":  "09-15", "title": "Старт отопительного сезона",
        "category": "season",
        "hint":     "Объясни, что делается в твоём округе по отоплению. Дай контакт обращений.",
    },
]


# Сезонные «поводы недели» — без точной даты, актуальны весь сезон
_SEASONAL_HINTS: List[Dict[str, Any]] = [
    {
        "season": "spring", "title": "Субботник в округе",
        "hint":   "Назначь дату, позови жителей. Фотоотчёт после.",
        "category": "civic",
    },
    {
        "season": "summer", "title": "Детские площадки и благоустройство",
        "hint":   "Обход дворов, отчёт по жалобам на качели/песочницы.",
        "category": "season",
    },
    {
        "season": "autumn", "title": "Подготовка к отопительному сезону",
        "hint":   "Контроль готовности УК и муниципальных подрядчиков.",
        "category": "season",
    },
    {
        "season": "winter", "title": "Уборка снега во дворах",
        "hint":   "Проверь, как чистят твой округ. Контакт в УК для жалоб.",
        "category": "season",
    },
]


def _next_occurrence(pattern: str, today: date) -> Optional[date]:
    """MM-DD → ближайшая дата от сегодня (текущий год или следующий)."""
    try:
        mm, dd = pattern.split("-")
        d = date(today.year, int(mm), int(dd))
        if d < today:
            d = date(today.year + 1, int(mm), int(dd))
        return d
    except (ValueError, TypeError):
        return None


def _season(today: date) -> str:
    m = today.month
    if m in (3, 4, 5):  return "spring"
    if m in (6, 7, 8):  return "summer"
    if m in (9, 10, 11): return "autumn"
    return "winter"


def upcoming_for(
    *, days: int = 14, district: Optional[str] = None, today: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Список ближайших поводов в окне [today, today+days].
    Сортируется по дате; сезонные идут в конец.
    """
    today = today or date.today()
    horizon = today + timedelta(days=days)
    out: List[Dict[str, Any]] = []

    for occ in _FIXED_OCCASIONS + _KOLOMNA_OCCASIONS:
        d = _next_occurrence(occ["pattern"], today)
        if d is None or d > horizon:
            continue
        out.append({
            "date_iso":  d.isoformat(),
            "days_until": (d - today).days,
            "title":     occ["title"],
            "hint":      occ["hint"],
            "category":  occ.get("category", "civic"),
            "scope":     occ.get("scope", "all"),
        })

    # Один сезонный повод
    season = _season(today)
    for s in _SEASONAL_HINTS:
        if s["season"] == season:
            out.append({
                "date_iso":   None,
                "days_until": None,
                "title":      s["title"],
                "hint":       s["hint"],
                "category":   s.get("category", "season"),
                "scope":      "all",
            })
            break

    # Сортируем: сначала с датой по близости, затем сезонные
    out.sort(key=lambda x: (x["days_until"] is None, x["days_until"] or 0))
    return out


def relevance_for_district(
    events: List[Dict[str, Any]], district: Optional[str],
) -> List[Dict[str, Any]]:
    """Фильтр: оставляем только относящиеся к округу или общие."""
    if not district:
        return events
    out: List[Dict[str, Any]] = []
    for e in events:
        scope = e.get("scope")
        if scope in (None, "all") or scope == district:
            out.append(e)
        elif isinstance(scope, list) and district in scope:
            out.append(e)
    return out
