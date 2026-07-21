"""
Sentinel agent — reads live weather and turns it into the risk score shown on
the dashboard.

Uses OpenWeatherMap's Current Weather API.
"""

import httpx

from app.core.config import settings
from app.models.schemas import RiskScore, WeatherSummary


CURRENT_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


async def get_weather(lat: float, lon: float) -> WeatherSummary:
    params = {
        "lat": lat,
        "lon": lon,
        "appid": settings.openweather_api_key,
        "units": "metric",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(CURRENT_WEATHER_URL, params=params)

        # This will show the OpenWeather error if the API key is invalid
        # or the API request fails.
        resp.raise_for_status()

        data = resp.json()

    # Current temperature
    main = data.get("main", {})

    # Weather condition
    weather_info = (data.get("weather") or [{}])[0]

    # Rain data
    # OpenWeather Current Weather API may return rain data as:
    # {"1h": value}
    rain_data = data.get("rain", {})
    rain_mm = rain_data.get("1h", 0.0)

    return WeatherSummary(
        temp_c=main.get("temp", 0.0),
        condition=weather_info.get("description", "unknown"),
        rain_mm_last_hour=rain_mm,
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