"""Тесты keyword-based детектора эмоций."""

from ai.emotion import EMOTION_TONES, TONE_INSTRUCTIONS, detect


def test_neutral_for_empty():
    out = detect("")
    assert out["emotion"] == "neutral"
    assert out["tone"] == "friendly"


def test_neutral_for_short():
    out = detect("ok")
    assert out["emotion"] == "neutral"


def test_sadness():
    out = detect("Мне грустно сегодня, плачу")
    assert out["emotion"] == "sadness"
    assert out["tone"] == "gentle"
    assert "признай" in out["instruction"].lower()


def test_anger():
    out = detect("Меня бесит этот процесс")
    assert out["emotion"] == "anger"
    assert out["tone"] == "calm"


def test_anxiety():
    out = detect("Очень нервничаю по этому поводу")
    assert out["emotion"] == "anxiety"
    assert out["tone"] == "grounding"


def test_joy():
    out = detect("Я так рад этому решению!")
    assert out["emotion"] == "joy"
    assert out["tone"] == "warm"


def test_confusion():
    out = detect("Не понимаю что делать")
    assert out["emotion"] == "confusion"
    assert out["tone"] == "clear"


def test_unknown_falls_back_to_neutral():
    out = detect("Какая температура воздуха в городе?")
    assert out["emotion"] == "neutral"
    assert out["tone"] == "friendly"


def test_first_keyword_wins():
    # «грустно» появляется раньше «рад» в нашем словаре
    out = detect("Мне сегодня грустно но я рад")
    assert out["emotion"] == "sadness"


def test_tone_instructions_complete():
    # Каждой эмоции должен соответствовать существующий tone и инструкция
    for emo, tone in EMOTION_TONES.items():
        assert tone in TONE_INSTRUCTIONS, f"missing instruction for {tone}"
