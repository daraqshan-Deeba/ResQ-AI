from flask import Blueprint, jsonify, request

from app.services import traffic_service

bp = Blueprint("traffic", __name__, url_prefix="/api/traffic")


@bp.get("/nearby")
async def traffic_nearby():
    lat = request.args.get("lat", type=float)
    lon = request.args.get("lon", type=float)
    radius_km = request.args.get("radius_km", type=float, default=5.0)

    if lat is None or lon is None:
        return jsonify({"detail": "Query parameters lat and lon are required."}), 400
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({"detail": "Invalid coordinates."}), 400
    if radius_km <= 0 or radius_km > 25:
        return jsonify({"detail": "radius_km must be between 0 and 25."}), 400

    result = await traffic_service.get_traffic_nearby_safe(lat, lon, radius_km=radius_km)
    if result.available and result.data:
        return jsonify(result.data.model_dump())

    payload = result.data.model_dump() if result.data else {
        "congestion_level": "unknown",
        "incident_count": 0,
        "incidents": [],
        "radius_km": radius_km,
        "lat": lat,
        "lon": lon,
        "sources_used": [],
    }
    payload["detail"] = result.detail or "Traffic data partially unavailable."
    payload["error_type"] = result.error_type
    return jsonify(payload), 200
