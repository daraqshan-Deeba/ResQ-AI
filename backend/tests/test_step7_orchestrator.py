"""
Step 7 Tests — Unified Emergency Orchestrator Layer

Test Inventory:
  Happy Path (1–4):
    1. Full success: Triage + Weather + Groq action plan + Confidence.
    2. Fallback success: Triage + Weather + Deterministic fallback plan + Confidence.
    3. Assessment without coordinates (hospitals skipped, weather uses default).
    4. Assessment with coordinates (hospitals looked up).

  Partial Failures (5–12):
    5. Weather failure (timeout / 500) -> assessment degrades gracefully.
    6. Weather service disabled -> assessment degrades gracefully.
    7. Groq disabled -> uses deterministic fallback ActionPlan.
    8. Groq timeout -> uses deterministic fallback ActionPlan.
    9. Groq malformed response -> uses deterministic fallback ActionPlan.
    10. Maps failure -> empty hospital list, assessment succeeds.
    11. Firebase unavailable without SOS -> normal assessment succeeds.
    12. Multiple simultaneous failures (weather + maps + groq) -> assessment succeeds.

  Authority Boundaries (13–19):
    13. LLM cannot overwrite authoritative triage category.
    14. LLM cannot overwrite deterministic weather risk.
    15. LLM severity is ignored.
    16. LLM confidence is ignored.
    17. Action plan cannot automatically trigger SOS.
    18. High confidence cannot automatically trigger SOS.
    19. Critical weather cannot automatically trigger SOS.

  Hospital Behavior (20–22):
    20. Coordinates supplied -> hospital search attempted.
    21. No coordinates -> hospital search not attempted.
    22. Maps failure -> assessment still succeeds.

  SOS Integration (23–28):
    23. Explicit SOS -> Step 3 persistence-first flow executed.
    24. SOS without coordinates -> validation failure (ValueError).
    25. Firestore unavailable -> degraded SOS result (event_id=None).
    26. FCM failure after persistence -> status=recorded, notification_failed.
    27. FCM disabled -> status=recorded, notification_disabled.
    28. Successful persistence + FCM -> status=recorded, notification_accepted.

  Confidence Propagation (29–32):
    29. Weakest-link confidence correctly calculated and propagated.
    30. Weather unavailable reduces overall confidence to low.
    31. Deterministic action plan gets 1.0 provenance confidence.
    32. Groq action plan gets 0.35 provenance confidence.

  Risk vs Confidence Separation (33–34):
    33. Critical weather risk + low confidence remains critical risk + low confidence.
    34. Safe weather risk + high confidence remains safe risk + high confidence.

  Determinism (35):
    35. Same deterministic inputs produce identical results.

  Request Validation Edge Cases (36–39):
    36. Empty description rejected.
    37. Single coordinate supplied (lat without lon) rejected.
    38. Out-of-bounds latitude rejected.
    39. Out-of-bounds longitude rejected.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models.schemas import (
    ActionPlan,
    AssessmentResult,
    ConfidenceResult,
    HospitalOut,
    RiskScore,
    ServiceResult,
    SosResponse,
    TriageResult,
    WeatherSummary,
)
from app.services import emergency_orchestrator
from app.services.emergency_orchestrator import (
    determine_emergency_level,
    orchestrate_emergency_assessment,
    validate_assessment_request,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_weather_success(rain_mm=10.0, temp_c=28.0):
    return ServiceResult[WeatherSummary](
        available=True,
        data=WeatherSummary(
            temp_c=temp_c,
            condition="Heavy rain",
            rain_mm_last_hour=rain_mm,
            alert_active=False,
        ),
    )


def _mock_groq_json_success(actions=None, explanation="Guidance plan"):
    return ServiceResult[str](
        available=True,
        data=json.dumps({
            "immediate_actions": actions or ["Move to high ground", "Switch off power"],
            "safety_warnings": ["Avoid submerged wires"],
            "when_to_seek_help": ["If water enters living rooms"],
            "questions_to_ask_user": ["Are you on an upper floor?"],
            "emergency_contacts": ["112", "108"],
            "explanation": explanation,
        }),
    )


def _mock_hospitals_success():
    return ServiceResult[list[HospitalOut]](
        available=True,
        data=[
            HospitalOut(
                name="Osmania General Hospital",
                lat=17.3800,
                lon=78.4700,
                address="Afzal Gunj, Hyderabad",
            )
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. HAPPY PATH TESTS (1–4)
# ─────────────────────────────────────────────────────────────────────────────

def test_1_full_success_pipeline():
    """All subsystems available: triage + weather + groq plan + confidence + hospitals."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_m:

        mock_w.return_value = _mock_weather_success(rain_mm=20.0)
        mock_g.return_value = _mock_groq_json_success()
        mock_m.return_value = _mock_hospitals_success()

        res = _run(orchestrate_emergency_assessment(
            description="Water is entering my house and rising quickly",
            lat=17.3850,
            lon=78.4867,
        ))

    assert isinstance(res, AssessmentResult)
    assert res.triage.category == "flooding"
    assert res.weather["status"] == "available"
    assert res.service_status["weather"] == "available"
    assert res.service_status["groq"] == "available"
    assert res.service_status["maps"] == "available"
    assert len(res.hospitals) == 1
    assert res.sos is None
    assert res.confidence.overall_confidence > 0.0


