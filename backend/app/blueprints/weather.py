from flask import Blueprint, jsonify, request

from app.services import weather_service

bp = Blueprint("weather", __name__, url_prefix="/api/weather")


def _coords_from_query() -> tuple[float, float] | None:
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None:
        return None
    return lat, lon


@bp.get("")
async def get_weather():
    coords = _coords_from_query()
    if coords is None:
        return jsonify({"detail": "lat and lon are required", "status": "unavailable"}), 400
    lat, lon = coords
    result = await weather_service.get_weather_safe(lat, lon)
    if result.available and result.data:
        return jsonify(result.data.model_dump())
    return (
        jsonify({"detail": result.detail or "Weather service is currently unavailable"}),
        503,
    )


@bp.get("/risk")
async def get_risk():
    coords = _coords_from_query()
    if coords is None:
        return jsonify({"detail": "lat and lon are required", "status": "unavailable"}), 400
    lat, lon = coords
    result = await weather_service.get_weather_safe(lat, lon)
    if result.available and result.data:
        return jsonify(weather_service.compute_risk_score(result.data).model_dump())

    return (
        jsonify({"detail": result.detail or "Weather risk is unavailable", "status": "unavailable"}),
        503,
    )
