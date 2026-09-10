from flask import Blueprint, jsonify, request

from app.core.config import settings
from app.services import maps_service

bp = Blueprint("hospitals", __name__, url_prefix="/api/hospitals")


@bp.get("")
async def list_hospitals():
    lat = request.args.get("lat", type=float) or settings.default_lat
    lon = request.args.get("lon", type=float) or settings.default_lon
    result = await maps_service.get_nearby_hospitals_safe(lat, lon)
    hospitals = result.data or []
    return jsonify([h.model_dump() for h in hospitals])