def test_2_fallback_plan_success_pipeline():
    """Groq unavailable -> deterministic fallback plan used, assessment succeeds."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_m:

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = ServiceResult(available=False, error_type="service_disabled")
        mock_m.return_value = _mock_hospitals_success()

        res = _run(orchestrate_emergency_assessment(
            description="Someone has been bitten by a venomous snake",
            lat=17.3850,
            lon=78.4867,
        ))

    assert res.triage.category == "snakebite"
    assert res.service_status["groq"] == "disabled" or res.service_status["groq"] == "fallback_used"
    assert "antivenom" in " ".join(res.action_plan.immediate_actions).lower()
    # Deterministic plan gives action_plan_confidence = 1.0
    assert res.confidence.action_plan_confidence == 1.0


def test_3_assessment_without_coordinates():
    """No coordinates supplied: hospital lookup is not attempted, assessment succeeds."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_m:

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = _mock_groq_json_success()

        res = _run(orchestrate_emergency_assessment(
            description="The wall collapsed in my house",
        ))

        # Hospital lookup should NOT have been called
        mock_m.assert_not_called()

    assert res.triage.category == "structural_damage"
    assert res.hospitals == []
    assert res.service_status["maps"] == "not_requested"


def test_4_assessment_with_coordinates():
    """Coordinates supplied: hospital lookup is attempted."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_m:

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = _mock_groq_json_success()
        mock_m.return_value = _mock_hospitals_success()

        res = _run(orchestrate_emergency_assessment(
            description="Car accident collision on main road",
            lat=17.3850,
            lon=78.4867,
        ))

        mock_m.assert_called_once_with(17.3850, 78.4867)

    assert res.triage.category == "accident"
    assert len(res.hospitals) == 1
    assert res.service_status["maps"] == "available"


# ─────────────────────────────────────────────────────────────────────────────
# 2. PARTIAL FAILURE TESTS (5–12)
# ─────────────────────────────────────────────────────────────────────────────

def test_5_weather_failure():
    """Weather API returns 500/timeout -> weather degrades, assessment succeeds."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        mock_w.return_value = ServiceResult(available=False, error_type="server_error")
        mock_g.return_value = _mock_groq_json_success()

        res = _run(orchestrate_emergency_assessment(
            description="Water is rising",
            lat=17.3850,
            lon=78.4867,
        ))

    assert res.weather["status"] == "server_error"
    assert res.service_status["weather"] == "server_error"
    assert res.confidence.weather_confidence == 0.20
    assert res.confidence.confidence_level == "low"
    assert res.confidence.limiting_factor == "weather"


