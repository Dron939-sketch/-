"""Тесты config/archetypes.py — 12 архетипов + suggest + match score."""

from config.archetypes import (
    ARCHETYPES, archetype_match_score, all_codes, get, suggest_for_deputy,
)


def test_twelve_archetypes():
    assert len(ARCHETYPES) == 12


def test_codes_are_unique():
    codes = all_codes()
    assert len(codes) == len(set(codes))


def test_each_has_required_fields():
    required = {"code", "name", "short", "voice", "do", "dont",
                "sample_post", "sectors_fit"}
    for a in ARCHETYPES:
        assert required.issubset(a.keys()), f"{a.get('code')} missing fields"


def test_get_valid():
    a = get("caregiver")
    assert a is not None
    assert a["name"] == "Заботливый"


def test_get_unknown_returns_none():
    assert get("villain") is None


# ---------------------------------------------------------------------------
# suggest_for_deputy
# ---------------------------------------------------------------------------

def test_suggest_chairman_is_ruler():
    deputy = {
        "role":    "speaker",
        "sectors": ["общая_повестка"],
        "note":    "Председатель Совета депутатов",
    }
    a = suggest_for_deputy(deputy)
    assert a["code"] == "ruler"


def test_suggest_speaker_with_many_sectors_is_sage():
    deputy = {
        "role":    "speaker",
        "sectors": ["a", "b", "c", "d", "e"],
        "note":    "Заместитель председателя",
    }
    a = suggest_for_deputy(deputy)
    assert a["code"] == "sage"


def test_suggest_caregiver_for_socialprotection():
    deputy = {"role": "district_rep", "sectors": ["соцзащита"]}
    a = suggest_for_deputy(deputy)
    # caregiver или другой с соцзащитой в sectors_fit
    assert any(
        "соцзащита" in [f.lower() for f in (x.get("sectors_fit") or [])]
        for x in [a]
    )


def test_suggest_creator_for_culture_or_youth():
    deputy = {"role": "district_rep", "sectors": ["молодёжь", "образование"]}
    a = suggest_for_deputy(deputy)
    # Должен быть из культуры/молодёжи
    assert a["code"] in ("creator", "explorer", "everyman", "innocent")


def test_suggest_default_everyman_when_no_match():
    deputy = {"role": "district_rep", "sectors": ["несуществующий_сектор"]}
    a = suggest_for_deputy(deputy)
    assert a["code"] == "everyman"


# ---------------------------------------------------------------------------
# archetype_match_score
# ---------------------------------------------------------------------------

def test_match_score_caregiver_high():
    a = get("caregiver")
    score = archetype_match_score(
        "Сегодня помогла бабушке Марии — будем поддерживать вместе.", a,
    )
    assert score >= 0.5


def test_match_score_ruler_high_with_percent():
    a = get("ruler")
    score = archetype_match_score(
        "Итог квартала: 96% домов прошли отопительный сезон без аварий. "
        "Ответственный — зам по ЖКХ.", a,
    )
    assert score >= 0.5


def test_match_score_sage_high_with_data():
    a = get("sage")
    score = archetype_match_score(
        "Данные показывают тренд: рост коммунальных жалоб на 15%.", a,
    )
    assert score >= 0.5


def test_match_score_returns_zero_for_empty():
    a = get("caregiver")
    assert archetype_match_score("", a) == 0.0


def test_match_score_irrelevant_text_low():
    a = get("ruler")
    score = archetype_match_score(
        "Сегодня я просто гулял в парке и думал о жизни.", a,
    )
    assert score < 0.3
