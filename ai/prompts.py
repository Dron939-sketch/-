"""Prompt templates for the AI enrichment layer."""

from __future__ import annotations

# Canonical category set. Keep in sync with dashboard filters and the
# hard-coded categories in `config/sources.py`.
CATEGORIES = [
    "incidents",     # ЧП, аварии, происшествия
    "utilities",     # ЖКХ, отопление, вода
    "transport",     # дороги, транспорт
    "culture",       # культура, туризм, мероприятия
    "sport",         # спорт
    "business",      # бизнес, инвестиции
    "official",      # официальные сообщения администрации
    "news",          # нейтральные новости
    "complaints",    # жалобы граждан
    "other",
]


ENRICHMENT_SYSTEM = """Ты — аналитик городской администрации Коломны.
Читаешь поток новостей и сообщений соцсетей и размечаешь каждое.
Отвечаешь строго одним JSON-объектом, без какого-либо другого текста.
""".strip()


ENRICHMENT_USER_TEMPLATE = """Для каждого объекта ниже верни:
- sentiment: число от -1.0 (резко негативно) до 1.0 (резко позитивно)
- category: одна из {categories}
- severity: число от 0.0 до 1.0, насколько срочно для мэра (0.0 — светская хроника, 1.0 — ЧП угрожающее людям)
- summary: одна строка ≤ 80 символов на русском, передающая суть

Сохрани порядок и используй те же `id`.

Формат ответа:
{{"items": [{{"id": "...", "sentiment": 0.0, "category": "...", "severity": 0.0, "summary": "..."}}]}}

Входные данные:
{payload}
""".strip()


def build_enrichment_prompt(items_payload: str) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) ready for DeepSeek."""
    categories = " | ".join(CATEGORIES)
    user = ENRICHMENT_USER_TEMPLATE.format(
        categories=categories, payload=items_payload
    )
    return ENRICHMENT_SYSTEM, user