def test_6_weather_disabled():
    """Weather disabled -> assessment continues with fallback weather baseline."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        mock_w.return_value = ServiceResult(available=False, error_type="service_disabled")
        mock_g.return_value = _mock_groq_json_success()

        res = _run(orchestrate_emergency_assessment(description="Heavy winds and cyclone"))

    assert res.service_status["weather"] == "service_disabled"
    assert res.weather["score"] == 18


def test_7_groq_disabled():
    """Groq disabled -> deterministic fallback ActionPlan used, assessment succeeds."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = ServiceResult(available=False, error_type="service_disabled")

        res = _run(orchestrate_emergency_assessment(description="Exposed live wire touching puddle"))

    assert res.triage.category == "electrocution"
    assert any("not touch" in a.lower() for a in res.action_plan.immediate_actions)
    assert res.confidence.action_plan_confidence == 1.0


def test_8_groq_timeout():
    """Groq timeout -> deterministic fallback ActionPlan used."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = ServiceResult(available=False, error_type="timeout")

        res = _run(orchestrate_emergency_assessment(description="Flooding in house"))

    assert res.triage.category == "flooding"
    assert res.service_status["groq"] in ("fallback_used", "disabled")


def test_9_groq_malformed_response():
    """Groq returns malformed non-JSON -> fallback used without crashing."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = ServiceResult(available=True, data="NOT A VALID JSON")

        res = _run(orchestrate_emergency_assessment(description="Bitten by snake"))

    assert res.triage.category == "snakebite"
    assert res.action_plan.immediate_actions is not None


def test_10_maps_failure():
    """Maps returns timeout / 500 -> hospital list is empty, assessment succeeds."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_m:

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = _mock_groq_json_success()
        mock_m.return_value = ServiceResult(available=False, data=[], error_type="timeout")

        res = _run(orchestrate_emergency_assessment(
            description="Deep cut bleeding badly",
            lat=17.3850,
            lon=78.4867,
        ))

    assert res.hospitals == []
    assert res.service_status["maps"] == "timeout"
    assert res.triage.category == "injury"


def test_11_firebase_unavailable_without_sos():
    """When Firebase is down and SOS was not requested, assessment completes normally."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.firebase_service.firebase_available", False):

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = _mock_groq_json_success()

        res = _run(orchestrate_emergency_assessment(description="My house is flooding and water is rising fast"))

    assert res.service_status["firebase"] == "unavailable"
    assert res.sos is None
    assert res.triage.category == "flooding"


