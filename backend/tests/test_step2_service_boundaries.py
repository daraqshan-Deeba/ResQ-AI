from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
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
    from app.services import database_service, supabase_service

    monkeypatch.setattr(supabase_service, "supabase_available", True)
    monkeypatch.setattr(database_service, "hospitals_directory_available", lambda: True)
    monkeypatch.setattr(
        database_service,
        "list_hospitals",
        lambda: [
            {
                "name": "Gandhi Hospital",
                "address": "Musheerabad, Hyderabad",
                "lat": 17.424,
                "lon": 78.502,
                "source": "supabase",
            }
        ],
    )
    res = await maps_service.get_nearby_hospitals_safe(17.385, 78.486)

    assert res.available is True
    assert len(res.data) == 1
    assert res.data[0].name == "Gandhi Hospital"
    assert res.data[0].source == "supabase"


@pytest.mark.anyio
async def test_maps_hospital_disabled(monkeypatch):
    from app.services import database_service

    monkeypatch.setattr(database_service, "hospitals_directory_available", lambda: False)
    res = await maps_service.get_nearby_hospitals_safe(17.385, 78.486)

    assert res.available is False
    assert res.error_type == "service_disabled"
    assert res.data == []


@pytest.mark.anyio
async def test_maps_hospital_empty_directory(monkeypatch):
    from app.services import database_service, supabase_service

    monkeypatch.setattr(supabase_service, "supabase_available", True)
    monkeypatch.setattr(database_service, "hospitals_directory_available", lambda: True)
    monkeypatch.setattr(database_service, "list_hospitals", lambda: [])
    res = await maps_service.get_nearby_hospitals_safe(17.385, 78.486)

    assert res.available is False
    assert res.error_type == "not_found"


@pytest.mark.anyio
async def test_maps_route_returns_link():
    res = await maps_service.get_route_safe(17.1, 78.1, 17.2, 78.2)
    assert res.available is True
    assert "maps_link" in res.data
    assert "distance_km" in res.data


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
async def test_groq_retries_known_model_on_404(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "gsk-test")
    monkeypatch.setattr(settings, "groq_model", "qwen/qwen3.6-27b")
    fail = make_mock_response(status_code=404)
    ok = make_mock_response(
        status_code=200,
        json_data={"choices": [{"message": {"content": "protocol wording"}}]},
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [fail, ok]
        res = await groq_service.call_groq_safe([{"role": "user", "content": "Help"}])

    assert res.available is True
    assert res.data == "protocol wording"
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[1].kwargs["json"]["model"] == "openai/gpt-oss-20b"


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
    client = app.test_client()
    monkeypatch.setattr(settings, "openweather_api_key", "test-key")

    # Success
    sample_weather = {
        "main": {"temp": 29.0},
        "weather": [{"description": "sunny"}],
        "rain": {},
    }
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = make_mock_response(200, sample_weather)
        res_w = client.get("/api/weather?lat=17.385&lon=78.4867")
        assert res_w.status_code == 200
        assert res_w.get_json()["temp_c"] == 29.0

        res_r = client.get("/api/weather/risk?lat=17.385&lon=78.4867")
        assert res_r.status_code == 200
        assert res_r.get_json()["level"] == "safe"

    # Unavailable weather -> /api/weather returns 503, /api/weather/risk returns 503 (no fake safe)
    monkeypatch.setattr(settings, "openweather_api_key", "")
    res_w_fail = client.get("/api/weather?lat=17.385&lon=78.4867")
    assert res_w_fail.status_code == 503

    res_r_fallback = client.get("/api/weather/risk?lat=17.385&lon=78.4867")
    assert res_r_fallback.status_code == 503


def test_router_hospitals_degraded_when_maps_unavailable(monkeypatch):
    from app.services import database_service

    client = app.test_client()
    monkeypatch.setattr(database_service, "hospitals_directory_available", lambda: False)
    res = client.get("/api/hospitals?lat=17.385&lon=78.4867")
    assert res.status_code == 503


def test_router_assessment_fallback_when_groq_unavailable(monkeypatch):
    client = app.test_client()
    monkeypatch.setattr(settings, "groq_api_key", "")
    res = client.post("/api/assessment", json={"description": "My home is flooded"})
    assert res.status_code == 200
    data = res.get_json()
    assert "112" in " ".join(data["call_these_services"])
    assert "108" in " ".join(data["call_these_services"])
    assert data["emergency_level"] in ("High", "Critical", "Unknown")


def test_router_chat_fallback_when_groq_unavailable(monkeypatch):
    client = app.test_client()
    monkeypatch.setattr(settings, "groq_api_key", "")
    res = client.post("/api/chat", json={"history": [], "message": "Help"})
    assert res.status_code == 200
    assert "112" in res.get_json()["reply"]
