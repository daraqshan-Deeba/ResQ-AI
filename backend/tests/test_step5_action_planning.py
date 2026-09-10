"""
Step 5 Tests — Structured LLM Action Planning

Test Inventory:
  Schema Tests (1-6):
    1. Valid ActionPlan parses.
    2. Missing required field fails validation.
    3. Wrong type fails validation.
    4. Excessively long action is rejected.
    5. Excessively large list is rejected.
    6. Unexpected severity field does not become an accepted ActionPlan field.

  Groq Success Tests (7-12):
    7. Valid JSON response -> valid ActionPlan.
    8. JSON wrapped in Markdown code block -> unwrapped and parsed safely.
    9. Extra JSON fields -> handled according to Pydantic configuration (ignored, excluded).
    10. Empty response -> returns category fallback.
    11. Malformed JSON -> returns category fallback.
    12. Valid JSON with invalid schema -> returns category fallback.

  Failure Tests (13-17):
    13. Groq disabled -> fallback.
    14. Groq timeout -> fallback.
    15. Groq network error -> fallback.
    16. Groq rate limited -> fallback.
    17. Groq server error -> fallback.

  Safety & Authority Tests (18-24):
    18. LLM response with 'severity' cannot create severity authority.
    19. LLM response with 'emergency_level' cannot create emergency-level authority.
    20. LLM cannot overwrite supplied triage category.
    21. LLM cannot overwrite supplied weather risk.
    22. LLM cannot create arbitrary hospital recommendations.
    23. LLM cannot create arbitrary URLs (rejected -> fallback).
    24. LLM cannot invent emergency numbers when trusted numbers were supplied.

  Fallback Tests (25-32):
    25. Flooding fallback.
    26. Electrocution fallback.
    27. Injury fallback.
    28. Snakebite fallback.
    29. Cyclone fallback.
    30. Structural damage fallback.
    31. Accident fallback.
    32. Unclassified fallback.

  Determinism Test (33):
    33. Same fallback context produces the exact same ActionPlan.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.models.schemas import (
    ActionPlan,
    ActionPlanContext,
    EmergencyCategory,
    ServiceResult,
)
from app.services import action_planner_service
from app.services.action_planner_service import (
    DEFAULT_TRUSTED_CONTACTS,
    generate_action_plan,
    get_fallback_action_plan,
    parse_action_plan_json,
)


# Helper for running async calls cleanly in tests
def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_groq_result(available: bool, data: str = None, error_type: str = None):
    return ServiceResult(
        available=available,
        data=data,
        error_type=error_type,
        detail="Mocked detail",
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. SCHEMA TESTS (1–6)
# ─────────────────────────────────────────────────────────────────────────────

def test_1_valid_action_plan_parses():
    """Verify that a valid dictionary parses cleanly into an ActionPlan model."""
    data = {
        "immediate_actions": ["Move to high ground", "Turn off main power"],
        "safety_warnings": ["Do not touch live wires"],
        "when_to_seek_help": ["If water enters the building"],
        "questions_to_ask_user": ["Is everyone safe?"],
        "emergency_contacts": ["112", "108"],
        "explanation": "Standard flood response guidance.",
    }
    plan = ActionPlan.model_validate(data)
    assert len(plan.immediate_actions) == 2
    assert plan.explanation == "Standard flood response guidance."
    assert "112" in plan.emergency_contacts


def test_2_missing_required_field_fails_validation():
    """Verify that missing a required field (e.g. immediate_actions or explanation) fails validation."""
    # Missing immediate_actions
    with pytest.raises(ValidationError):
        ActionPlan.model_validate({
            "safety_warnings": ["Be careful"],
            "explanation": "Some explanation",
        })

    # Missing explanation
    with pytest.raises(ValidationError):
        ActionPlan.model_validate({
            "immediate_actions": ["Run"],
        })


def test_3_wrong_type_fails_validation():
    """Verify that wrong data types (e.g. string instead of list of strings) fail validation."""
    with pytest.raises(ValidationError):
        ActionPlan.model_validate({
            "immediate_actions": "This should be a list, not a string",
            "explanation": "Valid explanation",
        })

    with pytest.raises(ValidationError):
        ActionPlan.model_validate({
            "immediate_actions": [123, 456],  # not strings
            "explanation": "Valid explanation",
        })


def test_4_excessively_long_action_is_rejected():
    """Verify that action strings exceeding 500 characters are rejected."""
    huge_action = "A" * 550
    with pytest.raises(ValidationError):
        ActionPlan.model_validate({
            "immediate_actions": [huge_action],
            "explanation": "Valid explanation",
        })


def test_5_excessively_large_list_is_rejected():
    """Verify that action lists exceeding 15 items are rejected."""
    many_actions = [f"Step {i}" for i in range(20)]
    with pytest.raises(ValidationError):
        ActionPlan.model_validate({
            "immediate_actions": many_actions,
            "explanation": "Valid explanation",
        })


def test_6_unexpected_severity_field_does_not_become_accepted_field():
    """Verify that extra fields like 'severity' or 'emergency_level' are stripped and never accepted."""
    data = {
        "immediate_actions": ["Move safely"],
        "explanation": "Valid explanation",
        "severity": "CRITICAL_HAZARD",
        "emergency_level": "Level_5",
        "risk_score": 99,
    }
    plan = ActionPlan.model_validate(data)
    assert not hasattr(plan, "severity")
    assert not hasattr(plan, "emergency_level")
    assert not hasattr(plan, "risk_score")
    assert "severity" not in plan.model_dump()
    assert "emergency_level" not in plan.model_dump()
    assert "severity" not in ActionPlan.model_fields


# ─────────────────────────────────────────────────────────────────────────────
# 2. GROQ SUCCESS TESTS (7–12)
# ─────────────────────────────────────────────────────────────────────────────

def test_7_valid_json_response_to_valid_action_plan():
    """Verify that valid JSON from Groq produces a valid ActionPlan."""
    valid_json = json.dumps({
        "immediate_actions": ["Evacuate building", "Check on neighbors"],
        "safety_warnings": ["Watch for falling masonry"],
        "when_to_seek_help": ["If structural cracks widen"],
        "questions_to_ask_user": ["Are you outside?"],
        "emergency_contacts": ["National Emergency: 112"],
        "explanation": "Immediate evacuation plan for structural damage.",
    })

    context = ActionPlanContext(
        user_description="Building is shaking",
        triage_category="structural_damage",
    )

    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(True, data=valid_json)
        plan = _run(generate_action_plan(context))

    assert plan.immediate_actions[0] == "Evacuate building"
    assert "Watch for falling masonry" in plan.safety_warnings
    assert plan.explanation == "Immediate evacuation plan for structural damage."


def test_8_json_wrapped_in_markdown_unwrapped_and_parsed():
    """Verify that JSON wrapped in markdown code fences (```json ... ```) is safely parsed."""
    wrapped_json = (
        "```json\n"
        "{\n"
        '  "immediate_actions": ["Move to upper level"],\n'
        '  "safety_warnings": ["Do not touch switches"],\n'
        '  "when_to_seek_help": ["If water rises past floor"],\n'
        '  "questions_to_ask_user": [],\n'
        '  "emergency_contacts": ["112"],\n'
        '  "explanation": "Unwrapped markdown test"\n'
        "}\n"
        "```"
    )
    context = ActionPlanContext(
        user_description="Water rising",
        triage_category="flooding",
    )

    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(True, data=wrapped_json)
        plan = _run(generate_action_plan(context))

    assert plan.immediate_actions == ["Move to upper level"]
    assert plan.explanation == "Unwrapped markdown test"


def test_9_extra_json_fields_handled_cleanly():
    """Verify that unexpected fields in the LLM JSON output are dropped without failing."""
    extra_json = json.dumps({
        "immediate_actions": ["Keep calm"],
        "safety_warnings": [],
        "when_to_seek_help": [],
        "questions_to_ask_user": [],
        "emergency_contacts": ["112"],
        "explanation": "Explanation here",
        "hallucinated_field": "some extra value",
        "internal_metadata": {"confidence": 0.99},
    })
    context = ActionPlanContext(
        user_description="Minor injury",
        triage_category="injury",
    )

    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(True, data=extra_json)
        plan = _run(generate_action_plan(context))

    assert plan.immediate_actions == ["Keep calm"]
    assert not hasattr(plan, "hallucinated_field")
    assert not hasattr(plan, "internal_metadata")


def test_10_empty_response_returns_fallback():
    """Verify that an empty string response triggers the category fallback."""
    context = ActionPlanContext(
        user_description="Flooding",
        triage_category="flooding",
    )
    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(True, data="")
        plan = _run(generate_action_plan(context))

    fallback = get_fallback_action_plan("flooding")
    assert plan.explanation == fallback.explanation
    assert plan.immediate_actions == fallback.immediate_actions


def test_11_malformed_json_returns_fallback():
    """Verify that corrupt or truncated JSON triggers the fallback without crashing."""
    corrupt_json = '{"immediate_actions": ["Step 1", '  # unclosed JSON
    context = ActionPlanContext(
        user_description="Car crash",
        triage_category="accident",
    )
    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(True, data=corrupt_json)
        plan = _run(generate_action_plan(context))

    fallback = get_fallback_action_plan("accident")
    assert plan.explanation == fallback.explanation
    assert plan.immediate_actions == fallback.immediate_actions


def test_12_valid_json_with_invalid_schema_returns_fallback():
    """Verify that syntactically valid JSON missing required fields returns fallback."""
    invalid_schema_json = json.dumps({"notes": "Nothing relevant here"})
    context = ActionPlanContext(
        user_description="Snakebite",
        triage_category="snakebite",
    )
    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(True, data=invalid_schema_json)
        plan = _run(generate_action_plan(context))

    fallback = get_fallback_action_plan("snakebite")
    assert plan.explanation == fallback.explanation
    assert "antivenom" in " ".join(plan.immediate_actions).lower()


# ─────────────────────────────────────────────────────────────────────────────
# 3. FAILURE TESTS (13–17)
# ─────────────────────────────────────────────────────────────────────────────

def test_13_groq_disabled_returns_fallback():
    """Verify that disabled Groq service returns the deterministic fallback."""
    context = ActionPlanContext(
        user_description="Electric shock",
        triage_category="electrocution",
    )
    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(False, error_type="service_disabled")
        plan = _run(generate_action_plan(context))

    fallback = get_fallback_action_plan("electrocution")
    assert plan.explanation == fallback.explanation
    assert "power" in " ".join(plan.immediate_actions).lower()


def test_14_groq_timeout_returns_fallback():
    """Verify that a timeout error returns the deterministic fallback."""
    context = ActionPlanContext(
        user_description="Cyclone winds",
        triage_category="cyclone",
    )
    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(False, error_type="timeout")
        plan = _run(generate_action_plan(context))

    fallback = get_fallback_action_plan("cyclone")
    assert plan.explanation == fallback.explanation


def test_15_groq_network_error_returns_fallback():
    """Verify that network connection errors return the deterministic fallback."""
    context = ActionPlanContext(
        user_description="Injured knee",
        triage_category="injury",
    )
    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(False, error_type="network_error")
        plan = _run(generate_action_plan(context))

    fallback = get_fallback_action_plan("injury")
    assert plan.explanation == fallback.explanation


def test_16_groq_rate_limited_returns_fallback():
    """Verify that rate limit errors (HTTP 429) return the deterministic fallback."""
    context = ActionPlanContext(
        user_description="Flooding street",
        triage_category="flooding",
    )
    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(False, error_type="rate_limited")
        plan = _run(generate_action_plan(context))

    fallback = get_fallback_action_plan("flooding")
    assert plan.explanation == fallback.explanation


def test_17_groq_server_error_returns_fallback():
    """Verify that 500/502/503 server errors return the deterministic fallback."""
    context = ActionPlanContext(
        user_description="Unknown emergency",
        triage_category="unclassified",
    )
    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(False, error_type="server_error")
        plan = _run(generate_action_plan(context))

    fallback = get_fallback_action_plan("unclassified")
    assert plan.explanation == fallback.explanation


# ─────────────────────────────────────────────────────────────────────────────
# 4. SAFETY & AUTHORITY BOUNDARY TESTS (18–24)
# ─────────────────────────────────────────────────────────────────────────────

def test_18_llm_cannot_create_severity_authority():
    """Verify that even if the LLM injects 'severity': 'critical', ActionPlan drops it."""
    raw_response = json.dumps({
        "immediate_actions": ["Move safely"],
        "safety_warnings": [],
        "when_to_seek_help": [],
        "questions_to_ask_user": [],
        "emergency_contacts": ["112"],
        "explanation": "Safe guidance",
        "severity": "CRITICAL_RED_ALERT",
    })
    context = ActionPlanContext(user_description="Help", triage_category="flooding")

    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(True, data=raw_response)
        plan = _run(generate_action_plan(context))

    assert not hasattr(plan, "severity")
    assert "severity" not in plan.model_dump()


def test_19_llm_cannot_create_emergency_level_authority():
    """Verify that 'emergency_level': 'extreme' is stripped and never accepted."""
    raw_response = json.dumps({
        "immediate_actions": ["Stay indoors"],
        "safety_warnings": [],
        "when_to_seek_help": [],
        "questions_to_ask_user": [],
        "emergency_contacts": ["112"],
        "explanation": "Cyclone alert",
        "emergency_level": "Catastrophic",
    })
    context = ActionPlanContext(user_description="Wind", triage_category="cyclone")

    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(True, data=raw_response)
        plan = _run(generate_action_plan(context))

    assert not hasattr(plan, "emergency_level")
    assert "emergency_level" not in plan.model_dump()


def test_20_llm_cannot_overwrite_supplied_triage_category():
    """Verify that the caller's triage category cannot be mutated or redefined by the LLM."""
    context = ActionPlanContext(
        user_description="Water is entering my living room",
        triage_category="flooding",
    )
    raw_response = json.dumps({
        "immediate_actions": ["Look for snakes"],
        "safety_warnings": [],
        "when_to_seek_help": [],
        "questions_to_ask_user": [],
        "emergency_contacts": ["112"],
        "explanation": "Plan",
        "triage_category": "snakebite",  # LLM attempt to reclassify
        "category": "snakebite",
    })

    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(True, data=raw_response)
        plan = _run(generate_action_plan(context))

    # The plan does not contain a category field, and context remains unchanged
    assert not hasattr(plan, "triage_category")
    assert not hasattr(plan, "category")
    assert context.triage_category == "flooding"


