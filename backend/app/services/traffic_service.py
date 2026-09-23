"""
Nearby traffic / road disruption lookup.

Combines:
  • OpenStreetMap Overpass — construction zones and road closures near the user
  • Community reports — accident / traffic / construction messages from Supabase
  • Optional TomTom Traffic Incidents API when TOMTOM_API_KEY is configured
"""

import logging
import math
import re
from typing import Literal, Optional

import httpx

from app.core.config import settings
from app.models.schemas import ServiceResult, TrafficIncident, TrafficOverview
from app.services import database_service

logger = logging.getLogger("resq.traffic")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
TOMTOM_INCIDENTS_URL = "https://api.tomtom.com/traffic/services/5/incidentDetails"

ACCIDENT_PATTERN = re.compile(
    r"\b(accident|collision|crash|wreck|pile[- ]?up|hit by|road blocked|overturned)\b",
    re.IGNORECASE,
)
CONSTRUCTION_PATTERN = re.compile(
    r"\b(construction|road work|roadwork|under construction|digging|excavat|"
    r"lane closed|road closed|repair work|maintenance)\b",
    re.IGNORECASE,
)
CONGESTION_PATTERN = re.compile(
    r"\b(congestion|heavy traffic|slow traffic|standstill|bumper to bumper|"
    r"gridlock|traffic jam|stalled traffic)\b",
    re.IGNORECASE,
)

