from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models.schemas import AssessmentResponse, HospitalOut, WeatherSummary
from app.services import groq_service, maps_service, weather_service


def make_mock_response(status_code: int = 200, json_data=None, text: str = ""):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("No JSON")
    resp.text = text
    if not resp.is_success:
        req = httpx.Request("GET", "http://test")
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}", request=req, response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ============================================================================
# WEATHER TESTS
# ============================================================================


@pytest.mark.anyio
async def test_weather_success(monkeypatch):
    monkeypatch.setattr(settings, "openweather_api_key", "test-key")
    sample_data = {
        "main": {"temp": 28.5},
        "weather": [{"description": "moderate rain"}],
        "rain": {"1h": 4.2},
    }
    mock_resp = make_mock_response(status_code=200, json_data=sample_data)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = await weather_service.get_weather_safe(17.385, 78.486)

    assert res.available is True
    assert res.error_type is None
    assert isinstance(res.data, WeatherSummary)
    assert res.data.temp_c == 28.5
    assert res.data.condition == "moderate rain"
    assert res.data.rain_mm_last_hour == 4.2


@pytest.mark.anyio
async def test_weather_service_disabled(monkeypatch):
    monkeypatch.setattr(settings, "openweather_api_key", "")
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        res = await weather_service.get_weather_safe(17.385, 78.486)
        mock_get.assert_not_called()

    assert res.available is False
    assert res.error_type == "service_disabled"
    assert res.data is None


@pytest.mark.anyio
async def test_weather_timeout(monkeypatch):
    monkeypatch.setattr(settings, "openweather_api_key", "test-key")
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Read timed out")
        res = await weather_service.get_weather_safe(17.385, 78.486)

    assert res.available is False
    assert res.error_type == "timeout"
    assert "timed out" in res.detail.lower()


@pytest.mark.anyio
async def test_weather_network_error(monkeypatch):
    monkeypatch.setattr(settings, "openweather_api_key", "test-key")
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectError("DNS failed")
        res = await weather_service.get_weather_safe(17.385, 78.486)

    assert res.available is False
    assert res.error_type == "network_error"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status,expected_error_type",
    [
        (401, "auth_error"),
        (403, "auth_error"),
        (404, "not_found"),
        (429, "rate_limited"),
        (500, "server_error"),
        (502, "server_error"),
        (503, "server_error"),
        (504, "timeout"),
    ],
)
async def test_weather_http_errors(monkeypatch, status, expected_error_type):
    monkeypatch.setattr(settings, "openweather_api_key", "test-key")
    mock_resp = make_mock_response(status_code=status)
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = await weather_service.get_weather_safe(17.385, 78.486)

    assert res.available is False
    assert res.error_type == expected_error_type


@pytest.mark.anyio
async def test_weather_parse_error(monkeypatch):
    monkeypatch.setattr(settings, "openweather_api_key", "test-key")
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.is_success = True
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.side_effect = ValueError("Invalid JSON")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = await weather_service.get_weather_safe(17.385, 78.486)

    assert res.available is False
    assert res.error_type == "parse_error"


def test_deterministic_risk_formula_preserved():
    # rain 0mm: 0*0.6 + 46*0.4 = 18.4 -> 18 -> safe
    w_safe = WeatherSummary(temp_c=25, condition="Clear", rain_mm_last_hour=0.0, alert_active=False)
    r_safe = weather_service.compute_risk_score(w_safe)
    assert r_safe.score == 18
    assert r_safe.level == "safe"

    # rain 5mm: int(5*12)=60 -> 60*0.6 + 46*0.4 = 36 + 18.4 = 54.4 -> 54 -> warning
    w_warn = WeatherSummary(temp_c=25, condition="Rain", rain_mm_last_hour=5.0, alert_active=False)
    r_warn = weather_service.compute_risk_score(w_warn)
    assert r_warn.score == 54
    assert r_warn.level == "warning"

    # rain 9mm: min(100, int(9*12)=108) -> 100 -> 60 + 18.4 = 78 -> critical
    w_crit = WeatherSummary(temp_c=25, condition="Flood", rain_mm_last_hour=9.0, alert_active=False)
    r_crit = weather_service.compute_risk_score(w_crit)
    assert r_crit.score == 78
    assert r_crit.level == "critical"


