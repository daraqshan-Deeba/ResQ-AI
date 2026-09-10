"""
Wayfinder agent — nearby hospitals via Google Places, routing via Google
Directions. Note: neither API exposes live bed availability; that number has
to come from your own database (see shelters router) or a hospital partner
feed. Here we surface name/address/distance only, honestly.
"""

import logging

import httpx

from app.core.config import settings
from app.models.schemas import HospitalOut, ServiceResult

logger = logging.getLogger("resq.maps")

PLACES_URL = "https://places.googleapis.com/v1/places:searchNearby"
DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"


async def get_nearby_hospitals_safe(
    lat: float, lon: float, radius_m: int = 5000
) -> ServiceResult[list[HospitalOut]]:
    api_key = settings.google_maps_api_key
    if not api_key or not api_key.strip():
        logger.info("Google Maps API key not configured; hospital search disabled.")
        return ServiceResult(
            available=False,
            data=[],
            error_type="service_disabled",
            detail="Google Maps/Places service is disabled or API key is not configured.",
        )

    body = {
        "includedTypes": ["hospital"],
        "maxResultCount": 10,
        "locationRestriction": {
            "circle": {"center": {"latitude": lat, "longitude": lon}, "radius": radius_m}
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key.strip(),
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(PLACES_URL, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        hospitals: list[HospitalOut] = []
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
        return ServiceResult(available=True, data=hospitals)

    except httpx.TimeoutException:
        logger.warning("Timeout while connecting to Google Places.")
        return ServiceResult(
            available=False,
            data=[],
            error_type="timeout",
            detail="Hospital lookup timed out.",
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        logger.warning("Google Places returned HTTP %s.", status)
        if status in (401, 403):
            error_type = "auth_error"
            detail = "Google Places authorization error."
        elif status == 404:
            error_type = "not_found"
            detail = "Google Places resource not found."
        elif status == 429:
            error_type = "rate_limited"
            detail = "Google Places rate limit exceeded. Please try again shortly."
        elif status == 504:
            error_type = "timeout"
            detail = "Google Places gateway timed out."
        elif status in (500, 502, 503):
            error_type = "server_error"
            detail = "Google Places service is temporarily unavailable."
        else:
            error_type = "server_error"
            detail = f"Google Places responded with status {status}."
        return ServiceResult(available=False, data=[], error_type=error_type, detail=detail)
    except httpx.RequestError as exc:
        logger.warning("Network error connecting to Google Places: %s", type(exc).__name__)
        return ServiceResult(
            available=False,
            data=[],
            error_type="network_error",
            detail="Network error while connecting to Google Places.",
        )
    except (ValueError, KeyError, TypeError) as exc:
        logger.error("Failed to parse Google Places response: %s", exc)
        return ServiceResult(
            available=False,
            data=[],
            error_type="parse_error",
            detail="Malformed response received from Google Places.",
        )
    except Exception as exc:
        logger.error("Unexpected error in maps service: %s", type(exc).__name__)
        return ServiceResult(
            available=False,
            data=[],
            error_type="server_error",
            detail="An unexpected error occurred while searching nearby hospitals.",
        )


async def get_nearby_hospitals(lat: float, lon: float, radius_m: int = 5000) -> list[HospitalOut]:
    """Legacy helper preserved for backward compatibility."""
    result = await get_nearby_hospitals_safe(lat, lon, radius_m)
    return result.data or []


async def get_route_safe(
    origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float
) -> ServiceResult[dict]:
    api_key = settings.google_maps_api_key
    if not api_key or not api_key.strip():
        logger.info("Google Maps API key not configured; routing disabled.")
        return ServiceResult(
            available=False,
            data={},
            error_type="service_disabled",
            detail="Google Directions service is disabled or API key is not configured.",
        )

    params = {
        "origin": f"{origin_lat},{origin_lon}",
        "destination": f"{dest_lat},{dest_lon}",
        "key": api_key.strip(),
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(DIRECTIONS_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        return ServiceResult(available=True, data=data)

    except httpx.TimeoutException:
        logger.warning("Timeout while connecting to Google Directions.")
        return ServiceResult(
            available=False,
            data={},
            error_type="timeout",
            detail="Directions route lookup timed out.",
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        logger.warning("Google Directions returned HTTP %s.", status)
        if status in (401, 403):
            error_type = "auth_error"
            detail = "Google Directions authorization error."
        elif status == 404:
            error_type = "not_found"
            detail = "Directions route not found."
        elif status == 429:
            error_type = "rate_limited"
            detail = "Google Directions rate limit exceeded. Please try again shortly."
        elif status == 504:
            error_type = "timeout"
            detail = "Google Directions gateway timed out."
        elif status in (500, 502, 503):
            error_type = "server_error"
            detail = "Google Directions service is temporarily unavailable."
        else:
            error_type = "server_error"
            detail = f"Google Directions responded with status {status}."
        return ServiceResult(available=False, data={}, error_type=error_type, detail=detail)
    except httpx.RequestError as exc:
        logger.warning("Network error connecting to Google Directions: %s", type(exc).__name__)
        return ServiceResult(
            available=False,
            data={},
            error_type="network_error",
            detail="Network error while connecting to Google Directions.",
        )
    except (ValueError, KeyError, TypeError) as exc:
        logger.error("Failed to parse Google Directions response: %s", exc)
        return ServiceResult(
            available=False,
            data={},
            error_type="parse_error",
            detail="Malformed response received from Google Directions.",
        )
    except Exception as exc:
        logger.error("Unexpected error in routing service: %s", type(exc).__name__)
        return ServiceResult(
            available=False,
            data={},
            error_type="server_error",
            detail="An unexpected error occurred while calculating route.",
        )


async def get_route(origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float) -> dict:
    """Legacy helper preserved for backward compatibility."""
    result = await get_route_safe(origin_lat, origin_lon, dest_lat, dest_lon)
    return result.data or {}
