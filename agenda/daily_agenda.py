"""Daily agenda builder.

Takes a snapshot of metrics, trust-index output, weather and recent news
items and produces the morning briefing shown to the mayor at 09:00. The
builder is deterministic and fully pure — no I/O — so it is easy to unit
test and to swap into a Celery task.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from collectors.base import CollectedItem


_VECTOR_LABELS = {
    "СБ": "🛡️ Безопасность",
    "ТФ": "💰 Экономика",
    "УБ": "😊 Качество жизни",
    "ЧВ": "🤝 Соцкапитал",
}


@dataclass
class DailyAgenda:
    date: datetime
    city: str
    headline: str
    description: str
    actions: List[str] = field(default_factory=list)
    top_complaints: List[str] = field(default_factory=list)
    top_praises: List[str] = field(default_factory=list)
    vectors: Dict[str, float] = field(default_factory=dict)
    weather_line: str = ""
    happiness: Optional[float] = None
    trust: Optional[float] = None

    def to_markdown(self) -> str:
        """Format the agenda as the Telegram-style Markdown report in the spec."""
        lines: List[str] = [
            f"🏙️ **{self.city} — сводка за {self.date:%Y-%m-%d}**",
            "",
        ]
        if self.weather_line:
            lines.append(f"**Погода:** {self.weather_line}")
        if self.happiness is not None:
            lines.append(f"**Индекс счастья:** {self.happiness:.2f} / 1.0")
        if self.trust is not None:
            lines.append(f"**Индекс доверия:** {self.trust:.2f} / 1.0")
        lines.append("")
        lines.append(f"**Ключевая проблема дня:** {self.headline}")
        if self.description:
            lines.append(self.description)
        if self.top_complaints:
            lines.append("")
            lines.append("**Топ-3 жалобы:**")
            for i, item in enumerate(self.top_complaints[:3], start=1):
                lines.append(f"{i}. {item}")
        if self.actions:
            lines.append("")
            lines.append("**Рекомендованные действия:**")
            for action in self.actions:
                lines.append(f"✅ {action}")
        if self.vectors:
            lines.append("")
            lines.append("**Статус метрик:**")
            for code, value in self.vectors.items():
                label = _VECTOR_LABELS.get(code, code)
                lines.append(f"{label}: {value:.1f}/6")
        lines.append("")
        lines.append("---")
        lines.append("CityMind | Ваш AI-ассистент")
        return "\n".join(lines)


class DailyAgendaBuilder:
    """Compose a `DailyAgenda` from raw analytical inputs.

    The implementation is intentionally conservative: we pick the single
    highest-signal problem as the headline and cap rest of the content so
    the report stays readable in a Telegram message.
    """

    def __init__(self, city_name: str):
        self.city_name = city_name

    def build(
        self,
        *,
        date: datetime,
        city_metrics: Dict[str, float],
        trust: Dict[str, Any],
        happiness: Dict[str, Any],
        weather: Dict[str, Any],
        news: Iterable[CollectedItem],
        interventions: Optional[List[str]] = None,
    ) -> DailyAgenda:
        news_list = list(news)
        headline, description = self._pick_headline(news_list, trust)
        top_complaints = list(trust.get("top_complaints") or [])[:3]
        top_praises = list(trust.get("top_praises") or [])[:3]
        actions = self._suggest_actions(interventions, headline, top_complaints)

        return DailyAgenda(
            date=date,
            city=self.city_name,
            headline=headline,
            description=description,
            actions=actions,
            top_complaints=top_complaints,
            top_praises=top_praises,
            vectors=self._extract_vectors(city_metrics),
            weather_line=self._format_weather(weather),
            happiness=happiness.get("overall"),
            trust=trust.get("index"),
        )

    @staticmethod
    def _extract_vectors(metrics: Dict[str, float]) -> Dict[str, float]:
        """Normalise metric keys to the canonical СБ/ТФ/УБ/ЧВ set."""
        return {
            code: float(metrics.get(code, 3.0))
            for code in ("СБ", "ТФ", "УБ", "ЧВ")
        }

    @staticmethod
    def _format_weather(weather: Dict[str, Any]) -> str:
        if not weather:
            return ""
        temp = weather.get("temperature")
        cond = weather.get("condition") or ""
        emoji = weather.get("condition_emoji") or ""
        if temp is None:
            return f"{cond} {emoji}".strip()
        return f"{temp:+.0f}°C, {cond} {emoji}".strip()

    def _pick_headline(
        self,
        news: List[CollectedItem],
        trust: Dict[str, Any],
    ) -> tuple[str, str]:
        # Prefer a fresh incident from Telegram/VK complaint feeds; fall back
        # to the single most frequent complaint bucketed by trust analyzer.
        negative = [
            n for n in news if n.category in {"complaints", "incidents", "utilities"}
        ]
        if negative:
            negative.sort(key=lambda n: n.published_at, reverse=True)
            head = negative[0]
            return head.title, head.content[:400]
        complaints = trust.get("top_complaints") or []
        if complaints:
            return (
                f"Системная жалоба: {complaints[0]}",
                "Частотная жалоба по городу за последние 24 часа.",
            )
        return ("Критических проблем не обнаружено", "")

    @staticmethod
    def _suggest_actions(
        interventions: Optional[List[str]],
        headline: str,
        complaints: List[str],
    ) -> List[str]:
        if interventions:
            return interventions[:5]
        actions: List[str] = []
        if complaints:
            actions.append(
                f"Поручить профильному заму разобрать жалобу: {complaints[0]}"
            )
        if headline:
            actions.append(f"Запросить оперативную справку по: {headline[:80]}")
        actions.append("Опубликовать ответ пресс-службы до 15:00")
        return actions[:5]

    @staticmethod
    def summarise_tags(news: Iterable[CollectedItem], limit: int = 5) -> List[str]:
        """Utility: returns the most frequent category tags in the incoming stream."""
        counter: Counter[str] = Counter(n.category or "other" for n in news)
        return [tag for tag, _ in counter.most_common(limit)]