# ============================================================================
# MAPS TESTS
# ============================================================================


@pytest.mark.anyio
async def test_maps_hospital_success(monkeypatch):
    monkeypatch.setattr(settings, "google_maps_api_key", "test-maps-key")
    sample_places = {
        "places": [
            {
                "displayName": {"text": "Gandhi Hospital"},
                "formattedAddress": "Musheerabad, Hyderabad",
                "location": {"latitude": 17.424, "longitude": 78.502},
            }
        ]
    }
    mock_resp = make_mock_response(status_code=200, json_data=sample_places)
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await maps_service.get_nearby_hospitals_safe(17.385, 78.486)

    assert res.available is True
    assert len(res.data) == 1
    assert res.data[0].name == "Gandhi Hospital"


@pytest.mark.anyio
async def test_maps_hospital_disabled(monkeypatch):
    monkeypatch.setattr(settings, "google_maps_api_key", "")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        res = await maps_service.get_nearby_hospitals_safe(17.385, 78.486)
        mock_post.assert_not_called()

    assert res.available is False
    assert res.error_type == "service_disabled"
    assert res.data == []


@pytest.mark.anyio
async def test_maps_hospital_timeout_and_network(monkeypatch):
    monkeypatch.setattr(settings, "google_maps_api_key", "test-maps-key")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Timeout")
        res_timeout = await maps_service.get_nearby_hospitals_safe(17.385, 78.486)
        assert res_timeout.available is False
        assert res_timeout.error_type == "timeout"
        assert res_timeout.data == []

        mock_post.side_effect = httpx.ConnectError("Network drop")
        res_net = await maps_service.get_nearby_hospitals_safe(17.385, 78.486)
        assert res_net.available is False
        assert res_net.error_type == "network_error"
        assert res_net.data == []


@pytest.mark.anyio
async def test_maps_hospital_auth_error(monkeypatch):
    monkeypatch.setattr(settings, "google_maps_api_key", "test-maps-key")
    mock_resp = make_mock_response(status_code=401)
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await maps_service.get_nearby_hospitals_safe(17.385, 78.486)

    assert res.available is False
    assert res.error_type == "auth_error"
    assert res.data == []


@pytest.mark.anyio
async def test_maps_route_success_and_failure(monkeypatch):
    monkeypatch.setattr(settings, "google_maps_api_key", "test-maps-key")
    # Success
    mock_resp = make_mock_response(status_code=200, json_data={"routes": [{"summary": "Route 1"}]})
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res_ok = await maps_service.get_route_safe(17.1, 78.1, 17.2, 78.2)
        assert res_ok.available is True
        assert "routes" in res_ok.data

    # Failure
    mock_fail = make_mock_response(status_code=500)
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_fail
        res_fail = await maps_service.get_route_safe(17.1, 78.1, 17.2, 78.2)
        assert res_fail.available is False
        assert res_fail.error_type == "server_error"
        assert res_fail.data == {}


# ============================================================================
# GROQ TESTS
# ============================================================================


@pytest.mark.anyio
async def test_groq_success(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "gsk-test")
    sample_completion = {
        "choices": [
            {
                "message": {
                    "content": (
                        "EMERGENCY LEVEL: High\n"
                        "WHAT'S HAPPENING: Water is entering ground floor.\n"
                        "IMMEDIATE FIRST AID:\n1. Switch off main power.\n"
                        "WHAT NOT TO DO:\n1. Do not wade in water.\n"
                        "CALL THESE SERVICES: 112\n"
                        "THINGS TO CARRY:\n1. Water\n"
                        "NEARBY HELP:\n- Shelter (no live lookup available)"
                    )
                }
            }
        ]
    }
    mock_resp = make_mock_response(status_code=200, json_data=sample_completion)
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await groq_service.call_groq_safe([{"role": "user", "content": "Help"}])

    assert res.available is True
    assert "EMERGENCY LEVEL: High" in res.data


