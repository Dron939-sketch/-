"""Голос-портрет депутата — узнаваемые маркеры стиля.

Простой статистический анализ постов:
- Топ-5 уникальных частых слов (без stop-words)
- Средняя длина предложения
- Доля постов с эмодзи / восклицанием / вопросом
- Грубая тональность (positive/neutral/negative по словарю)

На выходе — словарь markers для UI; это даёт «вау» — депутат видит,
что система действительно прочитала её посты.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List


# Стоп-слова — частотные служебные русские
_STOPWORDS = {
    "и", "в", "не", "что", "на", "я", "с", "со", "как", "а", "то", "все",
    "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за",
    "бы", "по", "только", "ее", "мне", "было", "вот", "от", "меня", "о",
    "из", "ему", "теперь", "когда", "даже", "ну", "вдруг", "ли", "если",
    "уже", "или", "ни", "быть", "был", "него", "до", "вас", "нибудь",
    "опять", "уж", "вам", "ведь", "там", "потом", "себя", "ничего", "ей",
    "может", "они", "тут", "где", "есть", "надо", "ней", "для", "мы",
    "тебя", "их", "чем", "была", "сам", "чтоб", "без", "будто", "чего",
    "раз", "тоже", "себе", "под", "будет", "ж", "тогда", "кто", "этот",
    "того", "потому", "этого", "какой", "совсем", "ним", "здесь", "этом",
    "один", "почти", "мой", "тем", "чтобы", "нее", "сейчас", "были",
    "куда", "зачем", "всех", "никогда", "можно", "при", "наконец", "два",
    "об", "другой", "хоть", "после", "над", "больше", "тот", "через",
    "эти", "нас", "про", "всего", "них", "какая", "много", "разве",
    "три", "эту", "моя", "впрочем", "хорошо", "свою", "этой", "перед",
    "иногда", "лучше", "чуть", "том", "нельзя", "такой", "им", "более",
    "всегда", "конечно", "всю", "между", "это",
}

# Лёгкая лексика тональности
_POSITIVE_RU = {
    "спасибо", "вместе", "помог", "помощь", "решено", "решили", "сделано",
    "благодарю", "благодарность", "успех", "победа", "радость", "поздрав",
    "семья", "дом", "сосед", "друг", "праздник", "ремонт", "восстанов",
}
_NEGATIVE_RU = {
    "проблема", "жалоба", "сломан", "нет", "нельзя", "ошибк", "плохо",
    "не работает", "сорван", "задерж", "штраф", "отказ", "увы", "к сожалению",
}


_WORD_RE = re.compile(r"[а-яёa-z]{4,}", re.IGNORECASE)
_SENT_RE = re.compile(r"[^.!?\n]+[.!?]", re.UNICODE)


def build_voice_portrait(audit: Dict[str, Any]) -> Dict[str, Any]:
    """Собираем маркеры стиля по сырым текстам."""
    posts_text = audit.get("_posts_text") or []
    if not posts_text:
        return {"state": "no_data"}

    all_text = "\n".join(p["text"] for p in posts_text if p.get("text"))
    if not all_text.strip():
        return {"state": "no_data"}

    # Топ-5 слов
    words = [w.lower() for w in _WORD_RE.findall(all_text)]
    words = [w for w in words if w not in _STOPWORDS and len(w) >= 4]
    counter = Counter(words)
    top_words = [
        {"word": w, "count": c}
        for w, c in counter.most_common(8)
    ]

    # Средняя длина предложения
    sentences = [s.strip() for s in _SENT_RE.findall(all_text) if s.strip()]
    avg_sent = round(sum(len(s) for s in sentences) / len(sentences), 0) if sentences else 0

    # Доли постов с эмодзи / восклицанием / вопросом
    n = len(posts_text)
    has_emoji = sum(1 for p in posts_text if _has_emoji(p["text"]))
    has_excl  = sum(1 for p in posts_text if "!" in p["text"])
    has_quest = sum(1 for p in posts_text if "?" in p["text"])

    # Простая тональность
    pos_hits = sum(1 for p in posts_text for k in _POSITIVE_RU if k in p["text"].lower())
    neg_hits = sum(1 for p in posts_text for k in _NEGATIVE_RU if k in p["text"].lower())
    if pos_hits + neg_hits == 0:
        tone = "нейтральный"
        tone_score = 50
    else:
        tone_score = round(pos_hits * 100 / (pos_hits + neg_hits))
        tone = "тёплый" if tone_score >= 60 else \
               "критичный" if tone_score < 40 else "сбалансированный"

    return {
        "state":      "ok",
        "top_words":  top_words[:8],
        "avg_sentence": avg_sent,
        "shares": {
            "emoji":    round(has_emoji * 100 / n) if n else 0,
            "excl":     round(has_excl  * 100 / n) if n else 0,
            "question": round(has_quest * 100 / n) if n else 0,
        },
        "tone":       tone,
        "tone_score": tone_score,
        "headline":   _make_headline(avg_sent, top_words, tone),
    }


def _has_emoji(text: str) -> bool:
    return any(ord(c) > 0x2600 for c in (text or ""))


def _make_headline(avg_sent: float, top_words: List[Dict[str, Any]], tone: str) -> str:
    word_part = ""
    if top_words:
        ws = ", ".join([f'«{tw["word"]}»' for tw in top_words[:3]])
        word_part = f"Часто пишет {ws}. "
    sent_part = ""
    if avg_sent:
        if avg_sent < 60:
            sent_part = "Короткие предложения, ритм. "
        elif avg_sent > 140:
            sent_part = "Длинные предложения, обстоятельность. "
        else:
            sent_part = "Сбалансированный ритм. "
    tone_part = f"Тональность — {tone}."
    return word_part + sent_part + tone_part
