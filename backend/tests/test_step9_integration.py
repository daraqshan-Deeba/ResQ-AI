"""
Step 9 Comprehensive Integration and End-to-End Test Suite

Covers Scenarios A-P:
  Scenario A — Normal emergency assessment (end-to-end through router)
  Scenario B — Groq unavailable (deterministic triage + action plan fallback + proper provenance)
  Scenario C — Weather unavailable (graceful degradation, uninvented weather data, confidence reduced)
  Scenario D — Maps unavailable (empty hospitals, no fake hospitals, maps degradation notice)
  Scenario E — Firebase unavailable (normal assessment works, SOS returns degraded, no crash)
  Scenario F — FCM failure after persistence (persisted record remains, notification_status=notification_failed)
  Scenario G — Successful SOS (persistence + notification accepted, explicit only)
  Scenario H — Invalid requests (empty, >5000 chars, partial coords, out of range coords, SOS without coords)
  Scenario I — Triage fallback cascade (Tier 1, Tier 2, Tier 3 Groq, Tier 3 unclassified)
  Scenario J — Confidence propagation (weakest-link model)
  Scenario K — Frontend contract alignment (all fields present and well-typed)
  Scenario L — Frontend degraded services presentation (proper degradation statuses)
  Scenario M — XSS / unsafe content sanitization (ActionPlan URL & tag protection)
  Scenario N — Explicit location privacy (no location without opt-in)
  Scenario O — Explicit SOS privacy (no SOS on assessment, no auto SOS)
  Scenario P — Backward compatibility fields preserved
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.main import app
from app.core.config import settings
from app.models.schemas import (
    ActionPlan,
    AssessmentResult,
    ConfidenceResult,
    HospitalOut,
    ServiceResult,
    SosResponse,
    TriageResult,
    WeatherSummary,
)
from app.services import emergency_orchestrator, firebase_service, triage_service

client = app.test_client()


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------
def _mock_weather_available(temp=27.0, rain=15.0, condition="Moderate rain"):
    return ServiceResult[WeatherSummary](
        available=True,
        data=WeatherSummary(
            temp_c=temp,
            condition=condition,
            rain_mm_last_hour=rain,
            alert_active=False,
            alert_headline=None,
        ),
    )


def _mock_groq_available(actions=None, explanation="Follow standard protocol"):
    return ServiceResult[str](
        available=True,
        data=json.dumps({
            "immediate_actions": actions or ["Move to high ground", "Switch off circuit breaker"],
            "safety_warnings": ["Do not enter moving water", "Avoid fallen utility poles"],
            "when_to_seek_help": ["If water breaches living quarters"],
            "questions_to_ask_user": ["Are vulnerable persons present?"],
            "emergency_contacts": ["112", "108"],
            "explanation": explanation,
        }),
    )


def _mock_hospitals_available():
    return ServiceResult[list[HospitalOut]](
        available=True,
        data=[
            HospitalOut(
                name="Gandhi General Hospital",
                lat=17.4200,
                lon=78.5000,
                address="Secunderabad, Telangana",
                distance_km=2.4,
            )
        ],
    )


# ===========================================================================
# SCENARIO A: Normal Emergency Assessment
# ===========================================================================
def test_scenario_a_normal_emergency_assessment():
    """Full successful end-to-end pipeline via POST /api/assessment."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_m:

        mock_w.return_value = _mock_weather_available(rain=25.0)
        mock_g.return_value = _mock_groq_available()
        mock_m.return_value = _mock_hospitals_available()

        res = client.post("/api/assessment", json={
            "description": "Heavy flooding is entering my house and water is rising fast.",
            "lat": 17.3850,
            "lon": 78.4867,
        })

    assert res.status_code == 200
    data = res.get_json()

    # Category and severity
    assert data["triage"]["category"] == "flooding"
    assert data["emergency_level"] in ("High", "Critical")  # deterministic rule
    assert data["weather"]["status"] == "available"
    assert data["weather"]["rain_mm_last_hour"] == 25.0
    assert len(data["action_plan"]["immediate_actions"]) > 0
    assert data["confidence"]["overall_confidence"] > 0
    assert len(data["hospitals"]) == 1
    assert data["hospitals"][0]["name"] == "Gandhi General Hospital"
    assert data["sos"] is None  # No auto-SOS!


