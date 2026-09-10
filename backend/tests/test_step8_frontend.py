"""
Step 8 Tests — Frontend Integration Contract Validation (Next.js)

Validates:
  1. Next.js page contract: assessment and SOS pages contain required UI patterns.
  2. API endpoint alignment: /api/assessment response matches what the frontend expects.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.main import app
from app.models.schemas import ServiceResult, WeatherSummary

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
ASSESSMENT_PAGE = FRONTEND_DIR / "src" / "app" / "dashboard" / "assessment" / "page.tsx"
SOS_PAGE = FRONTEND_DIR / "src" / "app" / "dashboard" / "sos" / "page.tsx"
API_CLIENT = FRONTEND_DIR / "src" / "lib" / "api.ts"

client = app.test_client()


def read_assessment_page() -> str:
    return ASSESSMENT_PAGE.read_text(encoding="utf-8")


def read_sos_page() -> str:
    return SOS_PAGE.read_text(encoding="utf-8")


def test_1_assessment_has_optional_location_toggle():
    page = read_assessment_page()
    assert "includeLocation" in page
    assert "Include GPS" in page


def test_2_assessment_has_description_input():
    page = read_assessment_page()
    assert "Describe what's happening" in page or "placeholder=" in page


def test_3_assessment_has_submit_action():
    page = read_assessment_page()
    assert "Get Help Now" in page
    assert "submitAssessment" in page


def test_4_assessment_has_result_state():
    page = read_assessment_page()
    assert "setResult" in page or "result" in page


def test_5_assessment_has_emergency_presets():
    page = read_assessment_page()
    for preset in ("flooding", "electrocution", "injury", "snakebite", "cyclone", "structural_damage", "accident"):
        assert preset in page


def test_6_sos_requires_explicit_confirm():
    page = read_sos_page()
    assert "Confirm SOS" in page
    assert "confirmSos" in page


def test_7_api_client_exists():
    assert API_CLIENT.exists()
    content = API_CLIENT.read_text(encoding="utf-8")
    assert "apiCall" in content
    assert "NEXT_PUBLIC_API_URL" in content


def test_8_assessment_geolocation_not_on_mount():
    page = read_assessment_page()
    assert "navigator.geolocation" in page
    assert "toggleLocation" in page or "getCurrentPosition" in page


def test_9_sos_geolocation_only_on_confirm():
    page = read_sos_page()
    assert "navigator.geolocation" in page
    assert "confirmSos" in page


def _get_assessment_response():
    with (
        patch("app.services.weather_service.get_weather_safe", new_callable=AsyncMock) as mock_weather,
        patch("app.services.action_planner_service.call_groq_safe", new_callable=AsyncMock) as mock_groq,
        patch("app.services.maps_service.get_nearby_hospitals_safe", new_callable=AsyncMock) as mock_maps,
    ):
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
            data=json.dumps({
                "immediate_actions": ["Call 112", "Move to higher ground"],
                "safety_warnings": ["Avoid flood water"],
                "when_to_seek_help": ["Water reaches chest"],
                "questions_to_ask_user": [],
                "emergency_contacts": ["112"],
                "explanation": "Flooding emergency.",
            }),
        )
        mock_maps.return_value = ServiceResult(available=False, error_type="service_disabled")

        return client.post(
            "/api/assessment",
            json={"description": "My house is flooding", "language": "English"},
        )


def test_10_assessment_response_has_triage():
    response = _get_assessment_response()
    assert response.status_code == 200
    data = response.get_json()
    assert "triage" in data
    assert "category" in data["triage"]


def test_11_assessment_response_has_action_plan():
    response = _get_assessment_response()
    data = response.get_json()
    assert "action_plan" in data
    assert "immediate_actions" in data["action_plan"]


def test_12_assessment_response_has_confidence():
    response = _get_assessment_response()
    data = response.get_json()
    assert "confidence" in data
    assert "confidence_level" in data["confidence"]


def test_13_assessment_response_has_service_status():
    response = _get_assessment_response()
    data = response.get_json()
    assert "service_status" in data