def test_12_multiple_simultaneous_failures():
    """Weather down + Maps down + Groq down: orchestrator still produces safe assessment."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_m:

        mock_w.return_value = ServiceResult(available=False, error_type="network_error")
        mock_g.return_value = ServiceResult(available=False, error_type="server_error")
        mock_m.return_value = ServiceResult(available=False, data=[], error_type="timeout")

        res = _run(orchestrate_emergency_assessment(
            description="Building wall has collapsed",
            lat=17.3850,
            lon=78.4867,
        ))

    assert res.triage.category == "structural_damage"
    assert res.hospitals == []
    assert res.service_status["weather"] == "network_error"
    assert res.service_status["maps"] == "timeout"
    assert res.confidence.overall_confidence == 0.20  # bounded by weather failure
    assert len(res.action_plan.immediate_actions) > 0


# ─────────────────────────────────────────────────────────────────────────────
# 3. AUTHORITY BOUNDARIES (13–19)
# ─────────────────────────────────────────────────────────────────────────────

def test_13_llm_cannot_overwrite_triage_category():
    """Authoritative triage category cannot be altered by LLM."""
    malicious_json = json.dumps({
        "immediate_actions": ["Run"],
        "safety_warnings": [],
        "when_to_seek_help": [],
        "questions_to_ask_user": [],
        "emergency_contacts": ["112"],
        "explanation": "Test",
        "triage_category": "accident",
        "category": "accident",
    })

    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = ServiceResult(available=True, data=malicious_json)

        res = _run(orchestrate_emergency_assessment(description="Live wire on street"))

    # Triage must remain electrocution despite LLM's 'accident' injection
    assert res.triage.category == "electrocution"


def test_14_llm_cannot_overwrite_weather_risk():
    """Deterministic weather risk score/level cannot be overridden by LLM."""
    malicious_json = json.dumps({
        "immediate_actions": ["Rest"],
        "safety_warnings": [],
        "when_to_seek_help": [],
        "questions_to_ask_user": [],
        "emergency_contacts": ["112"],
        "explanation": "Test",
        "weather_risk": {"score": 0, "level": "safe"},
    })

    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        # 50 mm rain creates a high risk score
        mock_w.return_value = _mock_weather_success(rain_mm=50.0)
        mock_g.return_value = ServiceResult(available=True, data=malicious_json)

        res = _run(orchestrate_emergency_assessment(description="Flooding"))

    assert res.weather["score"] > 50
    assert res.weather["level"] in ("warning", "critical")


def test_15_llm_severity_is_ignored():
    """LLM attempts to specify severity or emergency level are ignored."""
    malicious_json = json.dumps({
        "immediate_actions": ["Move"],
        "safety_warnings": [],
        "when_to_seek_help": [],
        "questions_to_ask_user": [],
        "emergency_contacts": ["112"],
        "explanation": "Test",
        "severity": "CRITICAL_URGENT",
        "emergency_level": "CATACLYSMIC",
    })

    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        mock_w.return_value = _mock_weather_success(rain_mm=0.0)
        mock_g.return_value = ServiceResult(available=True, data=malicious_json)

        res = _run(orchestrate_emergency_assessment(description="Someone has a deep cut and is bleeding badly"))

    # Severity is derived deterministically (injury + safe weather -> Moderate), not CATACLYSMIC
    assert res.emergency_level == "Moderate"


def test_16_llm_confidence_is_ignored():
    """LLM cannot claim high confidence to override the aggregator."""
    malicious_json = json.dumps({
        "immediate_actions": ["Move"],
        "safety_warnings": [],
        "when_to_seek_help": [],
        "questions_to_ask_user": [],
        "emergency_contacts": ["112"],
        "explanation": "Test",
        "confidence": 1.0,
        "overall_confidence": 1.0,
    })

    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        # Weather is down (0.20)
        mock_w.return_value = ServiceResult(available=False, error_type="timeout")
        mock_g.return_value = ServiceResult(available=True, data=malicious_json)

        res = _run(orchestrate_emergency_assessment(description="Flooding in home"))

    # Weakest link ensures confidence is 0.20 (low) despite LLM claiming 1.0
    assert res.confidence.overall_confidence == 0.20
    assert res.confidence.confidence_level == "low"


def test_17_action_plan_cannot_trigger_sos():
    """Action plan recommending SOS does NOT trigger SOS without request_sos=True."""
    sos_recommend_json = json.dumps({
        "immediate_actions": ["TRIGGER SOS NOW", "CALL 112"],
        "safety_warnings": [],
        "when_to_seek_help": [],
        "questions_to_ask_user": [],
        "emergency_contacts": ["112"],
        "explanation": "Emergency require SOS",
    })

    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.firebase_service.create_sos_record") as mock_sos:

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = ServiceResult(available=True, data=sos_recommend_json)

        res = _run(orchestrate_emergency_assessment(
            description="Flooding fast",
            request_sos=False,  # Explicitly False
        ))

        mock_sos.assert_not_called()

    assert res.sos is None


def test_18_high_confidence_cannot_automatically_trigger_sos():
    """100% confidence cannot trigger SOS without explicit user request."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.firebase_service.create_sos_record") as mock_sos:

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = _mock_groq_json_success()

        res = _run(orchestrate_emergency_assessment(
            description="Exposed live wire on the road",
            lat=17.3850,
            lon=78.4867,
            request_sos=False,
        ))
        mock_sos.assert_not_called()

    assert res.sos is None


