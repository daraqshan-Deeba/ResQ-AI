"""
Parse Telangana / Hyderabad health-facility KML (PHC, Area Hospital, etc.)
into a normalized hospital directory dataset.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}

# Greater Hyderabad — drop obvious coordinate errors in source file
HYDERABAD_BBOX = (17.2, 78.3, 17.65, 78.62)  # south, west, north, east


def _simple_data(placemark: ET.Element) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in placemark.findall(".//kml:SimpleData", KML_NS):
        key = node.attrib.get("name")
        if key and node.text:
            out[key] = node.text.strip()
    return out


def _point_coords(placemark: ET.Element) -> tuple[float, float] | None:
    coord_el = placemark.find(".//kml:coordinates", KML_NS)
    if coord_el is None or not coord_el.text:
        return None
    parts = coord_el.text.strip().split(",")
    if len(parts) < 2:
        return None
    try:
        lon = float(parts[0])
        lat = float(parts[1])
    except ValueError:
        return None
    return lat, lon


def _in_hyderabad_bbox(lat: float, lon: float) -> bool:
    south, west, north, east = HYDERABAD_BBOX
    return south <= lat <= north and west <= lon <= east


def _detect_kml_schema(path: Path | str) -> str:
    root = ET.parse(str(path)).getroot()
    if root.find(".//kml:Schema[@name='Hyd_hospitals']", KML_NS) is not None:
        return "hyd_hospitals"
    if root.find(".//kml:Schema[@name='health_facilities']", KML_NS) is not None:
        return "health_facilities"

    for placemark in root.findall(".//kml:Placemark", KML_NS):
        fields = _simple_data(placemark)
        if fields.get("Wardno_Name"):
            return "hyd_hospitals"
        if fields.get("Facility"):
            return "health_facilities"
    return "health_facilities"


def parse_hyd_hospitals_kml(path: Path | str) -> list[dict[str, Any]]:
    """Return normalized rows from GHMC / open-city Hyd_hospitals KML export."""
    tree = ET.parse(str(path))
    root = tree.getroot()
    rows: list[dict[str, Any]] = []

    for placemark in root.findall(".//kml:Placemark", KML_NS):
        fields = _simple_data(placemark)
        category = (fields.get("Category") or "").strip().upper()
        if category and category != "HOSPITALS":
            continue

        # In this dataset the Address column stores the facility name.
        name = (fields.get("Address") or "").strip()
        if not name:
            continue

        lat: float | None = None
        lon: float | None = None
        if fields.get("Latitude") and fields.get("Longitude"):
            try:
                lat = float(fields["Latitude"])
                lon = float(fields["Longitude"])
            except ValueError:
                lat, lon = None, None

        point = _point_coords(placemark)
        if point:
            plat, plon = point
            if lat is None or lon is None:
                lat, lon = plat, plon

        if lat is None or lon is None:
            continue
        if not _in_hyderabad_bbox(lat, lon):
            continue

        ward = fields.get("Wardno_Name", "").strip()
        circle = fields.get("Circleno_Name", "").strip()
        zone = fields.get("Zone", "").strip()
        address_parts = [part for part in (ward, circle, zone, "Hyderabad") if part]
        address = ", ".join(address_parts)

        rows.append(
            {
                "name": name,
                "address": address,
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "facility_type": category.title() if category else "Hospital",
                "district": "Hyderabad",
                "ward": ward or None,
                "circle": circle or None,
                "zone": zone or None,
                "source": "hyd_municipal_kml",
                "source_file": Path(path).name,
            }
        )

    rows.sort(key=lambda r: (r.get("zone", ""), r.get("name", "")))
    return rows


def parse_health_facilities_kml(path: Path | str) -> list[dict[str, Any]]:
    """Return normalized facility rows from a Telangana health_facilities KML export."""
    tree = ET.parse(str(path))
    root = tree.getroot()
    rows: list[dict[str, Any]] = []

    for placemark in root.findall(".//kml:Placemark", KML_NS):
        fields = _simple_data(placemark)
        name = fields.get("Facility", "").strip()
        if not name:
            continue

        lat: float | None = None
        lon: float | None = None
        if fields.get("Latitutde") and fields.get("Longitude"):
            try:
                lat = float(fields["Latitutde"])
                lon = float(fields["Longitude"])
            except ValueError:
                lat, lon = None, None

        point = _point_coords(placemark)
        if point:
            plat, plon = point
            if lat is None or lon is None:
                lat, lon = plat, plon

        if lat is None or lon is None:
            continue
        if not _in_hyderabad_bbox(lat, lon):
            continue

        address = fields.get("Address", "").strip() or None
        district = fields.get("District", "Hyderabad").strip()
        facility_type = fields.get("Facility_T", "").strip() or "Health Facility"

        rows.append(
            {
                "name": name,
                "address": address or f"{district}, Telangana",
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "facility_type": facility_type,
                "district": district,
                "hod": fields.get("HOD") or None,
                "object_id": fields.get("OBJECTID"),
                "source": "telangana_phc_kml",
                "source_file": Path(path).name,
            }
        )

    rows.sort(key=lambda r: (r.get("facility_type", ""), r.get("name", "")))
    return rows


def parse_hospital_kml(path: Path | str) -> list[dict[str, Any]]:
    """Parse a supported Hyderabad hospital KML export (auto-detect schema)."""
    schema = _detect_kml_schema(path)
    if schema == "hyd_hospitals":
        return parse_hyd_hospitals_kml(path)
    return parse_health_facilities_kml(path)


def facility_type_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        ft = row.get("facility_type") or "Unknown"
        counts[ft] = counts.get(ft, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))
