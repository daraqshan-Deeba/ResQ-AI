import logging

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.auth import current_user_id, rate_limit, require_write_auth
from app.http_utils import parse_json, validation_error_response
from app.models.schemas import SosRequest
from app.services import database_service
from app.services.sos_dispatch import dispatch_sos

logger = logging.getLogger("resq.sos")

bp = Blueprint("sos", __name__, url_prefix="/api/sos")


@bp.post("")
@require_write_auth
@rate_limit(max_calls=10, window_sec=60)
def trigger_sos():
    try:
        payload = parse_json(SosRequest, request.get_json())
    except ValidationError as exc:
        return validation_error_response(exc)

    user_id = current_user_id()
    contact = database_service.get_emergency_contact(user_id)
    if not user_id:
        logger.warning("SOS has no signed-in user; emergency-contact SMS will be skipped")
    elif not contact.get("phone"):
        logger.warning("SOS user has no emergency contact phone on profile")
    result = dispatch_sos(
        lat=payload.lat,
        lon=payload.lon,
        situation=payload.situation,
        user_id=user_id,
        idempotency_key=payload.idempotency_key,
        emergency_contact_phone=contact.get("phone"),
        emergency_contact_name=contact.get("name"),
        emergency_contact_relation=contact.get("relation"),
        user_name=contact.get("user_name"),
    )
    return jsonify(result.model_dump())