def test_21_llm_cannot_overwrite_supplied_weather_risk():
    """Verify that the LLM cannot overwrite or alter the deterministic weather risk."""
    context = ActionPlanContext(
        user_description="Water is rising",
        triage_category="flooding",
        weather_risk={"score": 85, "level": "critical"},
    )
    raw_response = json.dumps({
        "immediate_actions": ["Move to safety"],
        "safety_warnings": [],
        "when_to_seek_help": [],
        "questions_to_ask_user": [],
        "emergency_contacts": ["112"],
        "explanation": "Plan",
        "weather_risk": {"score": 10, "level": "safe"},  # LLM attempt to downplay
        "risk_level": "safe",
    })

    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(True, data=raw_response)
        plan = _run(generate_action_plan(context))

    assert not hasattr(plan, "weather_risk")
    assert not hasattr(plan, "risk_level")
    assert context.weather_risk["score"] == 85
    assert context.weather_risk["level"] == "critical"


def test_22_llm_cannot_create_arbitrary_hospital_recommendations():
    """Verify that hospital names or recommendations injected by LLM are excluded."""
    raw_response = json.dumps({
        "immediate_actions": ["Go to City Hospital"],
        "safety_warnings": [],
        "when_to_seek_help": [],
        "questions_to_ask_user": [],
        "emergency_contacts": ["112"],
        "explanation": "Plan",
        "hospitals": ["Apollo Private Care", "Care Hospital Banjara Hills"],
        "nearby_hospitals": ["Fake Clinic"],
    })
    context = ActionPlanContext(user_description="Injury", triage_category="injury")

    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(True, data=raw_response)
        plan = _run(generate_action_plan(context))

    assert not hasattr(plan, "hospitals")
    assert not hasattr(plan, "nearby_hospitals")
    assert "hospitals" not in plan.model_dump()


