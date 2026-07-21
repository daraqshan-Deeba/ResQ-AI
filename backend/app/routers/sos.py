from fastapi import APIRouter, HTTPException

from app.models.schemas import SosRequest
from app.services import firebase_service

router = APIRouter(prefix="/api/sos", tags=["sos"])


@router.post("")
async def trigger_sos(payload: SosRequest):
    maps_link = f"https://maps.google.com/?q={payload.lat},{payload.lon}"
    body = payload.situation or "An SOS was triggered — tap for live location."

    try:
        message_id = firebase_service.send_topic_push(
            title="🚨 ResQ AI — SOS Alert",
            body=body,
            data={"lat": payload.lat, "lon": payload.lon, "maps_link": maps_link},
        )
    except Exception as exc:  # firebase raises various error types depending on the failure
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"status": "sent", "message_id": message_id}
