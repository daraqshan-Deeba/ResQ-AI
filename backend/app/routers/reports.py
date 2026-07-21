from fastapi import APIRouter

from app.models.schemas import ReportIn, ReportOut
from app.services import firebase_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("", response_model=list[ReportOut])
async def list_reports():
    return firebase_service.list_reports()


@router.post("", response_model=ReportOut)
async def create_report(payload: ReportIn):
    return firebase_service.add_report(
        area=payload.area, message=payload.message, reporter_name=payload.reporter_name
    )