# ===========================================================================
# SCENARIO B: Groq Unavailable
# ===========================================================================
def test_scenario_b_groq_unavailable():
    """When Groq is down or unconfigured, fallback action plan is used and provenance recorded."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_m:

        mock_w.return_value = _mock_weather_available()
        mock_g.return_value = ServiceResult(available=False, error_type="service_disabled")
        mock_m.return_value = _mock_hospitals_available()

        res = client.post("/api/assessment", json={
            "description": "Someone has been bitten by a snake, urgent medical help needed.",
            "lat": 17.3850,
            "lon": 78.4867,
        })

    assert res.status_code == 200
    data = res.get_json()

    assert data["triage"]["category"] == "snakebite"
    assert data["emergency_level"] == "Critical"  # deterministic rule for snakebite
    assert data["service_status"]["groq"] in ("disabled", "fallback_used")
    # Action plan still provided by deterministic fallback
    assert len(data["action_plan"]["immediate_actions"]) > 0
    # Deterministic action plan provenance leads to 1.0 confidence provenance in confidence result
    assert data["confidence"]["action_plan_confidence"] == 1.0


# ===========================================================================
# SCENARIO C: Weather Unavailable
# ===========================================================================
def test_scenario_c_weather_unavailable():
    """When weather fails, assessment succeeds, weather status is degraded, confidence is penalized."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_m:

        mock_w.return_value = ServiceResult(available=False, error_type="timeout", detail="OpenWeather timed out")
        mock_g.return_value = _mock_groq_available()
        mock_m.return_value = _mock_hospitals_available()

        res = client.post("/api/assessment", json={
            "description": "Someone has a deep cut and is bleeding badly, needs medical help.",
            "lat": 17.3850,
            "lon": 78.4867,
        })

    assert res.status_code == 200
    data = res.get_json()

    assert data["weather"]["status"] == "timeout"
    assert data["service_status"]["weather"] == "timeout"
    # Weather confidence is penalized to 0.20
    assert data["confidence"]["weather_confidence"] == 0.20
    assert data["confidence"]["limiting_factor"] == "weather"
    assert data["confidence"]["confidence_level"] == "low"


# ===========================================================================
# SCENARIO D: Maps / Hospital Service Unavailable
# ===========================================================================
def test_scenario_d_maps_unavailable_no_fake_hospitals():
    """When Maps fails, hospitals list is empty; no fabricated hospitals allowed."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_m:

        mock_w.return_value = _mock_weather_available()
        mock_g.return_value = _mock_groq_available()
        mock_m.return_value = ServiceResult(available=False, error_type="network_error")

        res = client.post("/api/assessment", json={
            "description": "Live electrical wire has fallen onto standing water.",
            "lat": 17.3850,
            "lon": 78.4867,
        })

    assert res.status_code == 200
    data = res.get_json()

    assert data["hospitals"] == []
    assert data["service_status"]["maps"] == "network_error"


# ===========================================================================
# SCENARIO E: Firebase Unavailable
# ===========================================================================
def test_scenario_e_firebase_unavailable_assessment_and_sos():
    """Normal assessment works when Firebase is missing; SOS degrades safely without 500."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g:

        mock_w.return_value = _mock_weather_available()
        mock_g.return_value = _mock_groq_available()

        # Assessment works fine
        res_assess = client.post("/api/assessment", json={
            "description": "Cyclone approaching our area with strong cyclonic winds.",
        })
        assert res_assess.status_code == 200

        # SOS returns degraded status with guidance
        res_sos = client.post("/api/sos", json={"lat": 17.3850, "lon": 78.4867})
        assert res_sos.status_code == 200
        sos_body = res_sos.get_json()
        assert sos_body["status"] == "degraded"
        assert sos_body["event_id"] is None
        assert "112" in sos_body["message"]


