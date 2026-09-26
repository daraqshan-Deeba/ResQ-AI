import json
from unittest.mock import AsyncMock, patch

from app.models.schemas import ActionPlanContext, ServiceResult
from app.services.action_planner_service import (
    _select_protocol_lines,
    generate_action_plan_with_provenance,
)
from app.services.protocol_service import _load_bundle, get_protocol_plan, protocol_key_for
from tests.test_step4_triage import _classify


def test_slip_knee_uses_mobility_protocol_not_trauma_blurb():
    result = _classify(
        "i was walking through my garden and i slipped. my knee hurts what can i do"
    )
    key = protocol_key_for(result.category, None, result.matched_rule_or_example)
    assert key == "injury_mobility"
    _load_bundle.cache_clear()
    plan = get_protocol_plan(key)
    blob = " ".join(plan.immediate_actions + [plan.explanation]).lower()
    assert "bear weight" in blob or "knee" in blob
    assert "hemorrhage" not in plan.explanation.lower()


def test_select_protocol_lines_rejects_invented_steps():
    allowed = ["Sit down and rest the joint.", "Call 108 if you cannot stand."]
    picked = _select_protocol_lines(
        ["Sit down and rest the joint.", "Apply a tourniquet immediately"],
        allowed,
    )
    assert picked == ["Sit down and rest the joint."]


def test_groq_headline_kept_invented_first_aid_dropped():
    protocol = get_protocol_plan("injury_mobility")
    payload = {
        "headline": "You slipped in the garden and your knee hurts.",
        "selected_actions": [
            protocol.immediate_actions[0],
            "Invent a new surgery at home",
        ],
        "questions_to_ask_user": ["Can you put weight on the leg?"],
    }

    async def fake_groq(*_args, **_kwargs):
        return ServiceResult(available=True, data=json.dumps(payload))

    context = ActionPlanContext(
        user_description="I slipped. My knee hurts.",
        triage_category="injury",
        reply_language="English",
    )
    with patch(
        "app.services.action_planner_service.call_groq_safe",
        new=AsyncMock(side_effect=fake_groq),
    ):
        import asyncio

        plan, source, status = asyncio.run(
            generate_action_plan_with_provenance(
                context, protocol_key="injury_mobility"
            )
        )
    assert status == "available"
    assert source == "deterministic"
    assert "slipped" in plan.explanation.lower()
    assert "Invent a new surgery" not in " ".join(plan.immediate_actions)
    assert protocol.immediate_actions[0] in plan.immediate_actions


def test_non_english_uses_aligned_translations():
    protocol = get_protocol_plan("injury_mobility")
    payload = {
        "headline": "Aadmi gadi se gir gaya aur khoon nikal raha hai.",
        "questions_to_ask_user": ["Khoon tez nikal raha hai kya?"],
        "selected_actions": protocol.immediate_actions[:2],
        "translated_actions": [
            "Baith jao ya let jao, dard ho to weight mat dalo.",
            "Ghutne ya ankle ko aaram ki position mein rakho.",
        ],
        "selected_warnings": [protocol.safety_warnings[0]],
        "translated_warnings": ["Us pair pe chalna mat jaari rakho jo weight nahi le sakta."],
    }

    async def fake_groq(*_args, **_kwargs):
        return ServiceResult(available=True, data=json.dumps(payload))

    context = ActionPlanContext(
        user_description="gadi se gir gaya khoon nikal raha hai",
        triage_category="injury",
        reply_language="Hinglish",
    )
    with patch(
        "app.services.action_planner_service.call_groq_safe",
        new=AsyncMock(side_effect=fake_groq),
    ):
        import asyncio

        plan, _, status = asyncio.run(
            generate_action_plan_with_provenance(
                context, protocol_key="injury_mobility"
            )
        )
    assert status == "available"
    assert "gadi se gir" in plan.explanation.lower()
    assert plan.immediate_actions[0].startswith("Baith jao")
    assert "Sit or lie down" not in plan.immediate_actions[0]

