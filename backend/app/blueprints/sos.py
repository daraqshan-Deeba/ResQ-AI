import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.http_utils import parse_json, validation_error_response
from app.models.schemas import SosRequest, SosResponse
from app.services import database_service

logger = logging.getLogger("resq.sos")

bp = Blueprint("sos", __name__, url_prefix="/api/sos")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@bp.post("")
def trigger_sos():
    try:
        payload = parse_json(SosRequest, request.get_json())
    except ValidationError as exc:
        return validation_error_response(exc)

    maps_link = f"https://maps.google.com/?q={payload.lat},{payload.lon}"
    now = _now_iso()

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
        event_id = database_service.create_sos_record(initial_data)
    except RuntimeError:
        logger.warning("trigger_sos: Firestore unavailable; returning degraded response.")
        return jsonify(
            SosResponse(
                event_id=None,
                status="degraded",
                notification_status="notification_disabled",
                maps_link=maps_link,
                message=(
                    "⚠️ Emergency services could not be reached at this moment. "
                    "Call 112 immediately. Your SOS could not be recorded — "
                    "please use a phone call as backup."
                ),
            ).model_dump()
        )

    if not database_service.push_available():
        database_service.update_sos_record(
            event_id,
            {
                "notification_status": "notification_disabled",
                "updated_at": _now_iso(),
            },
        )
        return jsonify(
            SosResponse(
                event_id=event_id,
                status="recorded",
                notification_status="notification_disabled",
                maps_link=maps_link,
                message=(
                    "✅ SOS recorded. Push notifications are currently disabled — "
                    "call 112 directly to reach emergency services. "
                    f"Your location: {maps_link}"
                ),
            ).model_dump()
        )

    notify_body = payload.situation or "An SOS was triggered — tap for live location."
    try:
        message_id = database_service.send_topic_push(
            title="🚨 ResQ AI — SOS Alert",
            body=notify_body,
            data={
                "lat": str(payload.lat),
                "lon": str(payload.lon),
                "maps_link": maps_link,
                "event_id": event_id,
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
        return jsonify(
            SosResponse(
                event_id=event_id,
                status="recorded",
                notification_status="notification_accepted",
                maps_link=maps_link,
                message=(
                    "✅ SOS recorded and alert sent to responders. "
                    f"Your live location: {maps_link}"
                ),
            ).model_dump()
        )
    except Exception as exc:
        safe_detail = f"{type(exc).__name__}: notification delivery failed"
        logger.warning(
            "trigger_sos: FCM send failed for event %s (%s: %s); event record is intact.",
            event_id,
            type(exc).__name__,
            exc,
        )
        database_service.update_sos_record(
            event_id,
            {
                "notification_status": "notification_failed",
                "error_detail": safe_detail,
                "updated_at": _now_iso(),
            },
        )
        return jsonify(
            SosResponse(
                event_id=event_id,
                status="recorded",
                notification_status="notification_failed",
                maps_link=maps_link,
                message=(
                    "✅ SOS recorded, but the push notification could not be delivered. "
                    "Call 112 directly. "
                    f"Your location: {maps_link}"
                ),
            ).model_dump()
        )
