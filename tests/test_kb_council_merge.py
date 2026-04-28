"""Тесты объединения 25 депутатов из config/deputies.py с KB."""

from config.knowledge_base import (
    ALL_PEOPLE, COUNCIL_DEPUTIES, find_person, kb_prompt_block,
)


def test_council_loaded_25():
    """Все 25 действующих депутатов из config/deputies.py подгрузились."""
    assert len(COUNCIL_DEPUTIES) == 25


def test_council_in_all_people():
    assert all(d in ALL_PEOPLE for d in COUNCIL_DEPUTIES)


def test_find_bratushkov():
    p = find_person("Расскажи про Братушкова")
    assert p is not None
    assert "Братушков" in p["full_name"]
    assert "Депутат" in p["role"]


def test_find_androsov():
    p = find_person("Кто такой Андросов")
    assert p is not None
    assert "Андросов" in p["full_name"]


def test_find_kossov():
    p = find_person("Расскажи про Коссова")
    assert p is not None
    assert "Коссов" in p["full_name"]


def test_find_random_council_member():
    """Любой депутат из списка должен находиться по фамилии."""
    for d in COUNCIL_DEPUTIES[:5]:
        last = d["full_name"].split(" ", 1)[0]
        # Матч должен быть с padding-ом, чтобы query был >= 5 символов
        p = find_person(f"Расскажи про {last}а")
        assert p is not None, f"{last} не найден через 'про {last}а'"


def test_kb_prompt_includes_council_count():
    block = kb_prompt_block()
    assert "Совет депутатов" in block
    assert "25" in block


def test_council_deputy_has_district_in_bio():
    """Округ из config/deputies.py попадает в bio."""
    p = find_person("Кто такой Братушков")
    assert p is not None
    # Братушков из округа №5
    assert "Округ" in p["bio"]
