from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import AssessmentRequest, AssessmentResponse
from app.services import firebase_service, groq_service

router = APIRouter(prefix="/api/assessment", tags=["assessment"])


@router.post("", response_model=AssessmentResponse)
async def create_assessment(payload: AssessmentRequest):
    city = payload.city or settings.default_city
    result = await groq_service.run_assessment(payload.description, city, payload.language)

    firebase_service.log_emergency(
        description=payload.description,
        emergency_level=result.emergency_level,
        city=city,
    )

    return result
