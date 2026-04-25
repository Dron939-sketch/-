"""Unit tests for the refactored DeputyAgendaManager (lightweight version).

Verifies that the manipulative features intentionally removed in the
refactor stay removed (regression guards), and that the kept-functionality
still works.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from deputy_agenda_manager import (
    Deputy,
    DeputyAgendaManager,
    DeputyDraft,
    DeputyRole,
    MessageTone,
    Platform,
    TopicTask,
)


# ---------------------------------------------------------------------------
# Regression guards: features deliberately removed
# ---------------------------------------------------------------------------


def test_deputy_has_no_loyalty_field():
    """Loyalty-to-administration scoring must not exist on the model."""
    deputy = Deputy(
        id="d1", name="Иванов", role=DeputyRole.SPEAKER,
        district="Центральный", party="X",
    )
    assert not hasattr(deputy, "loyalty"), \
        "loyalty was removed in lightweight refactor — must not come back"


def test_message_tone_has_no_offensive():
    """OFFENSIVE tone (criticise opponents) must not exist."""
    assert not any(t.name == "OFFENSIVE" for t in MessageTone), \
        "OFFENSIVE tone was removed — must not come back"


def test_manager_has_no_wave_generator():
    """generate_coordinated_posts (wave 30/40/30) must not exist."""
    mgr = DeputyAgendaManager("Коломна")
    assert not hasattr(mgr, "generate_coordinated_posts"), \
        "wave-generation was removed — must not come back"
    assert not hasattr(mgr, "_get_forbidden_topics"), \
        "party-based forbidden_topics was removed — must not come back"


def test_suggest_draft_replaces_generate_post_content():
    """`suggest_draft` is the new API; legacy `generate_post_content` gone."""
    mgr = DeputyAgendaManager("Коломна")
    assert hasattr(mgr, "suggest_draft")
    assert not hasattr(mgr, "generate_post_content")


# ---------------------------------------------------------------------------
# Functional behaviour — what should still work
# ---------------------------------------------------------------------------


@pytest.fixture
def manager() -> DeputyAgendaManager:
    mgr = DeputyAgendaManager("Коломна")
    mgr.add_deputy(Deputy(
        id="d1", name="Иванов", role=DeputyRole.SPEAKER,
        district="Центральный", party="X", sectors=["все"],
    ))
    mgr.add_deputy(Deputy(
        id="d2", name="Петров", role=DeputyRole.SECTOR_LEAD,
        district="Колычёво", party="Y", sectors=["ЖКХ", "благоустройство"],
    ))
    mgr.add_deputy(Deputy(
        id="d3", name="Сидорова", role=DeputyRole.DISTRICT_REP,
        district="Щурово", party="Z", sectors=["образование"],
    ))
    return mgr


def test_create_topic_assigns_id_and_defaults(manager):
    topic = manager.create_topic({
        "title": "Благоустройство дворов",
        "priority": "high",
        "target_tone": MessageTone.POSITIVE,
        "talking_points": ["t1"],
    })
    assert topic.id.startswith("topic_")
    assert topic.priority == "high"
    assert topic.target_tone == MessageTone.POSITIVE
    assert topic.required_posts == 5  # default
    assert topic.deadline > datetime.now(timezone.utc)


def test_auto_assign_picks_speaker_for_high_priority(manager):
    topic = manager.create_topic({
        "title": "Какая-то общая тема",
        "priority": "high",
        "target_tone": MessageTone.NEUTRAL,
    })
    chosen = manager.assign_deputies(topic.id)
    assert "d1" in chosen, "SPEAKER must be assigned to high-priority topics"


def test_auto_assign_matches_by_sector(manager):
    topic = manager.create_topic({
        "title": "ЖКХ: проблемы с водой",
        "priority": "medium",
        "target_tone": MessageTone.PROTECTIVE,
        "key_messages": ["благоустройство улиц"],
    })
    chosen = manager.assign_deputies(topic.id)
    assert "d2" in chosen, "deputy with matching sector must be assigned"


def test_auto_assign_matches_by_district(manager):
    topic = manager.create_topic({
        "title": "Открытие парка в Щурово",
        "priority": "low",
        "target_tone": MessageTone.POSITIVE,
    })
    chosen = manager.assign_deputies(topic.id)
    assert "d3" in chosen


def test_explicit_deputy_ids_override_auto(manager):
    topic = manager.create_topic({"title": "X", "priority": "low"})
    chosen = manager.assign_deputies(topic.id, deputy_ids=["d2"], auto=False)
    assert chosen == ["d2"]


def test_explicit_assignment_filters_unknown_ids(manager):
    topic = manager.create_topic({"title": "X", "priority": "low"})
    chosen = manager.assign_deputies(topic.id, deputy_ids=["d1", "ghost"])
    assert chosen == ["d1"]


def test_suggest_draft_returns_draft_with_flag(manager):
    topic = manager.create_topic({
        "title": "Открытие школы",
        "priority": "medium",
        "target_tone": MessageTone.POSITIVE,
        "talking_points": ["t1", "t2"],
    })
    draft = manager.suggest_draft(topic.id, "d1")
    assert isinstance(draft, DeputyDraft)
    assert draft.is_draft is True, \
        "draft must be flagged as DRAFT, not delivered as a ready-to-publish post"
    assert "черновик" in draft.note.lower(), \
        "human-readable note must explicitly say 'черновик'"
    assert draft.talking_points == ["t1", "t2"]


def test_suggest_draft_keeps_placeholders_visible(manager):
    """Plaholders like [период], [факты] must remain unfilled — deputy fills them."""
    topic = manager.create_topic({
        "title": "Отчёт по бюджету",
        "priority": "medium",
        "target_tone": MessageTone.NEUTRAL,
    })
    draft = manager.suggest_draft(topic.id, "d1")
    # At least one placeholder marker must remain — proves we don't hardcode
    # fake numbers in the deputy's mouth.
    assert "[" in draft.suggested_text and "]" in draft.suggested_text


def test_suggest_draft_unknown_deputy_raises(manager):
    topic = manager.create_topic({"title": "X", "priority": "low"})
    with pytest.raises(KeyError):
        manager.suggest_draft(topic.id, "ghost")


def test_register_post_increments_topic_counter(manager):
    topic = manager.create_topic({
        "title": "X", "priority": "low", "required_posts": 2,
    })
    manager.assign_deputies(topic.id, deputy_ids=["d1"])
    manager.register_post({
        "deputy_id": "d1", "topic_id": topic.id,
        "platform": "telegram", "content": "...", "views": 100,
    })
    assert topic.completed_posts == 1


def test_topic_report_aggregates_metrics(manager):
    topic = manager.create_topic({
        "title": "X", "priority": "low", "required_posts": 4,
    })
    manager.assign_deputies(topic.id, deputy_ids=["d1", "d2"])
    manager.register_post({
        "deputy_id": "d1", "topic_id": topic.id,
        "platform": "telegram", "views": 500, "likes": 30,
    })
    manager.register_post({
        "deputy_id": "d2", "topic_id": topic.id,
        "platform": "vk", "views": 200, "likes": 10,
    })
    report = manager.topic_report(topic.id)
    assert report["completed_posts"] == 2
    assert report["total_views"] == 700
    assert report["total_likes"] == 40
    assert report["completion_rate"] == 0.5  # 2 of 4
    assert len(report["by_deputy"]) == 2


def test_briefing_only_if_deputy_has_topics(manager):
    # No topics yet → no briefing.
    assert manager.build_briefing("d1") is None

    topic = manager.create_topic({
        "title": "X", "priority": "high",
        "target_tone": MessageTone.POSITIVE,
        "talking_points": ["a", "b"],
    })
    manager.assign_deputies(topic.id, deputy_ids=["d1"])

    briefing = manager.build_briefing("d1", recommended_hashtags=["#hash"])
    assert briefing is not None
    assert briefing.deputy_name == "Иванов"
    assert len(briefing.topics) == 1
    assert "#hash" in briefing.recommended_hashtags
    assert briefing.forbidden_topics == [], \
        "no auto-populated forbidden topics — only explicit input"


def test_briefing_forbidden_topics_only_from_explicit_input(manager):
    """The lightweight version must NOT auto-populate forbidden_topics
    based on party membership."""
    topic = manager.create_topic({"title": "X", "priority": "low"})
    manager.assign_deputies(topic.id, deputy_ids=["d2"])  # d2 is party "Y", not ЕР
    briefing = manager.build_briefing("d2")
    assert briefing.forbidden_topics == [], \
        "party-based forbidden_topics must NOT be auto-populated"

    briefing2 = manager.build_briefing(
        "d2", forbidden_topics=["личные нападки"],
    )
    assert briefing2.forbidden_topics == ["личные нападки"]


def test_coordinator_dashboard_lists_active_topics(manager):
    t1 = manager.create_topic({
        "title": "T1", "priority": "high",
        "deadline": datetime.now(timezone.utc) + timedelta(days=1),
    })
    t2 = manager.create_topic({
        "title": "T2", "priority": "medium",
        "deadline": datetime.now(timezone.utc) + timedelta(days=5),
    })
    manager.assign_deputies(t1.id, deputy_ids=["d1"])
    manager.assign_deputies(t2.id, deputy_ids=["d2"])

    dash = manager.coordinator_dashboard()
    assert dash["totals"]["deputies"] == 3
    assert dash["totals"]["active_topics"] == 2
    titles = [t["title"] for t in dash["active_topics"]]
    assert titles[0] == "T1"  # earliest deadline first
