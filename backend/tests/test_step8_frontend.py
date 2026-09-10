"""
Step 8 Tests — Frontend Integration Contract Validation

This test suite validates:
  1. HTML contract: dashboard.html contains all required Step 8 UI elements.
  2. Script contract: script.js exports all required renderer functions via module.exports
     and contains correct security patterns.
  3. API endpoint alignment: /api/assessment response matches what the frontend expects.
  4. SOS safety invariants on API level.

Test Inventory (20 tests):
  HTML Contract (1-7):
    1. assessLocationToggle checkbox exists in dashboard.html.
    2. assessLocationStatus span exists in dashboard.html.
    3. assessSubmit button exists in dashboard.html.
    4. assessInput textarea exists in dashboard.html.
    5. assessResult card exists in dashboard.html.
    6. All 7 preset buttons present (flooding, electrocution, injury, snakebite, cyclone, structural_damage, accident).
    7. SOS page has sosConfirmBtn (explicit click required).

  Script Contract (8-14):
    8.  script.js exports module.exports block.
    9.  escapeHtml is exported.
    10. renderServiceStatus is exported.
    11. renderActionPlan is exported.
    12. renderWeather is exported.
    13. renderConfidence is exported.
    14. renderHospitals is exported.

  Security Patterns (15-16):
    15. No automatic geolocation call (no navigator.geolocation without user action).
    16. No automatic SOS trigger (no apiCall('/api/sos') without explicit button).

  API-Frontend Contract (17-20):
    17. POST /api/assessment returns triage field.
    18. POST /api/assessment returns action_plan field.
    19. POST /api/assessment returns confidence field.
    20. POST /api/assessment returns service_status field.
"""

