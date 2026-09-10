from flask import Blueprint, jsonify, request

from app.core.config import settings
from app.models.schemas import WeatherSummary
from app.services import weather_service

bp = Blueprint("weather", __name__, url_prefix="/api/weather")


def _coords_from_query() -> tuple[float, float]:
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    return lat or settings.default_lat, lon or settings.default_lon


@bp.get("")
async def get_weather():
    lat, lon = _coords_from_query()
    result = await weather_service.get_weather_safe(lat, lon)
    if result.available and result.data:
        return jsonify(result.data.model_dump())
    return (
        jsonify({"detail": result.detail or "Weather service is currently unavailable"}),
        503,
    )


@bp.get("/risk")
async def get_risk():
    lat, lon = _coords_from_query()
    result = await weather_service.get_weather_safe(lat, lon)
    if result.available and result.data:
        return jsonify(weather_service.compute_risk_score(result.data).model_dump())

    fallback_weather = WeatherSummary(
        temp_c=25.0,
        condition="Unavailable (baseline fallback)",
        rain_mm_last_hour=0.0,
        alert_active=False,
        alert_headline=None,
    )
    return jsonify(weather_service.compute_risk_score(fallback_weather).model_dump())
