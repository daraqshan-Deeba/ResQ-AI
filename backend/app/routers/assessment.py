from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.schemas import AssessmentRequest, AssessmentResult
from app.services import emergency_orchestrator, firebase_service

router = APIRouter(prefix="/api/assessment", tags=["assessment"])


@router.post("", response_model=AssessmentResult)
async def create_assessment(payload: AssessmentRequest):
    city = payload.city or settings.default_city
    try:
        result = await emergency_orchestrator.orchestrate_emergency_assessment(
            description=payload.description,
            city=city,
            lat=payload.lat,
            lon=payload.lon,
            language=payload.language,
            request_sos=payload.request_sos,
            situation=payload.situation,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    firebase_service.log_emergency(
        description=payload.description,
        emergency_level=result.emergency_level,
        city=city,
    )

    return result