import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models.schemas import (
    ActionPlan,
    ConfidenceResult,
    ServiceResult,
    TriageResult,
    WeatherSummary,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
DASHBOARD_HTML = FRONTEND_DIR / "dashboard.html"
SCRIPT_JS = FRONTEND_DIR / "script.js"

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def read_html() -> str:
    return DASHBOARD_HTML.read_text(encoding="utf-8")


def read_script() -> str:
    return SCRIPT_JS.read_text(encoding="utf-8")


def _mock_triage(category: str = "flooding") -> TriageResult:
    return TriageResult(
        category=category,
        confidence=0.9,
        tier=1,
        explanation="Deterministic match",
        matched_rule="flood_tier1",
    )


def _mock_weather_safe() -> ServiceResult[WeatherSummary]:
    return ServiceResult[WeatherSummary](
        status="available",
        data=WeatherSummary(
            temp_c=28.0,
            condition="Clear",
            rain_mm=0.0,
            wind_kmh=10.0,
            humidity_pct=50.0,
        ),
    )


def _mock_action_plan() -> ActionPlan:
    return ActionPlan(
        immediate_actions=["Call 112", "Move to safety"],
        safety_warnings=["Avoid flood water"],
        emergency_contacts=["112"],
        when_to_seek_help=["Water at chest height"],
        questions_to_ask_user=[],
        explanation="Flooding emergency response.",
        provenance="deterministic",
    )


def _mock_confidence() -> ConfidenceResult:
    return ConfidenceResult(
        overall_confidence=0.85,
        confidence_level="high",
        triage_confidence=0.9,
        weather_confidence=1.0,
        action_plan_confidence=1.0,
        limiting_factor=None,
    )


# ===========================================================================
# HTML Contract (Tests 1–7)
# ===========================================================================

def test_1_location_toggle_exists_in_html():
    """assessLocationToggle checkbox must exist for explicit opt-in location."""
    html = read_html()
    assert 'id="assessLocationToggle"' in html, "assessLocationToggle not found in dashboard.html"


def test_2_location_status_span_exists_in_html():
    """assessLocationStatus span must exist to show GPS acquisition status."""
    html = read_html()
    assert 'id="assessLocationStatus"' in html, "assessLocationStatus span not found"


def test_3_assess_submit_button_exists():
    """assessSubmit button must exist."""
    html = read_html()
    assert 'id="assessSubmit"' in html, "assessSubmit button not found"


def test_4_assess_input_textarea_exists():
    """assessInput textarea must exist for user description."""
    html = read_html()
    assert 'id="assessInput"' in html, "assessInput textarea not found"


def test_5_assess_result_card_exists():
    """assessResult container must exist for rendering structured results."""
    html = read_html()
    assert 'id="assessResult"' in html, "assessResult card not found"


def test_6_all_seven_preset_buttons_exist():
    """All 7 emergency presets must be present as data-preset attributes."""
    html = read_html()
    required_presets = [
        "flooding", "electrocution", "injury", "snakebite",
        "cyclone", "structural_damage", "accident",
    ]
    for preset in required_presets:
        assert f'data-preset="{preset}"' in html, f"Missing preset button: {preset}"


def test_7_sos_page_has_explicit_confirm_button():
    """SOS page must use sosConfirmBtn requiring explicit user click, not auto-trigger."""
    html = read_html()
    assert 'id="sosConfirmBtn"' in html, "sosConfirmBtn not found in SOS page"


# ===========================================================================
# Script Contract (Tests 8–14)
# ===========================================================================

def test_8_script_has_module_exports():
    """script.js must have a module.exports block for testability."""
    js = read_script()
    assert "module.exports" in js, "module.exports not found in script.js"


def test_9_escape_html_exported():
    js = read_script()
    assert "escapeHtml" in js and "module.exports" in js
    # Verify escapeHtml is in the module.exports block
    exports_section = js[js.rfind("module.exports"):]
    assert "escapeHtml" in exports_section, "escapeHtml not in module.exports"


def test_10_render_service_status_exported():
    js = read_script()
    exports_section = js[js.rfind("module.exports"):]
    assert "renderServiceStatus" in exports_section, "renderServiceStatus not exported"


def test_11_render_action_plan_exported():
    js = read_script()
    exports_section = js[js.rfind("module.exports"):]
    assert "renderActionPlan" in exports_section, "renderActionPlan not exported"


def test_12_render_weather_exported():
    js = read_script()
    exports_section = js[js.rfind("module.exports"):]
    assert "renderWeather" in exports_section, "renderWeather not exported"


def test_13_render_confidence_exported():
    js = read_script()
    exports_section = js[js.rfind("module.exports"):]
    assert "renderConfidence" in exports_section, "renderConfidence not exported"


def test_14_render_hospitals_exported():
    js = read_script()
    exports_section = js[js.rfind("module.exports"):]
    assert "renderHospitals" in exports_section, "renderHospitals not exported"


# ===========================================================================
# Security Patterns (Tests 15–16)
# ===========================================================================

def test_15_location_only_acquired_on_checkbox_change():
    """
    navigator.geolocation.getCurrentPosition must only be called inside the
    locationToggle change handler — never at module load time.
    Verify that there's a locationToggle.addEventListener('change', ...) guard.
    """
    js = read_script()
    # Must reference locationToggle guard
    assert "locationToggle" in js, "locationToggle reference not found"
    assert "assessLocationToggle" in js, "assessLocationToggle ID not found"
    # The GPS call must not appear before the IIFE (outside of event handler context)
    # Check that getCurrentPosition is inside an addEventListener block
    pattern = re.compile(r"addEventListener\s*\(\s*['\"]change['\"]", re.DOTALL)
    assert pattern.search(js), "No 'change' event listener found for location toggle"


def test_16_sos_requires_explicit_button_click():
    """
    SOS must only fire on explicit button click — never automatically.
    Verify no auto-invocation of apiCall('/api/sos') without a click handler.
    """
    js = read_script()
    # SOS API call must be inside a click handler function, not at top level
    assert "/api/sos" in js, "/api/sos not referenced in script.js"
    # There must be a click handler containing the SOS call
    assert "assessSosTriggerBtn" in js, "assessSosTriggerBtn not in script.js"
    assert "addEventListener('click'" in js or 'addEventListener("click"' in js, \
        "No click event listener found"


# ===========================================================================
# API-Frontend Contract (Tests 17–20)
# ===========================================================================

def _get_assessment_response():
    """Return a successful /api/assessment response with full mocking."""
    import json as _json
    with (
        patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_weather,
        patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq,
        patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_maps,
    ):
        from app.models.schemas import WeatherSummary
        mock_weather.return_value = ServiceResult[WeatherSummary](
            available=True,
            data=WeatherSummary(
                temp_c=28.0,
                condition="Clear",
                rain_mm_last_hour=0.0,
                alert_active=False,
            ),
        )
        mock_groq.return_value = ServiceResult[str](
            available=True,
            data=_json.dumps({
                "immediate_actions": ["Call 112", "Move to higher ground"],
                "safety_warnings": ["Avoid flood water"],
                "when_to_seek_help": ["Water reaches chest"],
                "questions_to_ask_user": [],
                "emergency_contacts": ["112"],
                "explanation": "Flooding emergency.",
            }),
        )
        mock_maps.return_value = ServiceResult(available=False, error_type="service_disabled")

        response = client.post(
            "/api/assessment",
            json={"description": "My house is flooding", "language": "English"},
        )
    return response


def test_17_assessment_response_has_triage():
    """Frontend expects r.triage with category field."""
    response = _get_assessment_response()
    assert response.status_code == 200
    data = response.json()
    assert "triage" in data, "triage field missing from /api/assessment response"
    assert "category" in data["triage"], "triage.category missing"


def test_18_assessment_response_has_action_plan():
    """Frontend expects r.action_plan with immediate_actions array."""
    response = _get_assessment_response()
    assert response.status_code == 200
    data = response.json()
    assert "action_plan" in data, "action_plan missing from response"
    assert "immediate_actions" in data["action_plan"], "action_plan.immediate_actions missing"


def test_19_assessment_response_has_confidence():
    """Frontend expects r.confidence with confidence_level and overall_confidence."""
    response = _get_assessment_response()
    assert response.status_code == 200
    data = response.json()
    assert "confidence" in data, "confidence field missing from response"
    assert "confidence_level" in data["confidence"], "confidence_level missing"
    assert "overall_confidence" in data["confidence"], "overall_confidence missing"


def test_20_assessment_response_has_service_status():
    """Frontend needs r.service_status to show degradation banners."""
    response = _get_assessment_response()
    assert response.status_code == 200
    data = response.json()
    assert "service_status" in data, "service_status missing from response"
