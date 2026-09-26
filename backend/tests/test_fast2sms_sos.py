"""SOS SMS copy and Fast2SMS fail-open delivery."""

from app.services.fast2sms import (
    build_sos_sms_body,
    is_smsable_phone,
    send_sos_sms,
    to_fast2sms_number,
)


def test_sos_sms_copy_includes_relation_and_maps_link():
    body = build_sos_sms_body(
        relation="son",
        user_name="Rahul",
        maps_link="https://maps.google.com/?q=17.385,78.4867",
        has_location=True,
    )
    assert "Your son, Rahul," in body
    assert "has hit an SOS" in body
    assert "might be in danger or might need you" in body
    assert "https://maps.google.com/?q=17.385,78.4867" in body


def test_sos_sms_copy_without_name_or_location():
    body = build_sos_sms_body(
        relation="friend",
        user_name=None,
        maps_link="https://maps.google.com/",
        has_location=False,
    )
    assert body.startswith("Your friend has hit an SOS")
    assert "location was not available" in body.lower()


def test_public_emergency_numbers_are_not_smsable():
    assert is_smsable_phone("+91112") is False
    assert is_smsable_phone("112") is False
    assert is_smsable_phone("+919999999999") is True


def test_fast2sms_uses_ten_digit_indian_mobile():
    assert to_fast2sms_number("+919999999999") == "9999999999"
    assert to_fast2sms_number("+91112") is None


def test_send_sos_sms_skips_when_fast2sms_unconfigured():
    assert (
        send_sos_sms(
            to_phone="+919999999999",
            relation="daughter",
            user_name="Asha",
            maps_link="https://maps.google.com/?q=17.4,78.5",
            has_location=True,
        )
        == "skipped"
    )


def test_sos_dispatch_sends_sms_after_persist(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_sms(**kwargs):
        captured.update(kwargs)
        return "sent"

    monkeypatch.setattr(
        "app.services.database_service.get_emergency_contact",
        lambda _uid: {
            "name": "Priya",
            "phone": "+919999999999",
            "relation": "son",
            "user_name": "Rahul",
        },
    )
    monkeypatch.setattr("app.services.database_service.create_sos_record", lambda data: "evt-sms")
    monkeypatch.setattr("app.services.database_service.list_device_tokens", lambda user_id=None: [])
    monkeypatch.setattr("app.services.database_service.update_sos_record", lambda *a, **k: None)
    monkeypatch.setattr("app.services.database_service.push_available", lambda: False)
    monkeypatch.setattr("app.services.sos_dispatch.send_sos_sms", _fake_sms)

    from app.main import app

    client = app.test_client()
    res = client.post("/api/sos", json={"lat": 17.385, "lon": 78.4867})
    assert res.status_code == 200
    body = res.get_json()
    assert body["sms_status"] == "sent"
    assert "SMS was sent" in body["message"]
    assert captured["to_phone"] == "+919999999999"
    assert captured["relation"] == "son"
    assert captured["user_name"] == "Rahul"
    assert captured["has_location"] is True
    assert "maps.google.com" in str(captured["maps_link"])
