"""Тесты базы знаний Джарвиса (config/knowledge_base.py)."""

from config.knowledge_base import (
    ALL_PEOPLE, CREATOR, DEPUTIES_OF_HEAD, HEAD,
    deterministic_creator_answer, deterministic_person_answer,
    find_person, is_creator_question, kb_prompt_block,
)


# ---------------------------------------------------------------------------
# Состав
# ---------------------------------------------------------------------------

def test_creator_is_meister():
    assert "Мейстер" in CREATOR["full_name"]
    assert "психолог" in CREATOR["bio"].lower()


def test_head_is_grechishev():
    assert "Гречищев" in HEAD["full_name"]
    assert "Александр" in HEAD["full_name"]


def test_nine_deputies():
    assert len(DEPUTIES_OF_HEAD) == 9
    last_names = [d["full_name"].split(" ", 1)[0] for d in DEPUTIES_OF_HEAD]
    assert "Лубяной" in last_names
    assert "Лунькова" in last_names
    assert "Дмитриева" in last_names
    assert "Потиха" in last_names
    assert "Котов" in last_names
    assert "Цаплинский" in last_names
    assert "Ходасевич" in last_names
    assert "Коновалов" in last_names
    assert "Панчишный" in last_names


def test_all_people_includes_creator_head_and_deputies():
    assert CREATOR in ALL_PEOPLE
    assert HEAD in ALL_PEOPLE
    for d in DEPUTIES_OF_HEAD:
        assert d in ALL_PEOPLE


# ---------------------------------------------------------------------------
# is_creator_question
# ---------------------------------------------------------------------------

def test_creator_question_variants():
    assert is_creator_question("Кто тебя создал?")
    assert is_creator_question("Кто тебя разработал?")
    assert is_creator_question("кто твой автор")
    assert is_creator_question("Кем ты создан")


def test_creator_question_negative():
    assert not is_creator_question("привет")
    assert not is_creator_question("какая погода?")
    assert not is_creator_question("кто глава города")


# ---------------------------------------------------------------------------
# find_person
# ---------------------------------------------------------------------------

def test_find_person_by_lastname():
    p = find_person("Расскажи про Гречищева")
    assert p is not None
    assert "Гречищев" in p["full_name"]


def test_find_person_by_alias_glava():
    p = find_person("Кто такой глава города?")
    assert p is not None
    assert "Гречищев" in p["full_name"]


def test_find_person_meister():
    p = find_person("Что ты знаешь про Мейстера?")
    assert p is not None
    assert "Мейстер" in p["full_name"]


def test_find_person_zam():
    p = find_person("Кто такой Лубяной?")
    assert p is not None
    assert "Лубяной" in p["full_name"]


def test_find_person_unknown_returns_none():
    # Сидор Сидоров — гарантированно ни в KB-руководстве, ни в Совете депутатов
    p = find_person("Кто такой Сидоров Сидор Сидорович?")
    assert p is None


def test_find_person_short_query_returns_none():
    p = find_person("кто")
    assert p is None


# ---------------------------------------------------------------------------
# kb_prompt_block / deterministic answers
# ---------------------------------------------------------------------------

def test_kb_prompt_block_contains_creator_and_head():
    block = kb_prompt_block()
    assert "Мейстер" in block
    assert "Гречищев" in block
    assert "Лубяной" in block   # хотя бы один зам


def test_creator_answer_starts_with_creator():
    out = deterministic_creator_answer()
    assert "Мейстер" in out


def test_person_answer_includes_role_and_bio():
    out = deterministic_person_answer(HEAD)
    assert "Гречищев" in out
    assert "Глава" in out
