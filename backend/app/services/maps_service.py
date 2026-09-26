"""
Wayfinder agent — nearby hospitals from Supabase (preferred) or Firebase fallback.

Hospital locations are stored in the `hospitals` table (seed via import scripts).
Distance is computed locally with haversine — no Google Maps API required.
"""

import logging
import math

from app.models.schemas import HospitalOut, ServiceResult
from app.services import database_service, supabase_service

logger = logging.getLogger("resq.maps")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _directory_provider() -> str:
    return "supabase_directory" if supabase_service.supabase_available else "firebase_directory"


async def get_nearby_hospitals_safe(
    lat: float, lon: float, radius_m: int = 5000
) -> ServiceResult[list[HospitalOut]]:
    if not database_service.hospitals_directory_available():
        logger.info("Hospital directory not configured.")
        return ServiceResult(
            available=False,
            data=[],
            error_type="service_disabled",
            detail="Hospital directory requires Supabase (or Firebase fallback).",
        )

    try:
        rows = database_service.list_hospitals()
        if not rows:
            return ServiceResult(
                available=False,
                data=[],
                error_type="not_found",
                detail="No hospitals in database. Run hospital import scripts.",
            )

        default_source = "supabase" if supabase_service.supabase_available else "firebase"
        hospitals: list[HospitalOut] = []
        for row in rows:
            h_lat = row.get("lat")
            h_lon = row.get("lon")
            if h_lat is None or h_lon is None:
                continue
            distance_km = _haversine_km(lat, lon, float(h_lat), float(h_lon))
            if distance_km * 1000 > radius_m:
                continue
            hospitals.append(
                HospitalOut(
                    name=row.get("name", "Hospital"),
                    address=row.get("address"),
                    lat=float(h_lat),
                    lon=float(h_lon),
                    distance_km=round(distance_km, 2),
                    facility_type=row.get("facility_type"),
                    phone=row.get("phone"),
                    source=row.get("source", default_source),
                )
            )

        hospitals.sort(key=lambda h: h.distance_km or 999.0)
        return ServiceResult(available=True, data=hospitals[:10])

    except Exception as exc:
        logger.error("Hospital lookup failed: %s", type(exc).__name__)
        return ServiceResult(
            available=False,
            data=[],
            error_type="server_error",
            detail="Failed to read hospitals from database.",
        )


async def get_nearby_hospitals(lat: float, lon: float, radius_m: int = 5000) -> list[HospitalOut]:
    result = await get_nearby_hospitals_safe(lat, lon, radius_m)
    return result.data or []


async def get_route_safe(
    origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float
) -> ServiceResult[dict]:
    """Routing uses external map apps; no Directions API is called."""
    maps_link = (
        f"https://maps.google.com/?saddr={origin_lat},{origin_lon}"
        f"&daddr={dest_lat},{dest_lon}"
    )
    distance_km = _haversine_km(origin_lat, origin_lon, dest_lat, dest_lon)
    return ServiceResult(
        available=True,
        data={
            "maps_link": maps_link,
            "distance_km": round(distance_km, 2),
            "provider": _directory_provider(),
        },
    )


async def get_route(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float) -> dict:
    result = await get_route_safe(origin_lat, origin_lon, dest_lat, dest_lon)
    return result.data or {}