def test_23_llm_cannot_create_arbitrary_urls():
    """Verify that LLM output containing arbitrary URLs is rejected and falls back safely."""
    raw_response = json.dumps({
        "immediate_actions": ["Visit https://malicious-emergency-site.com for rescue"],
        "safety_warnings": ["Check http://unverified-blog.org/firstaid"],
        "when_to_seek_help": [],
        "questions_to_ask_user": [],
        "emergency_contacts": ["112"],
        "explanation": "Click www.resq-fake.com to get help.",
    })
    context = ActionPlanContext(user_description="Flooding", triage_category="flooding")

    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(True, data=raw_response)
        plan = _run(generate_action_plan(context))

    # Because URL validation failed, fallback was returned
    all_text = (
        " ".join(plan.immediate_actions)
        + " "
        + " ".join(plan.safety_warnings)
        + " "
        + plan.explanation
    )
    assert "http://" not in all_text
    assert "https://" not in all_text
    assert "www." not in all_text
    assert plan.explanation == get_fallback_action_plan("flooding").explanation


def test_24_llm_cannot_invent_emergency_numbers_when_trusted_supplied():
    """Verify that hallucinated phone numbers are stripped/sanitized against trusted numbers."""
    trusted = ["National Emergency: 112", "Ambulance: 108"]
    context = ActionPlanContext(
        user_description="Chest pain",
        triage_category="injury",
        trusted_contacts=trusted,
    )
    raw_response = json.dumps({
        "immediate_actions": ["Keep resting"],
        "safety_warnings": [],
        "when_to_seek_help": [],
        "questions_to_ask_user": [],
        "emergency_contacts": [
            "Call 9876543210 (Fake Doctor)",
            "Helpline: 555-0199",
            "Call 108 immediately",
        ],
        "explanation": "Rest plan",
    })

    with patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = _mock_groq_result(True, data=raw_response)
        plan = _run(generate_action_plan(context))

    # The invented numbers '9876543210' and '555-0199' must NOT be in the plan's emergency contacts
    contacts_str = " ".join(plan.emergency_contacts)
    assert "9876543210" not in contacts_str
    assert "555-0199" not in contacts_str
    assert "108" in contacts_str


