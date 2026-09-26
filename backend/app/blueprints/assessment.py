from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.auth import rate_limit
from app.core.config import settings
from app.http_utils import parse_json, validation_error_response
from app.i18n.languages import normalize_language
from app.models.schemas import AssessmentRequest
from app.services import database_service, emergency_orchestrator

bp = Blueprint("assessment", __name__, url_prefix="/api/assessment")


@bp.post("")
@rate_limit(max_calls=20, window_sec=60)
async def create_assessment():
    try:
        payload = parse_json(AssessmentRequest, request.get_json())
    except ValidationError as exc:
        return validation_error_response(exc)

    city = payload.city or settings.default_city
    try:
        result = await emergency_orchestrator.orchestrate_emergency_assessment(
            description=payload.description,
            city=city,
            lat=payload.lat,
            lon=payload.lon,
            language=normalize_language(payload.language),
            request_sos=payload.request_sos,
            situation=payload.situation,
        )
    except ValueError as exc:
        return jsonify({"detail": str(exc)}), 400

    database_service.log_emergency(
        description=payload.description,
        emergency_level=result.emergency_level,
        city=city,
    )

    return jsonify(result.model_dump())
