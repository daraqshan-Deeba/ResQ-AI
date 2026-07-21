from fastapi import APIRouter, Query

from app.core.config import settings
from app.models.schemas import HospitalOut
from app.services import maps_service

router = APIRouter(prefix="/api/hospitals", tags=["hospitals"])


@router.get("", response_model=list[HospitalOut])
async def list_hospitals(
    lat: float = Query(default=None),
    lon: float = Query(default=None),
):
    return await maps_service.get_nearby_hospitals(
        lat or settings.default_lat, lon or settings.default_lon
    )