def test_19_critical_weather_cannot_automatically_trigger_sos():
    """Critical weather risk (100 mm rain) cannot automatically trigger SOS."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.firebase_service.create_sos_record") as mock_sos:

        mock_w.return_value = _mock_weather_success(rain_mm=100.0)
        mock_g.return_value = _mock_groq_json_success()

        res = _run(orchestrate_emergency_assessment(
            description="Flooding",
            request_sos=False,
        ))
        mock_sos.assert_not_called()

    assert res.weather["level"] == "critical"
    assert res.sos is None


# ─────────────────────────────────────────────────────────────────────────────
# 4. HOSPITAL BEHAVIOR (20–22)
# ─────────────────────────────────────────────────────────────────────────────

def test_20_coordinates_supplied_hospital_search_attempted():
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_m:

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = _mock_groq_json_success()
        mock_m.return_value = _mock_hospitals_success()

        res = _run(orchestrate_emergency_assessment(
            description="Injury from slip",
            lat=17.4000,
            lon=78.4900,
        ))
        mock_m.assert_called_once_with(17.4000, 78.4900)

    assert len(res.hospitals) == 1
    assert res.service_status["maps"] == "available"


def test_21_no_coordinates_hospital_search_not_attempted():
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_m:

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = _mock_groq_json_success()

        res = _run(orchestrate_emergency_assessment(
            description="Injury from slip",
            lat=None,
            lon=None,
        ))
        mock_m.assert_not_called()

    assert res.hospitals == []
    assert res.service_status["maps"] == "not_requested"


def test_22_maps_failure_assessment_still_succeeds():
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_m:

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = _mock_groq_json_success()
        mock_m.return_value = ServiceResult(available=False, data=[], error_type="auth_error")

        res = _run(orchestrate_emergency_assessment(
            description="Someone has a deep cut and is bleeding badly",
            lat=17.3850,
            lon=78.4867,
        ))

    assert res.hospitals == []
    assert res.service_status["maps"] == "auth_error"
    assert res.triage.category == "injury"


# ─────────────────────────────────────────────────────────────────────────────
# 5. SOS INTEGRATION TESTS (23–28)
# ─────────────────────────────────────────────────────────────────────────────

def test_23_explicit_sos_executes_step3_flow():
    """request_sos=True triggers persistence-first SOS."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.firebase_service.create_sos_record", return_value="evt-12345"), \
         patch("app.services.firebase_service.send_topic_push", return_value="msg-9999"), \
         patch("app.services.firebase_service.update_sos_record") as mock_update, \
         patch("app.services.firebase_service.firebase_available", True):

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = _mock_groq_json_success()

        res = _run(orchestrate_emergency_assessment(
            description="I am trapped in flood water",
            lat=17.3850,
            lon=78.4867,
            request_sos=True,
        ))

    assert res.sos is not None
    assert res.sos.event_id == "evt-12345"
    assert res.sos.status == "recorded"
    assert res.sos.notification_status == "notification_accepted"


def test_24_sos_without_coordinates_fails_validation():
    """Requesting SOS without GPS coordinates raises ValueError."""
    with pytest.raises(ValueError, match="Coordinates.*are required when requesting SOS"):
        _run(orchestrate_emergency_assessment(
            description="Help please",
            request_sos=True,
            lat=None,
            lon=None,
        ))


def test_25_firestore_unavailable_returns_degraded_sos():
    """Firestore down -> degraded SOS response, but assessment completes."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.firebase_service.create_sos_record", side_effect=RuntimeError("Firestore down")):

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = _mock_groq_json_success()

        res = _run(orchestrate_emergency_assessment(
            description="Flooding",
            lat=17.3850,
            lon=78.4867,
            request_sos=True,
        ))

    assert res.sos is not None
    assert res.sos.event_id is None
    assert res.sos.status == "degraded"
    assert res.sos.notification_status == "notification_disabled"


def test_26_fcm_failure_after_persistence():
    """Persistence ok + FCM fails -> status=recorded, notification_failed."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.firebase_service.create_sos_record", return_value="evt-fcm-fail"), \
         patch("app.services.firebase_service.send_topic_push", side_effect=Exception("FCM quota exceeded")), \
         patch("app.services.firebase_service.update_sos_record"), \
         patch("app.services.firebase_service.firebase_available", True):

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = _mock_groq_json_success()

        res = _run(orchestrate_emergency_assessment(
            description="Flooding",
            lat=17.3850,
            lon=78.4867,
            request_sos=True,
        ))

    assert res.sos.event_id == "evt-fcm-fail"
    assert res.sos.status == "recorded"
    assert res.sos.notification_status == "notification_failed"