@pytest.mark.anyio
async def test_groq_service_disabled(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        res = await groq_service.call_groq_safe([{"role": "user", "content": "Help"}])
        mock_post.assert_not_called()

    assert res.available is False
    assert res.error_type == "service_disabled"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status,expected_error_type",
    [
        (401, "auth_error"),
        (403, "auth_error"),
        (429, "rate_limited"),
        (500, "server_error"),
        (503, "server_error"),
    ],
)
async def test_groq_http_errors(monkeypatch, status, expected_error_type):
    monkeypatch.setattr(settings, "groq_api_key", "gsk-test")
    mock_resp = make_mock_response(status_code=status)
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await groq_service.call_groq_safe([{"role": "user", "content": "Help"}])

    assert res.available is False
    assert res.error_type == expected_error_type


@pytest.mark.anyio
async def test_groq_timeout_and_network(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "gsk-test")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Timeout")
        res_t = await groq_service.call_groq_safe([{"role": "user", "content": "Help"}])
        assert res_t.available is False
        assert res_t.error_type == "timeout"

        mock_post.side_effect = httpx.RequestError("Network failure")
        res_n = await groq_service.call_groq_safe([{"role": "user", "content": "Help"}])
        assert res_n.available is False
        assert res_n.error_type == "network_error"


@pytest.mark.anyio
async def test_groq_malformed_response(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "gsk-test")
    mock_resp = make_mock_response(status_code=200, json_data={"choices": []})
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await groq_service.call_groq_safe([{"role": "user", "content": "Help"}])

    assert res.available is False
    assert res.error_type == "parse_error"


@pytest.mark.anyio
async def test_groq_static_fallback_on_failure(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    # When Groq is disabled, run_assessment must return safe static fallback with 112 and 108
    resp = await groq_service.run_assessment("Flooding near house", "Hyderabad")
    assert isinstance(resp, AssessmentResponse)
    assert any("112" in s for s in resp.call_these_services)
    assert any("108" in s for s in resp.call_these_services)
    assert "Live AI assessment service is currently unavailable" in resp.whats_happening


@pytest.mark.anyio
async def test_groq_chat_fallback_on_failure(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    reply = await groq_service.run_chat_reply([], "What should I do?", "Hyderabad")
    assert "112" in reply
    assert "108" in reply


# ============================================================================
# ROUTER INTEGRATION & DEGRADATION TESTS
# ============================================================================


def test_router_weather_success_and_fallback(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(settings, "openweather_api_key", "test-key")

    # Success
    sample_weather = {
        "main": {"temp": 29.0},
        "weather": [{"description": "sunny"}],
        "rain": {},
    }
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = make_mock_response(200, sample_weather)
        res_w = client.get("/api/weather")
        assert res_w.status_code == 200
        assert res_w.json()["temp_c"] == 29.0

        res_r = client.get("/api/weather/risk")
        assert res_r.status_code == 200
        assert res_r.json()["level"] == "safe"

    # Unavailable weather -> /api/weather returns 503, /api/weather/risk returns fallback baseline
    monkeypatch.setattr(settings, "openweather_api_key", "")
    res_w_fail = client.get("/api/weather")
    assert res_w_fail.status_code == 503

    res_r_fallback = client.get("/api/weather/risk")
    assert res_r_fallback.status_code == 200
    assert res_r_fallback.json()["score"] == 18
    assert res_r_fallback.json()["level"] == "safe"


def test_router_hospitals_degraded_when_maps_unavailable(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(settings, "google_maps_api_key", "")
    res = client.get("/api/hospitals")
    assert res.status_code == 200
    assert res.json() == []


def test_router_assessment_fallback_when_groq_unavailable(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(settings, "groq_api_key", "")
    res = client.post("/api/assessment", json={"description": "My home is flooded"})
    assert res.status_code == 200
    data = res.json()
    assert "112" in " ".join(data["call_these_services"])
    assert "108" in " ".join(data["call_these_services"])
    assert "Live AI assessment service is currently unavailable" in data["whats_happening"]


def test_router_chat_fallback_when_groq_unavailable(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(settings, "groq_api_key", "")
    res = client.post("/api/chat", json={"history": [], "message": "Help"})
    assert res.status_code == 200
    assert "112" in res.json()["reply"]
