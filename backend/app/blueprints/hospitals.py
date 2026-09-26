from flask import Blueprint, jsonify, request

from app.services import maps_service

bp = Blueprint("hospitals", __name__, url_prefix="/api/hospitals")


@bp.get("")
async def list_hospitals():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    if lat is None or lon is None:
        return jsonify({"detail": "lat and lon are required", "status": "search_failed"}), 400
    result = await maps_service.get_nearby_hospitals_safe(lat, lon)
    if not result.available:
        return jsonify({"detail": result.detail or "Hospital search failed", "status": "search_failed"}), 503
    hospitals = result.data or []
    return jsonify([h.model_dump() for h in hospitals])
