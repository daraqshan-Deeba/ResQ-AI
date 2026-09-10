import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.services import firebase_service


def test_config_defaults_without_env():
    """Verify Settings initializes with safe defaults when no env keys are provided."""
    cfg = Settings(
        GROQ_API_KEY="",
        GROK_API_KEY="",
        OPENWEATHER_API_KEY="",
        GOOGLE_MAPS_API_KEY="",
        _env_file=None,
    )
    assert cfg.groq_api_key == ""
    assert cfg.groq_model == "llama-3.3-70b-versatile"
    assert cfg.is_groq_available is False
    assert cfg.default_city == "Hyderabad"


def test_config_backward_compatibility_alias():
    """Verify GROK_API_KEY alias works and GROQ_API_KEY takes precedence."""
    legacy_cfg = Settings(GROK_API_KEY="legacy-xai-style-key", _env_file=None)
    assert legacy_cfg.groq_api_key == "legacy-xai-style-key"
    assert legacy_cfg.is_groq_available is True

    canonical_cfg = Settings(GROQ_API_KEY="canonical-groq-key", _env_file=None)
    assert canonical_cfg.groq_api_key == "canonical-groq-key"

    precedence_cfg = Settings(
        GROQ_API_KEY="canonical-win",
        GROK_API_KEY="legacy-lose",
        _env_file=None,
    )
    assert precedence_cfg.groq_api_key == "canonical-win"


def test_firebase_degraded_when_credentials_missing():
    """Verify Firebase-dependent functions degrade safely when credentials are not loaded."""
    assert firebase_service.firebase_available is False
    assert firebase_service.firebase_error_detail is not None

    # Read/list operations return safe empty lists
    assert firebase_service.list_shelters() == []
    assert firebase_service.list_reports() == []

    # Non-critical write operations do not raise
    firebase_service.log_emergency("Water rising", "Low", "Hyderabad")
    firebase_service.register_device("dummy-device-token")

    # Critical operations raise controlled RuntimeErrors
    with pytest.raises(RuntimeError, match="Firebase Cloud Messaging is unavailable"):
        firebase_service.send_topic_push("Alert", "Body")

    with pytest.raises(RuntimeError, match="Firebase/Firestore is unavailable"):
        firebase_service.add_shelter({"name": "Test"})

    with pytest.raises(RuntimeError, match="Firebase/Firestore is unavailable"):
        firebase_service.add_report("Area", "Message")


def test_health_endpoint():
    """Verify GET /health returns 200 and status ok."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_shelters_and_reports_get_endpoints_when_firebase_unavailable():
    """Verify reading shelters and reports returns empty lists instead of 500 crashes."""
    client = TestClient(app)
    shelters_res = client.get("/api/shelters")
    assert shelters_res.status_code == 200
    assert shelters_res.json() == []

    reports_res = client.get("/api/reports")
    assert reports_res.status_code == 200
    assert reports_res.json() == []


def test_report_post_endpoint_when_firebase_unavailable():
    """Verify submitting a report when database is unavailable returns controlled 503."""
    client = TestClient(app)
    res = client.post("/api/reports", json={"area": "Tarnaka", "message": "Flooding near underpass"})
    assert res.status_code == 503
    assert "temporarily unavailable" in res.json()["detail"]


def test_sos_endpoint_when_firebase_unavailable():
    """Verify SOS returns 200 degraded (not 503) when Firebase is unavailable.

    Step 3 (SOS persistence) decoupled persistence from notification. When
    Firestore itself is unreachable the endpoint now returns
    status=200 with body status='degraded' and notification_status='notification_disabled'
    rather than raising HTTP 503, because returning 503 would cause the frontend
    to display a generic error and give the user no guidance — instead the
    degraded response always includes a human-readable message and the maps_link.
    """
    client = TestClient(app)
    res = client.post("/api/sos", json={"lat": 17.3850, "lon": 78.4867})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "degraded"
    assert body["notification_status"] == "notification_disabled"
    assert "maps_link" in body
    assert "message" in body
    # Sanity: event_id is absent (nothing was persisted)
    assert body.get("event_id") is None


def test_firebase_initialized_when_credentials_valid(monkeypatch):
    """Verify that when credentials exist, init_firebase initializes db and sets firebase_available=True."""
    from unittest.mock import MagicMock
    import os

    mock_db = MagicMock()
    mock_app = MagicMock()

    monkeypatch.setattr(os.path, "exists", lambda path: True)
    monkeypatch.setattr(firebase_service.credentials, "Certificate", lambda path: MagicMock())
    monkeypatch.setattr(firebase_service.firebase_admin, "initialize_app", lambda cred: mock_app)
    monkeypatch.setattr(firebase_service.firestore, "client", lambda: mock_db)
    monkeypatch.setattr(firebase_service.firebase_admin, "_apps", {})

    firebase_service.init_firebase()
    try:
        assert firebase_service.firebase_available is True
        assert firebase_service.db is mock_db
        assert firebase_service.firebase_error_detail is None

        # When available, list_shelters queries db
        mock_doc = MagicMock()
        mock_doc.id = "shelter-1"
        mock_doc.to_dict.return_value = {"name": "Community Center", "capacity": 100, "occupied": 20}
        mock_db.collection.return_value.stream.return_value = [mock_doc]

        shelters = firebase_service.list_shelters()
        assert len(shelters) == 1
        assert shelters[0]["id"] == "shelter-1"
        assert shelters[0]["name"] == "Community Center"
    finally:
        # Reset back to degraded mode for subsequent tests
        firebase_service.firebase_available = False
        firebase_service.db = None
        firebase_service.firebase_error_detail = "Firebase credentials file not found"