def test_27_fcm_disabled():
    """FCM disabled -> status=recorded, notification_disabled."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.firebase_service.create_sos_record", return_value="evt-fcm-off"), \
         patch("app.services.firebase_service.update_sos_record"), \
         patch("app.services.firebase_service.firebase_available", False):

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = _mock_groq_json_success()

        res = _run(orchestrate_emergency_assessment(
            description="Flooding",
            lat=17.3850,
            lon=78.4867,
            request_sos=True,
        ))

    assert res.sos.event_id == "evt-fcm-off"
    assert res.sos.status == "recorded"
    assert res.sos.notification_status == "notification_disabled"


def test_28_successful_persistence_and_fcm():
    """Happy path SOS: status=recorded, notification_accepted."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.firebase_service.create_sos_record", return_value="evt-perfect"), \
         patch("app.services.firebase_service.send_topic_push", return_value="msg-ok"), \
         patch("app.services.firebase_service.update_sos_record"), \
         patch("app.services.firebase_service.firebase_available", True):

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = _mock_groq_json_success()

        res = _run(orchestrate_emergency_assessment(
            description="Flooding",
            lat=17.3850,
            lon=78.4867,
            request_sos=True,
        ))

    assert res.sos.event_id == "evt-perfect"
    assert res.sos.status == "recorded"
    assert res.sos.notification_status == "notification_accepted"


# ─────────────────────────────────────────────────────────────────────────────
# 6. CONFIDENCE PROPAGATION TESTS (29–32)
# ─────────────────────────────────────────────────────────────────────────────

def test_29_weakest_link_confidence_propagated():
    """Weakest link across triage, weather, and action plan is correctly propagated."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        mock_w.return_value = _mock_weather_success()  # weather_conf = 1.0
        mock_g.return_value = _mock_groq_json_success()  # action_plan_conf = 0.35

        res = _run(orchestrate_emergency_assessment(description="Flooding in house"))  # triage_conf = 0.93

    # min(0.93, 1.0, 0.35) = 0.35
    assert res.confidence.overall_confidence == 0.35
    assert res.confidence.confidence_level == "low"
    assert res.confidence.limiting_factor == "action_plan"


def test_30_weather_unavailable_reduces_confidence():
    """Weather unavailable (0.20) pulls overall confidence down to 0.20."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        mock_w.return_value = ServiceResult(available=False, error_type="timeout")
        mock_g.return_value = _mock_groq_json_success()

        res = _run(orchestrate_emergency_assessment(description="Flooding"))

    assert res.confidence.overall_confidence == 0.20
    assert res.confidence.limiting_factor == "weather"


def test_31_deterministic_action_plan_gets_provenance_confidence():
    """Fallback action plan gives action_plan_confidence = 1.0."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = ServiceResult(available=False, error_type="service_disabled")

        res = _run(orchestrate_emergency_assessment(description="Flooding in house"))

    assert res.confidence.action_plan_confidence == 1.0
    # min(0.93, 1.0, 1.0) = 0.93
    assert res.confidence.overall_confidence == 0.93
    assert res.confidence.confidence_level == "high"


def test_32_groq_action_plan_gets_provenance_confidence():
    """Groq-generated plan gives action_plan_confidence = 0.35."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = _mock_groq_json_success()

        res = _run(orchestrate_emergency_assessment(description="Flooding"))

    assert res.confidence.action_plan_confidence == 0.35


# ─────────────────────────────────────────────────────────────────────────────
# 7. RISK VS CONFIDENCE SEPARATION (33–34)
# ─────────────────────────────────────────────────────────────────────────────

def test_33_critical_weather_with_low_confidence():
    """Critical weather risk + low confidence remains critical risk + low confidence."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        # 80 mm rain -> critical risk
        mock_w.return_value = _mock_weather_success(rain_mm=80.0)
        # Groq plan -> action confidence 0.35 -> overall confidence 0.35 (low)
        mock_g.return_value = _mock_groq_json_success()

        res = _run(orchestrate_emergency_assessment(description="General situation"))

    assert res.weather["level"] == "critical"
    assert res.confidence.confidence_level == "low"
    assert res.emergency_level == "Critical"


def test_34_safe_weather_with_high_confidence():
    """Safe weather risk + high confidence remains safe risk + high confidence."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        mock_w.return_value = _mock_weather_success(rain_mm=0.0)  # Safe
        mock_g.return_value = ServiceResult(available=False, error_type="service_disabled")  # Deterministic plan = 1.0

        res = _run(orchestrate_emergency_assessment(description="Flooding in house"))

    assert res.weather["level"] == "safe"
    assert res.confidence.confidence_level == "high"