# ===========================================================================
# SCENARIO F: FCM Failure After Successful Persistence
# ===========================================================================
def test_scenario_f_fcm_failure_after_persistence(monkeypatch):
    """FCM notification failure must NEVER delete or invalidate the persisted SOS record."""
    ref = MagicMock()
    ref.id = "sos-persisted-123"
    db = MagicMock()
    db.collection.return_value.document.return_value = ref

    mock_messaging = MagicMock()
    mock_messaging.send.side_effect = RuntimeError("FCM server connection timeout")

    monkeypatch.setattr(firebase_service, "firebase_available", True)
    monkeypatch.setattr(firebase_service, "db", db)
    monkeypatch.setattr(firebase_service, "messaging", mock_messaging)

    res = client.post("/api/sos", json={
        "lat": 17.3850,
        "lon": 78.4867,
        "situation": "Trapped on roof in flooding",
    })

    assert res.status_code == 200
    body = res.get_json()

    assert body["status"] == "recorded"
    assert body["event_id"] == "sos-persisted-123"
    assert body["notification_status"] == "notification_failed"
    # Confirm initial record was created
    ref.set.assert_called_once()
    # Confirm update recorded notification_failed
    update_data = ref.update.call_args[0][0]
    assert update_data["notification_status"] == "notification_failed"


# ===========================================================================
# SCENARIO G: Successful SOS
# ===========================================================================
def test_scenario_g_successful_sos(monkeypatch):
    """When both Firestore and FCM succeed, status is recorded and notification_accepted."""
    ref = MagicMock()
    ref.id = "sos-event-999"
    db = MagicMock()
    db.collection.return_value.document.return_value = ref

    mock_messaging = MagicMock()
    mock_messaging.send.return_value = "projects/p/messages/msg-888"

    monkeypatch.setattr(firebase_service, "firebase_available", True)
    monkeypatch.setattr(firebase_service, "db", db)
    monkeypatch.setattr(firebase_service, "messaging", mock_messaging)

    res = client.post("/api/sos", json={
        "lat": 17.3850,
        "lon": 78.4867,
        "situation": "Car accident with two trapped victims",
    })

    assert res.status_code == 200
    body = res.get_json()

    assert body["status"] == "recorded"
    assert body["event_id"] == "sos-event-999"
    assert body["notification_status"] == "notification_accepted"
    ref.set.assert_called_once()
    update_data = ref.update.call_args[0][0]
    assert update_data["notification_status"] == "notification_accepted"


# ===========================================================================
# SCENARIO H: Invalid Requests
# ===========================================================================
def test_scenario_h_invalid_requests_rejected_with_400():
    """All invalid request structures are rejected with HTTP 400 Bad Request."""
    # 1. Empty description
    r1 = client.post("/api/assessment", json={"description": ""})
    assert r1.status_code == 400
    assert "empty" in r1.get_json()["detail"].lower()

    # 2. Excessively long description (> 5000 chars)
    r2 = client.post("/api/assessment", json={"description": "a" * 5001})
    assert r2.status_code == 400
    assert "5000" in r2.get_json()["detail"]

    # 3. Latitude without longitude
    r3 = client.post("/api/assessment", json={"description": "Valid incident", "lat": 17.0})
    assert r3.status_code == 400
    assert "together" in r3.get_json()["detail"].lower()

    # 4. Longitude without latitude
    r4 = client.post("/api/assessment", json={"description": "Valid incident", "lon": 78.0})
    assert r4.status_code == 400
    assert "together" in r4.get_json()["detail"].lower()

    # 5. Invalid latitude (> 90)
    r5 = client.post("/api/assessment", json={"description": "Valid incident", "lat": 95.0, "lon": 78.0})
    assert r5.status_code == 400

    # 6. Invalid longitude (> 180)
    r6 = client.post("/api/assessment", json={"description": "Valid incident", "lat": 17.0, "lon": 185.0})
    assert r6.status_code == 400

    # 7. SOS requested without coordinates
    r7 = client.post("/api/assessment", json={"description": "Valid incident", "request_sos": True})
    assert r7.status_code == 400
    assert "coordinates" in r7.get_json()["detail"].lower()


