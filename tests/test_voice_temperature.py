"""Тесты раскрытия °C для TTS (произношение градусов Цельсия)."""

from ai.voice_service import expand_temperatures, normalize_for_tts


# ---------------------------------------------------------------------------
# expand_temperatures
# ---------------------------------------------------------------------------

def test_simple_positive():
    out = expand_temperatures("Сейчас +12°C")
    assert "градусов Цельсия" in out
    assert "плюс" in out
    assert "12" in out
    assert "°" not in out


def test_simple_negative():
    out = expand_temperatures("Утром было -3°C")
    assert "минус" in out
    assert "3 градуса" in out  # 3 → «градуса»


def test_zero_no_sign():
    out = expand_temperatures("0°C — ровно ноль")
    assert "0 градусов Цельсия" in out
    assert "плюс" not in out
    assert "минус" not in out


def test_unsigned_positive():
    out = expand_temperatures("Температура 21°C")
    assert "21 градус" in out  # 21 → «градус» (последняя цифра 1, не 11)


def test_singular_one():
    out = expand_temperatures("ровно 1°C")
    assert "1 градус Цельсия" in out


def test_few_form_two_three_four():
    assert "2 градуса Цельсия" in expand_temperatures("2°C")
    assert "3 градуса Цельсия" in expand_temperatures("3°C")
    assert "24 градуса Цельсия" in expand_temperatures("24°C")


def test_many_form_eleven_to_fourteen():
    assert "11 градусов Цельсия" in expand_temperatures("11°C")
    assert "13 градусов Цельсия" in expand_temperatures("13°C")
    assert "14 градусов Цельсия" in expand_temperatures("14°C")


def test_many_form_5_to_20():
    assert "5 градусов Цельсия" in expand_temperatures("5°C")
    assert "10 градусов Цельсия" in expand_temperatures("10°C")


def test_handles_minus_unicode():
    """U+2212 (−) часто используется в проектах вместо обычного дефиса."""
    out = expand_temperatures("Сейчас −5°C")
    assert "минус 5 градусов Цельсия" in out


def test_handles_cyrillic_c():
    """Иногда в данных приходит русская «С» вместо латинской C."""
    out = expand_temperatures("+8°С")  # русская С
    assert "плюс 8 градусов Цельсия" in out


def test_no_change_when_no_temperature():
    out = expand_temperatures("Просто текст без температуры")
    assert out == "Просто текст без температуры"


def test_empty_unchanged():
    assert expand_temperatures("") == ""


# ---------------------------------------------------------------------------
# normalize_for_tts тоже подхватывает expand
# ---------------------------------------------------------------------------

def test_normalize_for_tts_expands_temperature():
    out = normalize_for_tts("Погода: +10°C, ясно")
    assert "градусов Цельсия" in out
    assert "10" in out
    assert "°" not in out
