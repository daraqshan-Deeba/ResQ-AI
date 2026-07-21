from fastapi import APIRouter, Query

from app.core.config import settings
from app.models.schemas import RiskScore, WeatherSummary
from app.services import weather_service

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("", response_model=WeatherSummary)
async def get_weather(
    lat: float = Query(default=None),
    lon: float = Query(default=None),
):
    return await weather_service.get_weather(
        lat or settings.default_lat, lon or settings.default_lon
    )


@router.get("/risk", response_model=RiskScore)
async def get_risk(
    lat: float = Query(default=None),
    lon: float = Query(default=None),
):
    weather = await weather_service.get_weather(
        lat or settings.default_lat, lon or settings.default_lon
    )
    return weather_service.compute_risk_score(weather)
