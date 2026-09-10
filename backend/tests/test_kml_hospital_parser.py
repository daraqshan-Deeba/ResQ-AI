from pathlib import Path

from app.data_paths import GHMC_KML, PHC_KML
from app.services.kml_hospital_parser import (
    facility_type_counts,
    parse_health_facilities_kml,
    parse_hospital_kml,
    parse_hyd_hospitals_kml,
)

KML_PATH = PHC_KML
HYD_KML_PATH = GHMC_KML


def test_parse_kml_extracts_facilities():
    if not KML_PATH.exists():
        return
    rows = parse_health_facilities_kml(KML_PATH)
    assert len(rows) >= 50
    sample = rows[0]
    assert "name" in sample
    assert "lat" in sample
    assert "lon" in sample
    assert "facility_type" in sample
    assert sample["source"] == "telangana_phc_kml"


def test_facility_type_counts():
    if not KML_PATH.exists():
        return
    rows = parse_health_facilities_kml(KML_PATH)
    counts = facility_type_counts(rows)
    assert sum(counts.values()) == len(rows)
    assert any("PHC" in k or "Hospital" in k or "Dawakhana" in k for k in counts)


def test_parse_hyd_hospitals_kml():
    if not HYD_KML_PATH.exists():
        return
    rows = parse_hyd_hospitals_kml(HYD_KML_PATH)
    assert len(rows) >= 900
    sample = rows[0]
    assert sample["source"] == "hyd_municipal_kml"
    assert sample["name"]
    assert sample["zone"]
    assert sample["facility_type"] == "Hospitals"


def test_parse_hospital_kml_auto_detects_schema():
    if not HYD_KML_PATH.exists():
        return
    rows = parse_hospital_kml(HYD_KML_PATH)
    assert rows[0]["source"] == "hyd_municipal_kml"