# ─────────────────────────────────────────────────────────────────────────────
# 8. DETERMINISM TEST (35)
# ─────────────────────────────────────────────────────────────────────────────

def test_35_same_deterministic_inputs_produce_equivalent_results():
    """Identical deterministic inputs produce equivalent AssessmentResults."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        mock_w.return_value = _mock_weather_success(rain_mm=5.0)
        mock_g.return_value = ServiceResult(available=False, error_type="service_disabled")

        res1 = _run(orchestrate_emergency_assessment(description="Roof collapsed"))
        res2 = _run(orchestrate_emergency_assessment(description="Roof collapsed"))

    assert res1.triage.category == res2.triage.category
    assert res1.weather["score"] == res2.weather["score"]
    assert res1.confidence.overall_confidence == res2.confidence.overall_confidence
    assert res1.action_plan.immediate_actions == res2.action_plan.immediate_actions
    assert res1.emergency_level == res2.emergency_level


# ─────────────────────────────────────────────────────────────────────────────
# 9. REQUEST VALIDATION EDGE CASES (36–39)
# ─────────────────────────────────────────────────────────────────────────────

def test_36_empty_description_rejected():
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_assessment_request("")

    with pytest.raises(ValueError, match="cannot be empty"):
        validate_assessment_request("   \n\t  ")


def test_37_partial_coordinates_rejected():
    with pytest.raises(ValueError, match="Both latitude and longitude must be provided together"):
        validate_assessment_request("Valid description", lat=17.3850, lon=None)

    with pytest.raises(ValueError, match="Both latitude and longitude must be provided together"):
        validate_assessment_request("Valid description", lat=None, lon=78.4867)


def test_38_out_of_bounds_latitude_rejected():
    with pytest.raises(ValueError, match="Latitude must be between -90.0 and 90.0"):
        validate_assessment_request("Valid description", lat=95.0, lon=78.0)

    with pytest.raises(ValueError, match="Latitude must be between -90.0 and 90.0"):
        validate_assessment_request("Valid description", lat=-91.0, lon=78.0)


def test_39_out_of_bounds_longitude_rejected():
    with pytest.raises(ValueError, match="Longitude must be between -180.0 and 180.0"):
        validate_assessment_request("Valid description", lat=17.0, lon=185.0)

    with pytest.raises(ValueError, match="Longitude must be between -180.0 and 180.0"):
        validate_assessment_request("Valid description", lat=17.0, lon=-181.0)


# ─────────────────────────────────────────────────────────────────────────────
# 10. ROUTER INTEGRATION TEST (/api/assessment)
# ─────────────────────────────────────────────────────────────────────────────

def test_40_router_assessment_returns_structured_orchestrated_result():
    """POST /api/assessment returns the unified AssessmentResult via FastAPI client."""
    client = TestClient(app)

    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_m:

        mock_w.return_value = _mock_weather_success()
        mock_g.return_value = _mock_groq_json_success()
        mock_m.return_value = _mock_hospitals_success()

        res = client.post("/api/assessment", json={
            "description": "My home is flooded and water is rising fast",
            "lat": 17.3850,
            "lon": 78.4867,
        })

    assert res.status_code == 200
    data = res.json()

    # Verify structured orchestrator fields
    assert "triage" in data
    assert data["triage"]["category"] == "flooding"
    assert "weather" in data
    assert "action_plan" in data
    assert "confidence" in data
    assert "hospitals" in data
    assert "service_status" in data

    # Verify backward-compatible UI fields
    assert "emergency_level" in data
    assert "immediate_first_aid" in data
    assert "call_these_services" in data
    assert "whats_happening" in data
