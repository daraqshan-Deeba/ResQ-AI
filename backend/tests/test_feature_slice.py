"""Feature-slice tests: SOS contact, no-location SOS, chat emergency guard."""

from app.main import app
from app.services.chat_intent import emergency_intent_reply


def test_chat_blocks_life_threat_without_llm():
    assert emergency_intent_reply("My father is having a heart attack, severe chest pain")
    assert emergency_intent_reply("there is a fire in my kitchen")
    assert emergency_intent_reply("what is a cyclone warning?") is None


def test_chat_route_returns_guard_text():
    client = app.test_client()
    res = client.post("/api/chat", json={"history": [], "message": "chest pain and not breathing"})
    assert res.status_code == 200
    body = res.get_json()
    assert "112" in body["reply"]
    assert "Get help" in body["reply"]


def test_sos_includes_emergency_contact(monkeypatch):
    monkeypatch.setattr(
        "app.services.database_service.get_emergency_contact",
        lambda _uid: {
            "name": "Priya",
            "phone": "+919999999999",
            "relation": "son",
            "user_name": "Rahul",
        },
    )
    monkeypatch.setattr("app.services.database_service.create_sos_record", lambda data: "evt-contact")
    monkeypatch.setattr("app.services.database_service.list_device_tokens", lambda user_id=None: [])
    monkeypatch.setattr("app.services.database_service.update_sos_record", lambda *a, **k: None)
    monkeypatch.setattr("app.services.database_service.push_available", lambda: False)

    client = app.test_client()
    res = client.post("/api/sos", json={"lat": 17.385, "lon": 78.4867})
    assert res.status_code == 200
    body = res.get_json()
    assert body["emergency_contact_phone"] == "+919999999999"
    assert "919999999999" in body["message"] or "Priya" in body["message"]


def test_sos_without_location_still_records(monkeypatch):
    monkeypatch.setattr("app.services.database_service.get_emergency_contact", lambda _uid: {"name": None, "phone": None})
    monkeypatch.setattr("app.services.database_service.create_sos_record", lambda data: "evt-noloc")
    monkeypatch.setattr("app.services.database_service.list_device_tokens", lambda user_id=None: [])
    monkeypatch.setattr("app.services.database_service.update_sos_record", lambda *a, **k: None)
    monkeypatch.setattr("app.services.database_service.push_available", lambda: False)

    client = app.test_client()
    res = client.post("/api/sos", json={"situation": "Need help"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "recorded"
    assert body["event_id"] == "evt-noloc"
    assert "112" in body["message"]
