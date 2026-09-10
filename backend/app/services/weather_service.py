"""
Sentinel agent — reads live weather and turns it into the risk score shown on
the dashboard.

Uses OpenWeatherMap's Current Weather API.
"""

import logging

import httpx

from app.core.config import settings
from app.models.schemas import RiskScore, ServiceResult, WeatherSummary

logger = logging.getLogger("resq.weather")

CURRENT_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


async def get_weather_safe(lat: float, lon: float) -> ServiceResult[WeatherSummary]:
    api_key = settings.openweather_api_key
    if not api_key or not api_key.strip():
        logger.info("OpenWeatherMap API key not configured; weather service disabled.")
        return ServiceResult(
            available=False,
            error_type="service_disabled",
            detail="Weather service is not configured or disabled.",
        )

    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key.strip(),
        "units": "metric",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(CURRENT_WEATHER_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        main = data.get("main", {})
        weather_info = (data.get("weather") or [{}])[0]
        rain_data = data.get("rain", {})
        rain_mm = float(rain_data.get("1h", 0.0))

        summary = WeatherSummary(
            temp_c=float(main.get("temp", 0.0)),
            condition=str(weather_info.get("description", "unknown")),
            rain_mm_last_hour=rain_mm,
            alert_active=False,
            alert_headline=None,
        )
        return ServiceResult(available=True, data=summary)

    except httpx.TimeoutException:
        logger.warning("Timeout while connecting to OpenWeatherMap.")
        return ServiceResult(
            available=False,
            error_type="timeout",
            detail="Weather service request timed out.",
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        logger.warning("OpenWeatherMap returned HTTP %s.", status)
        if status in (401, 403):
            error_type = "auth_error"
            detail = "Weather service authorization error."
        elif status == 404:
            error_type = "not_found"
            detail = "Weather location data not found."
        elif status == 429:
            error_type = "rate_limited"
            detail = "Weather service rate limit reached. Please try again shortly."
        elif status == 504:
            error_type = "timeout"
            detail = "Weather service gateway timed out."
        elif status in (500, 502, 503):
            error_type = "server_error"
            detail = "Weather service is temporarily unavailable."
        else:
            error_type = "server_error"
            detail = f"Weather service responded with status {status}."
        return ServiceResult(available=False, error_type=error_type, detail=detail)
    except httpx.RequestError as exc:
        logger.warning("Network error connecting to OpenWeatherMap: %s", type(exc).__name__)
        return ServiceResult(
            available=False,
            error_type="network_error",
            detail="Network error while connecting to weather service.",
        )
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        logger.error("Failed to parse OpenWeatherMap response: %s", exc)
        return ServiceResult(
            available=False,
            error_type="parse_error",
            detail="Malformed response received from weather service.",
        )
    except Exception as exc:
        logger.error("Unexpected error in weather service: %s", type(exc).__name__)
        return ServiceResult(
            available=False,
            error_type="server_error",
            detail="An unexpected error occurred in weather service.",
        )


async def get_weather(lat: float, lon: float) -> WeatherSummary:
    """Legacy helper preserved for backward compatibility."""
    result = await get_weather_safe(lat, lon)
    if result.available and result.data:
        return result.data
    return WeatherSummary(
        temp_c=25.0,
        condition="Unavailable (baseline fallback)",
        rain_mm_last_hour=0.0,
        alert_active=False,
        alert_headline=None,
    )


def compute_risk_score(weather: WeatherSummary) -> RiskScore:
    """
    Heuristic placeholder — combines rainfall intensity with a fixed drainage
    factor since there's no public real-time drainage/river-level API for
    Indian cities.

    This is a simple estimate and not a scientific model.
    """

    rainfall_intensity_pct = min(
        100,
        int(weather.rain_mm_last_hour * 12)
    )

    drainage_capacity_pct = 54

    score = int(
        rainfall_intensity_pct * 0.6
        + (100 - drainage_capacity_pct) * 0.4
    )

    score = max(0, min(100, score))

    if score >= 75 or weather.alert_active:
        level = "critical"
    elif score >= 50:
        level = "warning"
    elif score >= 25:
        level = "watch"
    else:
        level = "safe"

    return RiskScore(
        score=score,
        level=level,
        rainfall_intensity_pct=rainfall_intensity_pct,
        drainage_capacity_pct=drainage_capacity_pct,
    )