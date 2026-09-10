from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.models.schemas import RiskScore, WeatherSummary
from app.services import weather_service

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("", response_model=WeatherSummary)
async def get_weather(
    lat: float = Query(default=None),
    lon: float = Query(default=None),
):
    result = await weather_service.get_weather_safe(
        lat or settings.default_lat, lon or settings.default_lon
    )
    if result.available and result.data:
        return result.data
    raise HTTPException(
        status_code=503,
        detail=result.detail or "Weather service is currently unavailable",
    )


@router.get("/risk", response_model=RiskScore)
async def get_risk(
    lat: float = Query(default=None),
    lon: float = Query(default=None),
):
    result = await weather_service.get_weather_safe(
        lat or settings.default_lat, lon or settings.default_lon
    )
    if result.available and result.data:
        return weather_service.compute_risk_score(result.data)

    fallback_weather = WeatherSummary(
        temp_c=25.0,
        condition="Unavailable (baseline fallback)",
        rain_mm_last_hour=0.0,
        alert_active=False,
        alert_headline=None,
    )
    return weather_service.compute_risk_score(fallback_weather)
