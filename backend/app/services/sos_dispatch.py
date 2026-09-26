"""Persist-then-notify SOS without broadcasting to a public topic."""

from __future__ import annotations

from datetime import datetime, timezone
import math
import time

from typing import Literal

from app.models.schemas import SosResponse
from app.services import database_service
from app.services.fast2sms import send_sos_sms

SmsStatus = Literal["sent", "failed", "skipped"]

_recent_keys: dict[str, float] = {}
_COOLDOWN_SEC = 30.0
_NO_LOCATION_SENTINEL = 0.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _call_line(*, emergency_contact_phone: str | None, emergency_contact_name: str | None) -> str:
    parts = ["Call 112 immediately if you are in danger."]
    if emergency_contact_phone:
        label = emergency_contact_name or "your emergency contact"
        parts.append(f"Also call {label} at {emergency_contact_phone}.")
    else:
        parts.append("Add an emergency contact in Settings so we can SMS them.")
    return " ".join(parts)


def _sms_line(sms_status: str, *, has_contact: bool) -> str:
    if sms_status == "sent":
        return " An SMS was sent to your emergency contact."
    if sms_status == "failed":
        return " We could not send the SMS to your emergency contact."
    if sms_status == "skipped" and has_contact:
        return " The SMS to your emergency contact was not sent."
    return ""


def _device_line(notification_status: str) -> str:
    if notification_status == "notification_accepted":
        return " An alert was sent to your registered devices."
    return ""


def dispatch_sos(
    *,
    lat: float | None = None,
    lon: float | None = None,
    situation: str | None = None,
    user_id: str | None = None,
    idempotency_key: str | None = None,
    emergency_contact_phone: str | None = None,
    emergency_contact_name: str | None = None,
    emergency_contact_relation: str | None = None,
    user_name: str | None = None,
) -> SosResponse:
    has_location = (
        lat is not None
        and lon is not None
        and math.isfinite(lat)
        and math.isfinite(lon)
    )
    maps_link = f"https://maps.google.com/?q={lat},{lon}" if has_location else "https://maps.google.com/"
    call_112 = _call_line(
        emergency_contact_phone=emergency_contact_phone,
        emergency_contact_name=emergency_contact_name,
    )

    if lat is not None and lon is not None and not has_location:
        return SosResponse(
            event_id=None,
            status="degraded",
            notification_status="notification_disabled",
            maps_link="https://maps.google.com/",
            message=f"Location is invalid. {call_112}",
            emergency_contact_phone=emergency_contact_phone,
            sms_status="skipped",
        )

    if idempotency_key:
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
                sms_status="skipped",
            )
        _recent_keys[idempotency_key] = now

    now = _now_iso()
    note = situation or ""
    if not has_location:
        prefix = "[location unavailable] "
        note = prefix + note if note else prefix.strip()

    initial_data = {
        "latitude": lat if has_location else _NO_LOCATION_SENTINEL,
        "longitude": lon if has_location else _NO_LOCATION_SENTINEL,
        "situation": note,
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
            sms_status="skipped",
        )

    notify_kwargs = {
        "to_phone": emergency_contact_phone,
        "relation": emergency_contact_relation,
        "user_name": user_name,
        "maps_link": maps_link,
        "has_location": has_location,
    }
    sms_status: SmsStatus = send_sos_sms(**notify_kwargs)
    sms_note = _sms_line(sms_status, has_contact=bool(emergency_contact_phone))

    tokens = database_service.list_device_tokens(user_id=user_id)
    if not tokens or not database_service.push_available():
        try:
            database_service.update_sos_record(
                event_id,
                {"notification_status": "notification_disabled", "updated_at": _now_iso()},
            )
        except Exception:
            pass
        loc = f" Location: {maps_link}" if has_location else " Location was not available."
        return SosResponse(
            event_id=event_id,
            status="recorded",
            notification_status="notification_disabled",
            maps_link=maps_link,
            message=f"SOS recorded.{sms_note} {call_112}{loc}",
            emergency_contact_phone=emergency_contact_phone,
            sms_status=sms_status,
        )

    try:
        message_id = database_service.send_device_push(
            tokens,
            title="ResQ AI — SOS Alert",
            body=(situation or "SOS triggered")[:120],
            data={
                "lat": str(lat) if has_location else "",
                "lon": str(lon) if has_location else "",
                "maps_link": maps_link,
                "event_id": event_id,
                "emergency_contact": emergency_contact_phone or "",
            },
        )
        database_service.update_sos_record(
            event_id,
            {
                "notification_status": "notification_accepted",
                "message_id": message_id,
                "updated_at": _now_iso(),
            },
        )
        loc = f" Location: {maps_link}" if has_location else " Location was not available."
        return SosResponse(
            event_id=event_id,
            status="recorded",
            notification_status="notification_accepted",
            maps_link=maps_link,
            message=(
                f"SOS recorded.{_device_line('notification_accepted')}{sms_note} "
                f"{call_112}{loc}"
            ),
            emergency_contact_phone=emergency_contact_phone,
            sms_status=sms_status,
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
            message=f"SOS recorded, but a device alert failed.{sms_note} {call_112} Location: {maps_link}",
            emergency_contact_phone=emergency_contact_phone,
            sms_status=sms_status,
        )
