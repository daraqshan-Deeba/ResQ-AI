"""
SOS router — Step 3: decoupled persistence and notification.

Flow:
  1. Validate request (FastAPI model validation).
  2. Generate UTC timestamps.
  3. Attempt Firestore persistence FIRST (create_sos_record).
     - On failure → return status="degraded" immediately.
  4. Attempt FCM notification (send_topic_push).
     - On success → update record: notification_status="notification_accepted".
     - On failure  → update record: notification_status="notification_failed".
     Either way the record is already durable; notification outcome never
     causes the SOS event itself to be lost.
  5. Return SosResponse to the caller.

FCM being unavailable (firebase_available is False) is treated as a known,
handled state (notification_disabled) — not an error — provided Firestore
itself is available, since the two Firebase features are independent at the
API level.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter

from app.models.schemas import SosRequest, SosResponse
from app.services import firebase_service

logger = logging.getLogger("resq.sos")

router = APIRouter(prefix="/api/sos", tags=["sos"])

_NOW_ISO = lambda: datetime.now(timezone.utc).isoformat()  # noqa: E731


@router.post("", response_model=SosResponse)
async def trigger_sos(payload: SosRequest) -> SosResponse:
    maps_link = f"https://maps.google.com/?q={payload.lat},{payload.lon}"
    now = _NOW_ISO()

    # ------------------------------------------------------------------ #
    # Step 3-A: Persist the event record BEFORE attempting notification.  #
    # If Firestore is unavailable we return a degraded response and stop. #
    # ------------------------------------------------------------------ #
    initial_data = {
        "latitude": payload.lat,
        "longitude": payload.lon,
        "situation": payload.situation,
        "created_at": now,
        "updated_at": now,
        "notification_status": "pending_notification",
        "message_id": None,
        "error_detail": None,
    }

    try:
        event_id = firebase_service.create_sos_record(initial_data)
    except RuntimeError:
        # Firestore is unavailable — nothing was persisted.
        logger.warning("trigger_sos: Firestore unavailable; returning degraded response.")
        return SosResponse(
            event_id=None,
            status="degraded",
            notification_status="notification_disabled",
            maps_link=maps_link,
            message=(
                "⚠️ Emergency services could not be reached at this moment. "
                "Call 112 immediately. Your SOS could not be recorded — "
                "please use a phone call as backup."
            ),
        )

    # ------------------------------------------------------------------ #
    # Step 3-B: Attempt FCM notification (best-effort).                  #
    # The record is already durable at this point regardless of outcome.  #
    # ------------------------------------------------------------------ #

    # Case 1 — FCM not available (Firebase itself is up for Firestore but
    # messaging is separately disabled, or firebase_available is False).
    if not firebase_service.firebase_available:
        firebase_service.update_sos_record(
            event_id,
            {
                "notification_status": "notification_disabled",
                "updated_at": _NOW_ISO(),
            },
        )
        return SosResponse(
            event_id=event_id,
            status="recorded",
            notification_status="notification_disabled",
            maps_link=maps_link,
            message=(
                "✅ SOS recorded. Push notifications are currently disabled — "
                "call 112 directly to reach emergency services. "
                f"Your location: {maps_link}"
            ),
        )

    # Case 2 — Attempt FCM send.
    notify_body = payload.situation or "An SOS was triggered — tap for live location."
    try:
        message_id = firebase_service.send_topic_push(
            title="🚨 ResQ AI — SOS Alert",
            body=notify_body,
            data={
                "lat": str(payload.lat),
                "lon": str(payload.lon),
                "maps_link": maps_link,
                "event_id": event_id,
            },
        )
        # FCM accepted the message.
        firebase_service.update_sos_record(
            event_id,
            {
                "notification_status": "notification_accepted",
                "message_id": message_id,
                "updated_at": _NOW_ISO(),
            },
        )
        return SosResponse(
            event_id=event_id,
            status="recorded",
            notification_status="notification_accepted",
            maps_link=maps_link,
            message=(
                "✅ SOS recorded and alert sent to responders. "
                f"Your live location: {maps_link}"
            ),
        )

    except Exception as exc:
        # FCM failed — record the failure detail (safe, no stack trace).
        safe_detail = f"{type(exc).__name__}: notification delivery failed"
        logger.warning(
            "trigger_sos: FCM send failed for event %s (%s: %s); "
            "event record is intact.",
            event_id,
            type(exc).__name__,
            exc,
        )
        firebase_service.update_sos_record(
            event_id,
            {
                "notification_status": "notification_failed",
                "error_detail": safe_detail,
                "updated_at": _NOW_ISO(),
            },
        )
        return SosResponse(
            event_id=event_id,
            status="recorded",
            notification_status="notification_failed",
            maps_link=maps_link,
            message=(
                "✅ SOS recorded, but the push notification could not be delivered. "
                "Call 112 directly. "
                f"Your location: {maps_link}"
            ),
        )
