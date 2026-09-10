"""
Parse HOT OSM India health-facilities GeoJSON (HDX) into normalized hospital rows.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import httpx

from app.services.kml_hospital_parser import HYDERABAD_BBOX, _in_hyderabad_bbox

HOTOSM_POINTS_ZIP_URL = (
    "https://s3.dualstack.us-east-1.amazonaws.com/production-raw-data-api/"
    "ISO3/IND/health_facilities/points/hotosm_ind_health_facilities_points_geojson.zip"
)

EXCLUDED_AMENITY = frozenset({"pharmacy", "dentist", "childcare"})
EXCLUDED_HEALTHCARE = frozenset(
    {
        "pharmacy",
        "dentist",
        "blood_bank",
        "laboratory",
        "physiotherapist",
        "optometrist",
        "hospice",
        "alternative",
        "psychotherapist",
    }
)


def _facility_type(props: dict[str, Any]) -> str:
    amenity = (props.get("amenity") or "").strip()
    healthcare = (props.get("healthcare") or "").strip()
    speciality = (props.get("healthcare:speciality") or "").strip()

    if amenity and amenity.lower() not in {"none"}:
        label = amenity.replace("_", " ").title()
    elif healthcare and healthcare.lower() not in {"none", "yes"}:
        label = healthcare.replace("_", " ").title()
    elif healthcare.lower() == "yes":
        label = "Health Facility"
    else:
        label = "Health Facility"

    if speciality:
        label = f"{label} ({speciality})"
    return label


def _is_emergency_relevant(props: dict[str, Any]) -> bool:
    amenity = (props.get("amenity") or "").lower()
    healthcare = (props.get("healthcare") or "").lower()

    if amenity in EXCLUDED_AMENITY or healthcare in EXCLUDED_HEALTHCARE:
        return False
    if amenity in {"hospital", "clinic", "doctors", "health_post", "dispensary"}:
        return True
    if healthcare in {"hospital", "clinic", "centre", "doctor", "yes"}:
        return True
    return bool(amenity or healthcare)


def _resolve_name(props: dict[str, Any]) -> str | None:
    for key in ("name", "name:en", "name:hi", "name:ta"):
        value = (props.get(key) or "").strip()
        if value:
            return value
    osm_id = props.get("osm_id")
    if osm_id:
        return f"Health Facility (OSM {osm_id})"
    return None


def _address(props: dict[str, Any]) -> str | None:
    full = (props.get("addr:full") or "").strip()
    if full:
        return full
    city = (props.get("addr:city") or "").strip()
    if city:
        return f"{city}, Telangana"
    return "Hyderabad, Telangana"


def parse_hotosm_geojson(
    geojson: dict[str, Any],
    *,
    hyderabad_only: bool = True,
    include_unnamed: bool = False,
) -> list[dict[str, Any]]:
    """Normalize HOT OSM point features into hospital directory rows."""
    rows: list[dict[str, Any]] = []

    for feature in geojson.get("features", []):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "Point":
            continue

        coords = geometry.get("coordinates") or []
        if len(coords) < 2:
            continue

        lon, lat = float(coords[0]), float(coords[1])
        if hyderabad_only and not _in_hyderabad_bbox(lat, lon):
            continue

        props = feature.get("properties") or {}
        if not _is_emergency_relevant(props):
            continue

        name = _resolve_name(props)
        if not name:
            if not include_unnamed:
                continue
            name = "Unnamed Health Facility"

        rows.append(
            {
                "name": name,
                "address": _address(props),
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "facility_type": _facility_type(props),
                "district": "Hyderabad",
                "phone": None,
                "osm_id": props.get("osm_id"),
                "osm_type": props.get("osm_type"),
                "source": "hotosm_hdx",
            }
        )

    rows.sort(key=lambda r: (r.get("facility_type", ""), r.get("name", "")))
    return rows


def load_geojson_from_zip_bytes(data: bytes) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        geojson_name = next(
            (name for name in archive.namelist() if name.endswith(".geojson")),
            None,
        )
        if not geojson_name:
            raise ValueError("No .geojson file found in HOT OSM zip archive.")
        with archive.open(geojson_name) as handle:
            return json.load(handle)


def download_hotosm_points_zip(
    *,
    cache_path: Path | None = None,
    timeout: float = 120.0,
) -> bytes:
    if cache_path and cache_path.exists():
        return cache_path.read_bytes()

    response = httpx.get(HOTOSM_POINTS_ZIP_URL, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    data = response.content

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(data)

    return data


def facility_type_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        ft = row.get("facility_type") or "Unknown"
        counts[ft] = counts.get(ft, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


def parse_hotosm_hyderabad(
    *,
    cache_path: Path | None = None,
    include_unnamed: bool = False,
) -> list[dict[str, Any]]:
    """Download (or read cached) HOT OSM zip and return Hyderabad bbox facilities."""
    data = download_hotosm_points_zip(cache_path=cache_path)
    geojson = load_geojson_from_zip_bytes(data)
    return parse_hotosm_geojson(
        geojson,
        hyderabad_only=True,
        include_unnamed=include_unnamed,
    )
