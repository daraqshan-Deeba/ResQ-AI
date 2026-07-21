from pydantic import BaseModel, Field


# ---------- Assessment (Responder / "Get Help Now") ----------
class AssessmentRequest(BaseModel):
    description: str = Field(..., description="What the user typed or a preset filled in")
    city: str | None = Field(None, description="Optional area/city; falls back to server default")
    lat: float | None = None
    lon: float | None = None
    language: str = Field("English", description="Reply language, e.g. English / Telugu / Hindi")


class AssessmentResponse(BaseModel):
    emergency_level: str          # e.g. "Critical" | "High" | "Moderate" | "Low"
    whats_happening: str
    immediate_first_aid: list[str]
    what_not_to_do: list[str]
    call_these_services: list[str]
    things_to_carry: list[str]
    nearby_help: list[dict]       # [{"name": ..., "url": ...}]
    raw_text: str                 # full model output, for debugging / fallback display


# ---------- Chat (multi-turn Responder) ----------
class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    text: str


class ChatRequest(BaseModel):
    history: list[ChatMessage]
    message: str
    city: str | None = None


class ChatResponse(BaseModel):
    reply: str


# ---------- Weather / risk (Sentinel) ----------
class WeatherSummary(BaseModel):
    temp_c: float
    condition: str
    rain_mm_last_hour: float
    alert_active: bool
    alert_headline: str | None = None


class RiskScore(BaseModel):
    score: int                    # 0-100
    level: str                    # "watch" | "warning" | "critical" | "safe"
    rainfall_intensity_pct: int
    drainage_capacity_pct: int    # placeholder factor — see risk_service.py


# ---------- Hospitals / Shelters (Wayfinder) ----------
class HospitalOut(BaseModel):
    name: str
    lat: float
    lon: float
    distance_km: float | None = None
    address: str | None = None
    source: str = "google_places"


class ShelterOut(BaseModel):
    id: str
    name: str
    capacity: int
    occupied: int
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    source: str = "manual"        # flag that this is admin-entered, not a live feed


# ---------- Community reports ----------
class ReportIn(BaseModel):
    area: str
    message: str
    reporter_name: str | None = None


class ReportOut(BaseModel):
    id: str
    area: str
    message: str
    verified: bool
    created_at: str


# ---------- SOS ----------
class SosRequest(BaseModel):
    lat: float
    lon: float
    situation: str | None = None


# ---------- Push notification device registration ----------
class DeviceTokenIn(BaseModel):
    token: str
