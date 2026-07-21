from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
# Importing this triggers firebase_admin.initialize_app(...) once, at startup.
from app.services import firebase_service  # noqa: F401
from app.routers import assessment, chat, device, hospitals, reports, shelters, sos, weather

app = FastAPI(title="ResQ AI Backend", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assessment.router)
app.include_router(chat.router)
app.include_router(weather.router)
app.include_router(hospitals.router)
app.include_router(shelters.router)
app.include_router(reports.router)
app.include_router(sos.router)
app.include_router(device.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
