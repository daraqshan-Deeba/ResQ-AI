from fastapi import APIRouter

from app.models.schemas import ShelterOut
from app.services import firebase_service

router = APIRouter(prefix="/api/shelters", tags=["shelters"])


@router.get("", response_model=list[ShelterOut])
async def list_shelters():
    return firebase_service.list_shelters()
