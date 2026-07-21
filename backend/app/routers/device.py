from fastapi import APIRouter

from app.models.schemas import DeviceTokenIn
from app.services import firebase_service

router = APIRouter(prefix="/api/device-token", tags=["push"])


@router.post("")
async def register_device(payload: DeviceTokenIn):
    firebase_service.register_device(payload.token)
    return {"status": "registered"}
