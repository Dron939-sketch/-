"""Тесты раскрытия единиц измерения для голоса."""

from ai.voice_service import expand_units, normalize_for_tts


def test_percent_singular_form():
    out = expand_units("Доля 1%")
    assert "1 процент" in out


def test_percent_few_form():
    assert "3 процента" in expand_units("выросло на 3%")
    assert "24 процента" in expand_units("24%")


def test_percent_many_form():
    assert "5 процентов" in expand_units("упало на 5%")
    assert "11 процентов" in expand_units("11%")
    assert "25 процентов" in expand_units("25%")


def test_rubles_decline():
    assert "1 рубль" in expand_units("выручка 1 руб")
    assert "2 рубля" in expand_units("2 руб")
    assert "5 рублей" in expand_units("5 руб")
    assert "11 рублей" in expand_units("11 руб")
    # С точкой («руб.»)
    assert "10 рублей" in expand_units("выручка 10 руб.")


def test_kmh():
    assert "60 километров в час" in expand_units("ехал 60 км/ч")
    assert "1 километр в час" in expand_units("1 км/ч")
    assert "3 километра в час" in expand_units("3 км/ч")


def test_ms():
    assert "5 метров в секунду" in expand_units("ветер 5 м/с")
    assert "1 метр в секунду" in expand_units("1 м/с")
    assert "2 метра в секунду" in expand_units("2 м/с")


def test_million():
    assert "5 миллионов" in expand_units("стоимость 5 млн")
    assert "1 миллион" in expand_units("выручка 1 млн")
    assert "3 миллиона" in expand_units("3 млн")


def test_billion():
    assert "2 миллиарда" in expand_units("бюджет 2 млрд")
    assert "10 миллиардов" in expand_units("10 млрд")


def test_thousand():
    assert "5 тысяч" in expand_units("население 5 тыс")
    assert "1 тысяча" in expand_units("1 тыс")
    assert "2 тысячи" in expand_units("2 тыс")
    # С точкой
    assert "10 тысяч" in expand_units("10 тыс.")


def test_no_unit_unchanged():
    assert expand_units("просто текст") == "просто текст"


def test_empty_unchanged():
    assert expand_units("") == ""


def test_combination():
    out = expand_units("проект на 5 млн руб, рост 20%")
    assert "миллион" in out
    assert "процент" in out


def test_normalize_for_tts_runs_units():
    out = normalize_for_tts("Доля 25% — много")
    assert "процентов" in out
