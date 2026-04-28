"""Лёгкий keyword-based детектор эмоций для Ко-пилота.

Адаптация из проекта Frederick (services/emotion_detector.py). Без
DeepSeek-вызова — детектор быстрый и бесплатный, работает на словарях.
Возвращает emotion + tone + instruction для подмеса в system prompt.

Когда хочется городского контекста (тревога мэра при кризисе,
радость при росте УБ) — те же tone'ы, что у психологического
ассистента Frederick, потому что собеседник тот же — человек с
эмоциями. Меняется только тема разговора.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Карты эмоция → тон → инструкция в prompt
# ---------------------------------------------------------------------------

EMOTION_TONES: Dict[str, str] = {
    "sadness":      "gentle",
    "anger":        "calm",
    "anxiety":      "grounding",
    "joy":          "warm",
    "confusion":    "clear",
    "neutral":      "friendly",
    "frustration":  "patient",
    "loneliness":   "warm",
    "fear":         "reassuring",
    "guilt":        "accepting",
}

TONE_INSTRUCTIONS: Dict[str, str] = {
    "gentle":      "Будь мягким, не сыпь цифрами в первой фразе. Сначала признай чувства.",
    "calm":        "Не спорь. Спокойно перечисли факты, дай выговориться.",
    "grounding":   "Упрости. Один конкретный шаг. Без катастрофизации.",
    "warm":        "Раздели радость. Подкрепи цифрой если уместно.",
    "clear":       "Упрости ситуацию, дай один конкретный шаг — без лишних деталей.",
    "friendly":    "Дружелюбно и по делу.",
    "patient":     "Прояви терпение. Признай, что ситуация сложная. Поддержи.",
    "reassuring":  "Успокой. Объясни что под контролем, что нет — честно.",
    "accepting":   "Прими без осуждения. Без морали.",
}


# ---------------------------------------------------------------------------
# Keyword-словари (case-insensitive substring match)
# ---------------------------------------------------------------------------

_KEYWORDS: List[Tuple[str, Tuple[str, ...]]] = [
    ("sadness",     ("грустно", "плачу", "тоска", "больно", "потеря", "умер", "скучаю", "печаль")),
    ("anger",       ("бесит", "злюсь", "ненавижу", "достало", "задолбал", "раздражает", "взбесил")),
    ("anxiety",     ("тревога", "страшно", "паника", "нервничаю", "волнуюсь", "боюсь", "переживаю", "беспоко")),
    ("joy",         ("рад", "счастлив", "ура", "здорово", "отлично", "класс", "победа", "получилось", "класс")),
    ("confusion",   ("не знаю", "запутал", "не понимаю", "растерян", "не могу решить", "странно")),
    ("frustration", ("устал", "надоело", "сил нет", "выгорел", "замучил")),
    ("loneliness",  ("одинок", "никому не нужен", "никто не понимает", "не с кем")),
    ("fear",        ("боязно", "опасно", "пугает", "ужас")),
    ("guilt",       ("виноват", "вина", "стыдно", "не справился")),
]


def _keyword_detect(text: str) -> Optional[str]:
    """Быстрый кейворд-поиск с границами слов (чтобы «температура» не
    триггерила «ура»). Возвращает первую сматченную эмоцию или None.
    """
    if not text or len(text) < 3:
        return None
    t = text.lower()
    for emo, words in _KEYWORDS:
        for w in words:
            # Stem-prefix match: ищем как корень в начале слова —
            # «нервничаю», «нервничал», «нервничать» все ловятся «нервнич».
            # Но «температура» не ловит «ура» — \bура\b требует пробела/конца.
            pattern = r"(?<![а-яёa-z])" + re.escape(w) + r"(?:[а-яёa-z]*)?"
            if re.search(pattern, t, flags=re.IGNORECASE | re.UNICODE):
                return emo
    return None


def detect(text: str) -> Dict[str, str]:
    """Главная точка входа.

    Возвращает dict с тремя ключами:
      emotion    — короткая метка ('sadness' / 'joy' / 'neutral' и т.д.)
      tone       — рекомендованный тон ответа
      instruction — кусок текста для подмеса в system prompt
    """
    if not text or len(text) < 3:
        return {
            "emotion":     "neutral",
            "tone":        "friendly",
            "instruction": TONE_INSTRUCTIONS["friendly"],
        }
    emo = _keyword_detect(text) or "neutral"
    tone = EMOTION_TONES.get(emo, "friendly")
    return {
        "emotion":     emo,
        "tone":        tone,
        "instruction": TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS["friendly"]),
    }
