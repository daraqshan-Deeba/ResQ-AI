from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.auth import current_user_id, rate_limit, require_write_auth
from app.http_utils import parse_json, validation_error_response
from app.models.schemas import DeviceTokenIn
from app.services import database_service

bp = Blueprint("device", __name__, url_prefix="/api/device-token")


@bp.post("")
@require_write_auth
@rate_limit(max_calls=20, window_sec=60)
def register_device():
    try:
        payload = parse_json(DeviceTokenIn, request.get_json())
    except ValidationError as exc:
        return validation_error_response(exc)

    database_service.register_device(payload.token, user_id=current_user_id())
    return jsonify({"status": "registered"})