# Approximate centroids for Hyderabad area labels used in community reports.
# Used only when a report has no explicit lat/lon of its own.
_HYDERABAD_AREA_COORDS: dict[str, tuple[float, float]] = {
    "abids": (17.3920, 78.4770),
    "adikmet": (17.4070, 78.5140),
    "banjara hills": (17.4150, 78.4350),
    "charminar": (17.3610, 78.4740),
    "dilsukhnagar": (17.3680, 78.5240),
    "gachibowli": (17.4400, 78.3480),
    "hitec city": (17.4480, 78.3820),
    "kondapur": (17.4620, 78.3660),
    "kukatpally": (17.4940, 78.3990),
    "lb nagar": (17.3500, 78.5520),
    "malakpet": (17.3730, 78.4930),
    "miyapur": (17.4960, 78.3910),
    "musheerabad": (17.4200, 78.5000),
    "nallakunta": (17.4000, 78.5090),
    "secunderabad": (17.4390, 78.4980),
    "shamirpet": (17.5940, 78.5760),
    "tolichowki": (17.3980, 78.4200),
    "uppal": (17.3980, 78.5580),
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _congestion_level(count: int) -> Literal["light", "moderate", "heavy", "unknown"]:
    if count == 0:
        return "light"
    if count <= 2:
        return "moderate"
    return "heavy"


def _classify_report_message(message: str) -> Optional[Literal["accident", "construction", "congestion"]]:
    try:
        from app.core.config import settings
        from app.services.report_ml_service import classify_report

        if settings.triage_ml_enabled:
            ml_label = classify_report(message)
            if ml_label in ("accident", "construction", "congestion"):
                return ml_label
    except Exception:
        pass

    if ACCIDENT_PATTERN.search(message):
        return "accident"
    if CONSTRUCTION_PATTERN.search(message):
        return "construction"
    if CONGESTION_PATTERN.search(message):
        return "congestion"
    return None


def _incident_severity(
    incident_type: str, distance_km: Optional[float]
) -> Literal["low", "moderate", "high"]:
    if incident_type == "accident":
        return "high"
    if incident_type == "construction":
        return "moderate"
    if distance_km is not None and distance_km < 1.0:
        return "high"
    if distance_km is not None and distance_km < 3.0:
        return "moderate"
    return "low"


async def _fetch_overpass_incidents(
    lat: float, lon: float, radius_m: int
) -> list[TrafficIncident]:
    query = f"""
    [out:json][timeout:25];
    (
      node(around:{radius_m},{lat},{lon})["construction"];
      way(around:{radius_m},{lat},{lon})["construction"];
      node(around:{radius_m},{lat},{lon})["highway"="construction"];
      way(around:{radius_m},{lat},{lon})["highway"="construction"];
      node(around:{radius_m},{lat},{lon})["barrier"="debris"];
      way(around:{radius_m},{lat},{lon})["barrier"="debris"];
    );
    out center tags;
    """
    incidents: list[TrafficIncident] = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(OVERPASS_URL, data={"data": query})
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:
        logger.warning("Overpass traffic lookup failed: %s", exc)
        return incidents

    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        elat = element.get("lat")
        elon = element.get("lon")
        center = element.get("center") or {}
        if elat is None:
            elat = center.get("lat")
        if elon is None:
            elon = center.get("lon")
        if elat is None or elon is None:
            continue

        name = (
            tags.get("name")
            or tags.get("description")
            or tags.get("construction")
            or tags.get("highway")
            or "Road work"
        )
        distance = haversine_km(lat, lon, float(elat), float(elon))
        is_closure = tags.get("barrier") == "debris" or tags.get("access") == "no"
        incident_type: Literal["construction", "road_closure"] = (
            "road_closure" if is_closure else "construction"
        )
        incidents.append(
            TrafficIncident(
                id=f"osm-{element.get('type', 'node')}-{element.get('id', len(incidents))}",
                type=incident_type,
                title=f"Under construction: {name}" if incident_type == "construction" else f"Road obstruction: {name}",
                description=tags.get("note") or tags.get("description") or "OpenStreetMap road disruption",
                lat=float(elat),
                lon=float(elon),
                distance_km=round(distance, 2),
                severity=_incident_severity(incident_type, distance),
                source="openstreetmap",
                verified=True,
            )
        )
    return incidents


async def _fetch_tomtom_incidents(
    lat: float, lon: float, radius_km: float
) -> list[TrafficIncident]:
    api_key = settings.tomtom_api_key.strip()
    if not api_key:
        return []

    # Bounding box ~radius around point (rough degrees at Hyderabad latitude)
    delta = radius_km / 111.0
    bbox = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"
    params = {
        "key": api_key,
        "bbox": bbox,
        "fields": "{incidents{geometry,type,properties}}",
        "language": "en-GB",
    }

    incidents: list[TrafficIncident] = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(TOMTOM_INCIDENTS_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as exc:
        logger.warning("TomTom traffic lookup failed: %s", exc)
        return incidents

    for item in payload.get("incidents", []):
        geometry = item.get("geometry") or {}
        coords = geometry.get("coordinates") or []
        if len(coords) < 2:
            continue
        elon, elat = float(coords[0]), float(coords[1])
        props = item.get("properties") or {}
        icon_category = (props.get("iconCategory") or 0)
        incident_type: Literal["accident", "construction", "congestion", "road_closure"] = "congestion"
        if icon_category in (1, 2, 3):
            incident_type = "accident"
        elif icon_category in (6, 7, 8, 9):
            incident_type = "construction"
        elif icon_category in (4, 5):
            incident_type = "road_closure"

        distance = haversine_km(lat, lon, elat, elon)
        if distance > radius_km:
            continue

        incidents.append(
            TrafficIncident(
                id=f"tomtom-{props.get('id', len(incidents))}",
                type=incident_type,
                title=props.get("from") or props.get("description") or "Traffic incident",
                description=props.get("description") or props.get("to") or "TomTom traffic incident",
                lat=elat,
                lon=elon,
                distance_km=round(distance, 2),
                severity=_incident_severity(incident_type, distance),
                source="tomtom",
                verified=True,
            )
        )
    return incidents


def _resolve_report_coords(report: dict) -> Optional[tuple[float, float]]:
    """Prefer explicit lat/lon; otherwise map known Hyderabad area labels."""
    lat = report.get("lat")
    lon = report.get("lon")
    try:
        if lat is not None and lon is not None:
            return float(lat), float(lon)
    except (TypeError, ValueError):
        pass

    area = (report.get("area") or "").strip().lower()
    if not area:
        return None
    if area in _HYDERABAD_AREA_COORDS:
        return _HYDERABAD_AREA_COORDS[area]
    # Allow partial matches like "Uppal Ring Road"
    for key, coords in _HYDERABAD_AREA_COORDS.items():
        if key in area or area in key:
            return coords
    return None


def _fetch_community_incidents(
    lat: float,
    lon: float,
    radius_km: float,
) -> list[TrafficIncident]:
    """Return community traffic reports that fall inside the same radius as OSM/TomTom."""
    incidents: list[TrafficIncident] = []
    try:
        reports = database_service.list_reports()
    except Exception as exc:
        logger.warning("Community traffic reports unavailable: %s", exc)
        return incidents

    for report in reports[:100]:
        message = report.get("message", "")
        category = _classify_report_message(message)
        if not category:
            continue

        coords = _resolve_report_coords(report)
        if coords is None:
            # Cannot place the report — omit from "nearby" list rather than
            # showing citywide incidents as if they were local.
            continue

        report_lat, report_lon = coords
        distance = haversine_km(lat, lon, report_lat, report_lon)
        if distance > radius_km:
            continue

        incidents.append(
            TrafficIncident(
                id=f"report-{report.get('id', len(incidents))}",
                type=category,
                title=f"{category.replace('_', ' ').title()} — {report.get('area', 'Unknown area')}",
                description=message,
                lat=report_lat,
                lon=report_lon,
                distance_km=round(distance, 2),
                severity=_incident_severity(category, distance),
                source="community_report",
                verified=bool(report.get("verified", False)),
            )
        )
    return incidents


async def get_traffic_nearby_safe(
    lat: float,
    lon: float,
    radius_km: float = 5.0,
) -> ServiceResult[TrafficOverview]:
    radius_m = int(radius_km * 1000)
    sources_used: list[str] = []

    osm_incidents = await _fetch_overpass_incidents(lat, lon, radius_m)
    if osm_incidents:
        sources_used.append("openstreetmap")

    tomtom_incidents = await _fetch_tomtom_incidents(lat, lon, radius_km)
    if tomtom_incidents:
        sources_used.append("tomtom")

    community_incidents = _fetch_community_incidents(lat, lon, radius_km)
    if community_incidents:
        sources_used.append("community_reports")

    merged: list[TrafficIncident] = []
    seen: set[str] = set()
    for item in [*tomtom_incidents, *osm_incidents, *community_incidents]:
        # Drop anything outside the requested radius (defense in depth).
        if item.distance_km is not None and item.distance_km > radius_km:
            continue
        # Community/OSM items without distance were already filtered above;
        # never promote unlocated items into the nearby list.
        if item.distance_km is None:
            continue
        key = f"{item.type}:{item.title}:{item.description[:40]}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)

    merged.sort(key=lambda i: i.distance_km or 999)

    level = _congestion_level(len(merged))
    if not sources_used:
        return ServiceResult(
            available=False,
            error_type="not_found",
            detail="No traffic data sources returned results.",
            data=TrafficOverview(
                congestion_level="unknown",
                incident_count=0,
                incidents=[],
                radius_km=radius_km,
                lat=lat,
                lon=lon,
                sources_used=[],
            ),
        )

    return ServiceResult(
        available=True,
        data=TrafficOverview(
            congestion_level=level,
            incident_count=len(merged),
            incidents=merged[:25],
            radius_km=radius_km,
            lat=lat,
            lon=lon,
            sources_used=sources_used,
        ),
    )