# ─────────────────────────────────────────────────────────────────────────────
# 5. FALLBACK TESTS (25–32)
# ─────────────────────────────────────────────────────────────────────────────

def test_25_flooding_fallback():
    plan = get_fallback_action_plan("flooding")
    assert isinstance(plan, ActionPlan)
    assert any("higher ground" in a.lower() for a in plan.immediate_actions)
    assert any("electrical" in w.lower() for w in plan.safety_warnings)


def test_26_electrocution_fallback():
    plan = get_fallback_action_plan("electrocution")
    assert isinstance(plan, ActionPlan)
    assert any("not touch" in a.lower() for a in plan.immediate_actions)
    assert any("power" in a.lower() for a in plan.immediate_actions)


def test_27_injury_fallback():
    plan = get_fallback_action_plan("injury")
    assert isinstance(plan, ActionPlan)
    assert any("pressure" in a.lower() for a in plan.immediate_actions)
    assert any("bleeding" in w.lower() for w in plan.when_to_seek_help)


def test_28_snakebite_fallback():
    plan = get_fallback_action_plan("snakebite")
    assert isinstance(plan, ActionPlan)
    assert any("still" in a.lower() for a in plan.immediate_actions)
    # Must explicitly warn against cutting, sucking, or tourniquets
    safety_text = " ".join(plan.safety_warnings).lower()
    assert "cut" in safety_text
    assert "tourniquet" in safety_text


