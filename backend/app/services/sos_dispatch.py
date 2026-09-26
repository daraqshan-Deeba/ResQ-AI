"""Persist-then-notify SOS without broadcasting to a public topic."""

from __future__ import annotations

from datetime import datetime, timezone
import math

from app.models.schemas import SosResponse
from app.services import database_service

_recent_keys: dict[str, float] = {}
_COOLDOWN_SEC = 30.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def dispatch_sos(
    *,
    lat: float,
    lon: float,
    situation: str | None = None,
    user_id: str | None = None,
    idempotency_key: str | None = None,
    emergency_contact_phone: str | None = None,
) -> SosResponse:
    maps_link = f"https://maps.google.com/?q={lat},{lon}"
    call_112 = "Call 112 immediately if you are in danger."

    if not math.isfinite(lat) or not math.isfinite(lon):
        return SosResponse(
            event_id=None,
            status="degraded",
            notification_status="notification_disabled",
            maps_link="https://maps.google.com/",
            message=f"Location is invalid. {call_112}",
            emergency_contact_phone=emergency_contact_phone,
        )

    if idempotency_key:
        import time

        now = time.monotonic()
        last = _recent_keys.get(idempotency_key)
        if last is not None and now - last < _COOLDOWN_SEC:
            return SosResponse(
                event_id=None,
                status="recorded",
                notification_status="notification_disabled",
                maps_link=maps_link,
                message=f"SOS already sent recently. {call_112} Location: {maps_link}",
                emergency_contact_phone=emergency_contact_phone,
            )
        _recent_keys[idempotency_key] = now

    now = _now_iso()
    initial_data = {
        "latitude": lat,
        "longitude": lon,
        "situation": situation,
        "created_at": now,
        "updated_at": now,
        "notification_status": "pending_notification",
        "message_id": None,
        "error_detail": None,
        "user_id": user_id,
    }

    try:
        event_id = database_service.create_sos_record(initial_data)
    except Exception:
        return SosResponse(
            event_id=None,
            status="degraded",
            notification_status="notification_disabled",
            maps_link=maps_link,
            message=f"SOS could not be recorded. {call_112}",
            emergency_contact_phone=emergency_contact_phone,
        )

    tokens = database_service.list_device_tokens(user_id=user_id)
    if not tokens or not database_service.push_available():
        try:
            database_service.update_sos_record(
                event_id,
                {"notification_status": "notification_disabled", "updated_at": _now_iso()},
            )
        except Exception:
            pass
        contact_note = (
            f" Also call your emergency contact {emergency_contact_phone}."
            if emergency_contact_phone
            else ""
        )
        return SosResponse(
            event_id=event_id,
            status="recorded",
            notification_status="notification_disabled",
            maps_link=maps_link,
            message=(
                f"SOS recorded. No private device alert was sent. {call_112}{contact_note} "
                f"Location: {maps_link}"
            ),
            emergency_contact_phone=emergency_contact_phone,
        )

    try:
        message_id = database_service.send_device_push(
            tokens,
            title="ResQ AI — SOS Alert",
            body=(situation or "SOS triggered")[:120],
            data={"lat": str(lat), "lon": str(lon), "maps_link": maps_link, "event_id": event_id},
        )
        database_service.update_sos_record(
            event_id,
            {
                "notification_status": "notification_accepted",
                "message_id": message_id,
                "updated_at": _now_iso(),
            },
        )
        return SosResponse(
            event_id=event_id,
            status="recorded",
            notification_status="notification_accepted",
            maps_link=maps_link,
            message=(
                f"SOS recorded and an alert was sent to your registered devices. "
                f"{call_112} Location: {maps_link}"
            ),
            emergency_contact_phone=emergency_contact_phone,
        )
    except Exception as exc:
        try:
            database_service.update_sos_record(
                event_id,
                {
                    "notification_status": "notification_failed",
                    "error_detail": f"{type(exc).__name__}: notification delivery failed",
                    "updated_at": _now_iso(),
                },
            )
        except Exception:
            pass
        return SosResponse(
            event_id=event_id,
            status="recorded",
            notification_status="notification_failed",
            maps_link=maps_link,
            message=f"SOS recorded, but the device alert failed. {call_112} Location: {maps_link}",
            emergency_contact_phone=emergency_contact_phone,
        )
