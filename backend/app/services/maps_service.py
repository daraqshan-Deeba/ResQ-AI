"""
Wayfinder agent — nearby hospitals via Google Places, routing via Google
Directions. Note: neither API exposes live bed availability; that number has
to come from your own database (see shelters router) or a hospital partner
feed. Here we surface name/address/distance only, honestly.
"""

import httpx

from app.core.config import settings
from app.models.schemas import HospitalOut

PLACES_URL = "https://places.googleapis.com/v1/places:searchNearby"
DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"


async def get_nearby_hospitals(lat: float, lon: float, radius_m: int = 5000) -> list[HospitalOut]:
    body = {
        "includedTypes": ["hospital"],
        "maxResultCount": 10,
        "locationRestriction": {
            "circle": {"center": {"latitude": lat, "longitude": lon}, "radius": radius_m}
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.google_maps_api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(PLACES_URL, json=body, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    hospitals = []
    for place in data.get("places", []):
        loc = place.get("location", {})
        hospitals.append(
            HospitalOut(
                name=place.get("displayName", {}).get("text", "Unknown hospital"),
                address=place.get("formattedAddress"),
                lat=loc.get("latitude", lat),
                lon=loc.get("longitude", lon),
            )
        )
    return hospitals


async def get_route(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float) -> dict:
    """Basic driving route. Flood-aware rerouting (avoiding roads flagged in
    community reports) needs custom logic layered on top of this — Directions
    API alone has no concept of 'flooded road'."""
    params = {
        "origin": f"{origin_lat},{origin_lon}",
        "destination": f"{dest_lat},{dest_lon}",
        "key": settings.google_maps_api_key,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(DIRECTIONS_URL, params=params)
        resp.raise_for_status()
        return resp.json()
