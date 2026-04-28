"""Reality-check the static deputy registry.

Если кто-то расширяет Совет (новый созыв, перевыборы), эти тесты
ломаются и форсируют автора правки осмысленно отметить, что состав
действительно поменялся.
"""

from __future__ import annotations

from collections import Counter

from config.deputies import (
    DEPUTIES_BY_CITY,
    KOLOMNA_DEPUTIES,
    deputies_for_city,
)


def test_kolomna_has_25_deputies():
    assert len(KOLOMNA_DEPUTIES) == 25


def test_kolomna_five_districts_five_each():
    by_district = Counter(d["district"] for d in KOLOMNA_DEPUTIES)
    assert set(by_district.keys()) == {
        "Округ №1", "Округ №2", "Округ №3", "Округ №4", "Округ №5",
    }
    assert all(count == 5 for count in by_district.values()), by_district


def test_external_ids_are_unique():
    ids = [d["external_id"] for d in KOLOMNA_DEPUTIES]
    assert len(ids) == len(set(ids))


def test_leadership_present_and_in_district_5():
    """Председатель + 2 зама — все из Округа №5 (фактический расклад)."""
    leaders = [d for d in KOLOMNA_DEPUTIES if d["role"] == "speaker"]
    assert len(leaders) == 3
    assert {d["external_id"] for d in leaders} == {
        "bratushkov-nv", "androsov-rv", "kossov-vs",
    }
    assert all(d["district"] == "Округ №5" for d in leaders)


def test_chairman_is_bratushkov():
    chair = next(d for d in KOLOMNA_DEPUTIES if d["external_id"] == "bratushkov-nv")
    assert chair["name"] == "Братушков Николай Владимирович"
    assert "Председатель" in chair.get("note", "")


def test_every_deputy_has_at_least_one_sector():
    for d in KOLOMNA_DEPUTIES:
        assert d.get("sectors"), f"{d['name']} без секторов"


def test_leaders_have_broader_coverage_than_district_reps():
    leaders = [d for d in KOLOMNA_DEPUTIES if d["role"] == "speaker"]
    reps = [d for d in KOLOMNA_DEPUTIES if d["role"] == "district_rep"]
    avg_leader = sum(len(d["sectors"]) for d in leaders) / len(leaders)
    avg_rep = sum(len(d["sectors"]) for d in reps) / len(reps)
    assert avg_leader > avg_rep


def test_deputies_for_city_returns_empty_for_unknown_city():
    assert deputies_for_city("Нет-такого-города") == []


def test_deputies_for_city_returns_kolomna_roster():
    result = deputies_for_city("Коломна")
    assert result is KOLOMNA_DEPUTIES or len(result) == 25


def test_kolomna_in_registry_map():
    assert "Коломна" in DEPUTIES_BY_CITY


def test_specific_known_names_present():
    """Pin-test: имена из публичных источников (kolomnagrad.ru) на месте."""
    names = {d["name"] for d in KOLOMNA_DEPUTIES}
    must_have = {
        "Братушков Николай Владимирович",
        "Андросов Роман Викторович",
        "Коссов Валерий Семенович",
        "Леонова Жанна Константиновна",
        "Иванов Алексей Вячеславович",
        "Бычкова Екатерина Владимировна",
    }
    assert must_have.issubset(names), must_have - names