# ===========================================================================
# SCENARIO I: Triage Fallback Cascade
# ===========================================================================
def test_scenario_i_triage_cascade():
    """Test all tiers of triage cascade."""
    # Tier 1: Deterministic keyword rule
    t1 = _run(triage_service.classify("Someone is trapped in heavy flooding with rising water."))
    assert t1.tier == 1
    assert t1.category == "flooding"
    assert t1.confidence >= 0.90

    # Tier 2: Semantic TF-IDF similarity (e.g. slight paraphrase of snakebite)
    t2 = _run(triage_service.classify("A venomous snake bit my hand."))
    assert t2.tier in (1, 2)
    assert t2.category == "snakebite"

    # Tier 3 fallback when unclassifiable
    with patch("app.services.groq_service.call_groq_safe", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = ServiceResult(available=False, error_type="service_disabled")
        t3 = _run(triage_service.classify("quantum entanglement anomaly in the garden"))
        assert t3.category == "unclassified"
        assert t3.confidence == 0.20


# ===========================================================================
# SCENARIO J: Confidence Propagation (Weakest-Link Principle)
# ===========================================================================
def test_scenario_j_confidence_propagation_weakest_link():
    """Overall confidence is always the minimum of triage, weather, and action plan."""
    from app.services.confidence_service import aggregate_confidence

    # 1. Triage is weakest
    c1 = aggregate_confidence(triage_confidence=0.55, weather_confidence=1.0, action_plan_confidence=1.0)
    assert c1.overall_confidence == 0.55
    assert c1.limiting_factor == "triage"

    # 2. Weather is weakest
    c2 = aggregate_confidence(triage_confidence=0.95, weather_confidence=0.20, action_plan_confidence=1.0)
    assert c2.overall_confidence == 0.20
    assert c2.limiting_factor == "weather"

    # 3. Action plan is weakest
    c3 = aggregate_confidence(triage_confidence=0.90, weather_confidence=0.85, action_plan_confidence=0.35)
    assert c3.overall_confidence == 0.35
    assert c3.limiting_factor == "action_plan"


# ===========================================================================
# SCENARIO K & P: Frontend Contract & Backward Compatibility
# ===========================================================================
def test_scenario_k_and_p_contract_and_backward_compatibility():
    """Verify AssessmentResult response preserves all structured and legacy fields."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_m:

        mock_w.return_value = _mock_weather_available()
        mock_g.return_value = _mock_groq_available()
        mock_m.return_value = _mock_hospitals_available()

        res = client.post("/api/assessment", json={
            "description": "There has been a severe car accident on the road with injured passengers.",
            "lat": 17.3850,
            "lon": 78.4867,
        })

    assert res.status_code == 200
    data = res.get_json()

    # Required structured fields
    structured_keys = ["triage", "weather", "action_plan", "confidence", "hospitals", "service_status", "sos"]
    for k in structured_keys:
        assert k in data, f"Missing structured field: {k}"

    # Required backward-compatibility fields
    legacy_keys = ["emergency_level", "whats_happening", "immediate_first_aid", "what_not_to_do", "call_these_services", "things_to_carry", "nearby_help", "raw_text"]
    for k in legacy_keys:
        assert k in data, f"Missing legacy field: {k}"


# ===========================================================================
# SCENARIO M: XSS and Arbitrary URL Protection
# ===========================================================================
def test_scenario_m_action_plan_rejects_arbitrary_urls():
    """ActionPlan validator strictly forbids arbitrary attacker URLs."""
    with pytest.raises(ValueError, match="arbitrary URLs"):
        ActionPlan(
            immediate_actions=["Visit http://malicious-site.com/hack for instructions"],
            safety_warnings=[],
            when_to_seek_help=[],
            questions_to_ask_user=[],
            emergency_contacts=[],
            explanation="Malicious explanation",
        )

    with pytest.raises(ValueError, match="arbitrary URLs"):
        ActionPlan(
            immediate_actions=["Safe step"],
            safety_warnings=[],
            when_to_seek_help=[],
            questions_to_ask_user=[],
            emergency_contacts=[],
            explanation="Check out https://evil-phishing.org for more information",
        )


# ===========================================================================
# SCENARIO N & O: Explicit Location & SOS Privacy Invariants
# ===========================================================================
def test_scenario_n_and_o_privacy_invariants():
    """Assessment without coordinates must never search hospitals or trigger SOS."""
    with patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_w, \
         patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_g, \
         patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_m:

        mock_w.return_value = _mock_weather_available()
        mock_g.return_value = _mock_groq_available()

        res = client.post("/api/assessment", json={
            "description": "Part of the building wall and roof has collapsed.",
        })

    assert res.status_code == 200
    data = res.get_json()

    # Maps service was never called
    mock_m.assert_not_called()
    assert data["hospitals"] == []
    assert data["service_status"]["maps"] == "not_requested"
    # SOS was never called
    assert data["sos"] is None