def test_29_cyclone_fallback():
    plan = get_fallback_action_plan("cyclone")
    assert isinstance(plan, ActionPlan)
    assert any("indoors" in a.lower() or "structure" in a.lower() for a in plan.immediate_actions)
    assert any("eye" in w.lower() for w in plan.safety_warnings)


def test_30_structural_damage_fallback():
    plan = get_fallback_action_plan("structural_damage")
    assert isinstance(plan, ActionPlan)
    assert any("evacuate" in a.lower() for a in plan.immediate_actions)
    assert any("re-enter" in w.lower() for w in plan.safety_warnings)


def test_31_accident_fallback():
    plan = get_fallback_action_plan("accident")
    assert isinstance(plan, ActionPlan)
    assert any("hazard" in a.lower() or "traffic" in a.lower() for a in plan.immediate_actions)
    assert any("move" in w.lower() for w in plan.safety_warnings)


def test_32_unclassified_fallback():
    plan = get_fallback_action_plan("unclassified")
    assert isinstance(plan, ActionPlan)
    assert len(plan.immediate_actions) > 0
    assert any("112" in c for c in plan.emergency_contacts)


# ─────────────────────────────────────────────────────────────────────────────
# 6. DETERMINISM TEST (33)
# ─────────────────────────────────────────────────────────────────────────────

def test_33_same_fallback_context_produces_identical_action_plan():
    """Verify that multiple calls with the exact same context produce identical ActionPlans."""
    plan1 = get_fallback_action_plan("flooding")
    plan2 = get_fallback_action_plan("flooding")
    assert plan1.model_dump() == plan2.model_dump()

    plan_inj_1 = get_fallback_action_plan("injury", trusted_contacts=["112", "108"])
    plan_inj_2 = get_fallback_action_plan("injury", trusted_contacts=["112", "108"])
    assert plan_inj_1.model_dump() == plan_inj_2.model_dump()
