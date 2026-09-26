"""Core safety invariants for Slice A of the ResQ thesis pipeline."""

import asyncio
from unittest.mock import AsyncMock, patch

from app.models.schemas import ServiceResult
from app.services.emergency_orchestrator import determine_emergency_level, orchestrate_emergency_assessment
from app.services.evidence_map import EVIDENCE_TOOL_NAMES
from app.services.safety_net import detect_life_threats
from app.services.triage_service import classify
from app.services.action_planner_service import parse_action_plan_json, get_fallback_action_plan, DEFAULT_TRUSTED_CONTACTS


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_unclassified_is_unknown_not_low():
    assert determine_emergency_level("unclassified") == "Unknown"


def test_fire_safety_net_forces_high():
    hit = detect_life_threats("fire in my building and smoke everywhere")
    assert "fire" in hit.hits
    assert hit.forced_level in {"High", "Critical"}
    assert hit.protocol_key == "fire"


def test_phone_flames_is_burn_not_building_fire():
    text = "my phone turned into flames and i burnt my hand"
    hit = detect_life_threats(text)
    assert "fire" not in hit.hits
    assert "burn" in hit.hits
    assert hit.protocol_key == "burn"
    assert hit.forced_level == "High"


def test_phone_burn_assessment_uses_burn_protocol():
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:
        mock_w.return_value = ServiceResult(available=False, error_type="timeout")
        mock_g.return_value = ServiceResult(available=False, error_type="service_disabled")
        res = _run(orchestrate_emergency_assessment(
            description="my phone turned into flames and i burnt my hand",
        ))
    assert res.protocol_key == "burn"
    plan_text = " ".join(res.action_plan.immediate_actions).lower()
    assert "leave the building" not in plan_text
    assert "cool" in plan_text
    assert res.emergency_level in {"High", "Critical"}


def test_chest_pain_is_critical():
    hit = detect_life_threats("heart attack, severe chest pain")
    assert hit.forced_level == "Critical"


def test_fire_assessment_not_low():
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:
        mock_w.return_value = ServiceResult(available=False, error_type="timeout")
        mock_g.return_value = ServiceResult(available=False, error_type="service_disabled")
        res = _run(orchestrate_emergency_assessment(description="fire in my building and smoke everywhere"))
    assert res.emergency_level != "Low"
    assert res.emergency_level in {"High", "Critical"}


def test_negation_not_high_flooding():
    result = _run(classify("There is no flooding here, just checking"))
    assert result.category != "flooding" or result.confidence < 0.9


def test_historical_life_threat_not_dropped():
    result = _run(classify("bitten by a snake last week and now cannot breathe"))
    assert result.category != "unclassified" or "breathe" in result.explanation.lower()
    # present-tense danger should not short-circuit to historical unclassified
    assert not (
        result.category == "unclassified"
        and "past-tense" in result.explanation
    )


def test_weather_failure_not_fake_safe():
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock):
        mock_w.return_value = ServiceResult(available=False, error_type="timeout")
        res = _run(orchestrate_emergency_assessment(
            description="Water is rising inside the house",
            lat=17.4,
            lon=78.5,
        ))
    assert res.weather.get("score") is None
    assert res.weather.get("level") not in {"safe"}
    assert res.weather.get("temp_c") != 25.0 or res.weather.get("status") != "available"


def test_llm_dangerous_plan_rejected_by_gate():
    raw = """{
      "immediate_actions": ["tight tourniquet then cut the wound"],
      "safety_warnings": [],
      "when_to_seek_help": [],
      "questions_to_ask_user": [],
      "emergency_contacts": ["Police: 1080"],
      "explanation": "folk remedy"
    }"""
    try:
        parse_action_plan_json(raw, DEFAULT_TRUSTED_CONTACTS)
        raised = False
    except Exception:
        raised = True
    assert raised
    protocol = get_fallback_action_plan("snakebite")
    assert "tourniquet" not in " ".join(protocol.safety_warnings).lower() or "NOT" in " ".join(protocol.safety_warnings)


def test_evidence_tools_allowlist():
    assert EVIDENCE_TOOL_NAMES == ("fetch_weather", "fetch_hospitals", "search_reports")
    assert "trigger_sos" not in EVIDENCE_TOOL_NAMES
    assert "set_severity" not in EVIDENCE_TOOL_NAMES
