from unittest.mock import AsyncMock, patch

from app.models.schemas import TrafficIncident, TrafficOverview


def test_traffic_nearby_requires_coords(client):
    res = client.get("/api/traffic/nearby")
    assert res.status_code == 400
    assert "lat and lon" in res.get_json()["detail"]


def test_traffic_nearby_returns_overview(client):
    mock_overview = TrafficOverview(
        congestion_level="moderate",
        incident_count=1,
        incidents=[
            TrafficIncident(
                id="osm-way-1",
                type="construction",
                title="Under construction: Main Road",
                description="Road work",
                lat=17.39,
                lon=78.49,
                distance_km=1.2,
                severity="moderate",
                source="openstreetmap",
                verified=True,
            )
        ],
        radius_km=5.0,
        lat=17.385,
        lon=78.487,
        sources_used=["openstreetmap"],
    )

    with patch(
        "app.services.traffic_service.get_traffic_nearby_safe",
        new_callable=AsyncMock,
    ) as mock_fn:
        from app.models.schemas import ServiceResult

        mock_fn.return_value = ServiceResult(available=True, data=mock_overview)
        res = client.get("/api/traffic/nearby?lat=17.385&lon=78.487")

    assert res.status_code == 200
    data = res.get_json()
    assert data["congestion_level"] == "moderate"
    assert data["incident_count"] == 1
    assert data["incidents"][0]["type"] == "construction"


def test_classify_report_message():
    from app.services.traffic_service import _classify_report_message

    assert _classify_report_message("Major accident on NH44") == "accident"
    assert _classify_report_message("Road under construction near metro") == "construction"
    assert _classify_report_message("Heavy traffic congestion") == "congestion"
    assert _classify_report_message("It is raining") is None


def test_community_incidents_filtered_by_radius(monkeypatch):
    from app.services import traffic_service

    monkeypatch.setattr(
        "app.services.traffic_service.database_service.list_reports",
        lambda: [
            {
                "id": "near",
                "area": "Uppal",
                "lat": 17.3980,
                "lon": 78.5580,
                "message": "Multi-vehicle collision on highway exit.",
                "verified": False,
            },
            {
                "id": "far",
                "area": "Banjara Hills",
                "lat": 17.4150,
                "lon": 78.4350,
                "message": "Road accident near Road No. 12 junction.",
                "verified": False,
            },
            {
                "id": "no-coords",
                "area": "Unknown Place",
                "message": "Road under construction near metro.",
                "verified": True,
            },
        ],
    )

    # User near Nacharam / Uppal corridor (matches dashboard screenshot coords)
    incidents = traffic_service._fetch_community_incidents(
        17.425914, 78.552289, radius_km=5.0
    )
    areas = {i.title.split(" — ")[-1] for i in incidents}
    assert "Uppal" in areas
    assert "Banjara Hills" not in areas
    assert all(i.distance_km is not None and i.distance_km <= 5.0 for i in incidents)
