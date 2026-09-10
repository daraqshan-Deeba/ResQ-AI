from pathlib import Path

from app.services.hotosm_hospital_parser import (
    load_geojson_from_zip_bytes,
    parse_hotosm_geojson,
)

CACHE_ZIP = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "downloads"
    / "hotosm_ind_health_facilities_points_geojson.zip"
)


def test_parse_hotosm_geojson_filters_hyderabad_bbox():
    if not CACHE_ZIP.exists():
        return

    geojson = load_geojson_from_zip_bytes(CACHE_ZIP.read_bytes())
    rows = parse_hotosm_geojson(geojson, hyderabad_only=True)

    assert len(rows) >= 500
    sample = rows[0]
    assert sample["source"] == "hotosm_hdx"
    assert 17.2 <= sample["lat"] <= 17.65
    assert 78.3 <= sample["lon"] <= 78.62


def test_parse_hotosm_geojson_from_minimal_fixture():
    fixture = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [78.47, 17.38]},
                "properties": {
                    "name": "Test City Hospital",
                    "amenity": "hospital",
                    "healthcare": "hospital",
                    "addr:city": "Hyderabad",
                    "osm_id": 123,
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [77.0, 28.6]},
                "properties": {"name": "Delhi Clinic", "amenity": "clinic"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [78.48, 17.39]},
                "properties": {"name": "Corner Pharmacy", "amenity": "pharmacy"},
            },
        ],
    }
    rows = parse_hotosm_geojson(fixture, hyderabad_only=True)
    assert len(rows) == 1
    assert rows[0]["name"] == "Test City Hospital"
    assert rows[0]["facility_type"] == "Hospital"
