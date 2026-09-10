"""
Emergency Orchestrator Service — Step 7: Unified Emergency Assessment Pipeline

The orchestrator is the single coordination layer that assembles:
  Stage 1 — Request Validation
  Stage 2 — Authoritative Triage Classification
  Stage 3 — Deterministic Weather Risk Assessment
  Stage 4 — Advisory Action Planning
  Stage 5 — Centralized Weakest-Link Confidence Aggregation
  Stage 6 — Optional Location-Dependent Hospital Lookup
  Stage 7 — Optional Explicit User SOS Integration
  Stage 8 — Result Assembly with Graceful Partial-Failure Handling

Architectural Constraints:
  • The LLM is NEVER above the orchestrator and has ZERO severity or confidence authority.
  • Triage and weather risk are deterministic and authoritative.
  • SOS is NEVER automatically triggered — only when explicitly requested.
  • Location is NEVER automatically captured — hospital lookup requires explicit coordinates.
  • Partial service failures degrade gracefully; they do not crash the assessment.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.config import settings
from app.models.schemas import (
    ActionPlan,
    ActionPlanContext,
    AssessmentResult,
    CommunityInsight,
    ConfidenceResult,
    EmergencyCategory,
    HospitalOut,
    RiskScore,
    ServiceResult,
    SosResponse,
    TriageResult,
    WeatherSummary,
)
from app.services import (
    action_planner_service,
    confidence_service,
    database_service,
    maps_service,
    supabase_service,
    triage_service,
    weather_service,
)
from app.services.action_planner_service import DEFAULT_TRUSTED_CONTACTS

logger = logging.getLogger("resq.orchestrator")

_NOW_ISO = lambda: datetime.now(timezone.utc).isoformat()  # noqa: E731


# ─────────────────────────────────────────────────────────────────────────────
# Request Validation (Stage 1)
# ─────────────────────────────────────────────────────────────────────────────

def validate_assessment_request(
    description: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    request_sos: bool = False,
) -> None:
    """Validate assessment inputs and ensure coordinate integrity.

    Raises:
        ValueError: On empty text, oversized text, partial coordinates, invalid range,
                    or SOS requested without coordinates.
    """
    if not description or not description.strip():
        raise ValueError("Emergency description cannot be empty.")

    if len(description) > 5000:
        raise ValueError("Emergency description exceeds maximum length of 5000 characters.")

    # Coordinates must be provided together or not at all
    if (lat is None and lon is not None) or (lon is None and lat is not None):
        raise ValueError("Both latitude and longitude must be provided together.")

    if lat is not None:
        if not isinstance(lat, (int, float)) or math.isnan(lat) or math.isinf(lat):
            raise ValueError(f"Latitude must be a valid finite number, got {lat}.")
        if lat < -90.0 or lat > 90.0:
            raise ValueError(f"Latitude must be between -90.0 and 90.0, got {lat}.")

    if lon is not None:
        if not isinstance(lon, (int, float)) or math.isnan(lon) or math.isinf(lon):
            raise ValueError(f"Longitude must be a valid finite number, got {lon}.")
        if lon < -180.0 or lon > 180.0:
            raise ValueError(f"Longitude must be between -180.0 and 180.0, got {lon}.")

    # SOS requires explicit GPS coordinates
    if request_sos and (lat is None or lon is None):
        raise ValueError("Coordinates (latitude and longitude) are required when requesting SOS.")


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic Emergency Level Decision (Stage 8)
# ─────────────────────────────────────────────────────────────────────────────

def determine_emergency_level(
    category: EmergencyCategory,
    risk_level: Optional[str] = None,
) -> str:
    """Deterministically derive emergency level without LLM involvement.

    Rules:
      - Critical: Life-threatening hazards (electrocution, snakebite) OR critical weather risk
      - High: Structural collapse, severe flood, cyclone, OR warning weather risk
      - Moderate: Injury, vehicular accident, watch weather risk
      - Low: Baseline/safe conditions or unclassified situations
    """
    if category in ("electrocution", "snakebite") or risk_level == "critical":
        return "Critical"
    elif category in ("structural_damage", "flooding", "cyclone") or risk_level == "warning":
        return "High"
    elif category in ("injury", "accident") or risk_level == "watch":
        return "Moderate"
    else:
        return "Moderate" if category != "unclassified" else "Low"


# ─────────────────────────────────────────────────────────────────────────────
# Community Context (Section 9.2 — accepted into orchestrator scope)
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_community_insights(description: str, city: str) -> list[CommunityInsight]:
    """Pull relevant community reports and vector-indexed knowledge for the assessment."""
    insights: list[CommunityInsight] = []
    seen_ids: set[str] = set()
    description_lower = description.lower()
    city_lower = city.lower()

    try:
        for report in database_service.list_reports():
            area = (report.get("area") or "").strip()
            message = (report.get("message") or "").strip()
            if not area or not message:
                continue
            area_match = city_lower in area.lower() or area.lower() in city_lower
            text_match = any(
                token in message.lower()
                for token in description_lower.split()
                if len(token) > 4
            )
            if not area_match and not text_match:
                continue
            report_id = str(report["id"])
            if report_id in seen_ids:
                continue
            seen_ids.add(report_id)
            insights.append(
                CommunityInsight(
                    id=report_id,
                    area=area,
                    message=message,
                    verified=bool(report.get("verified")),
                    source="community_report",
                    attachment_url=report.get("attachment_url"),
                    created_at=report.get("created_at"),
                )
            )
    except Exception as exc:
        logger.warning("orchestrator: community report lookup failed: %s", exc)

    try:
        from app.services import knowledge_service

        if knowledge_service.knowledge_available():
            for item in knowledge_service.search_knowledge(description, area=city, limit=3):
                item_id = str(item.get("id") or "")
                if not item_id or item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
                insights.append(
                    CommunityInsight(
                        id=item_id,
                        area=item.get("area") or city,
                        message=item.get("content_text") or item.get("title") or "",
                        verified=False,
                        source="knowledge_asset",
                        attachment_url=item.get("storage_url"),
                        similarity=item.get("similarity"),
                        created_at=item.get("created_at"),
                    )
                )
    except Exception as exc:
        logger.warning("orchestrator: knowledge search failed: %s", exc)

    return insights[:5]


def _build_source_labels(
    triage_res: TriageResult,
    weather_status: str,
    action_plan_source: str,
    maps_status: str,
    community_count: int,
) -> dict[str, str]:
    triage_labels = {1: "deterministic_keyword", 2: "embedding_or_ml", 3: "ai_classification"}
    weather_labels = {
        "available": "live_weather_api",
        "not_requested": "not_used",
    }
    hospital_labels = {
        "available": (
            "supabase_directory"
            if supabase_service.supabase_available
            else "firebase_directory"
        ),
        "not_requested": "location_not_provided",
    }
    action_labels = {
        "groq": "ai_generated",
        "deterministic": "deterministic_fallback",
    }

    return {
        "triage": triage_labels.get(triage_res.tier, "unknown"),
        "weather": weather_labels.get(weather_status, "unavailable"),
        "action_plan": action_labels.get(action_plan_source, "unknown"),
        "hospitals": hospital_labels.get(maps_status, "unavailable"),
        "community": "community_reports" if community_count else "none",
        "shelters": "database",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Core Pipeline Execution
# ─────────────────────────────────────────────────────────────────────────────

async def orchestrate_emergency_assessment(
    description: str,
    city: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    language: str = "English",
    request_sos: bool = False,
    situation: Optional[str] = None,
) -> AssessmentResult:
    """Execute the full, resilient emergency assessment pipeline.

    Coordinates triage, weather, action planning, confidence aggregation,
    hospitals, and optional explicit SOS into a single unified result.
    """
    # ── Stage 1: Request Validation ───────────────────────────────────────────
    validate_assessment_request(description, lat=lat, lon=lon, request_sos=request_sos)
    effective_city = city or settings.default_city

    # ── Stage 2: Authoritative Triage Classification ──────────────────────────
    try:
        triage_res: TriageResult = await triage_service.classify(description)
    except Exception as exc:
        logger.error("orchestrator: Triage classification failed unexpectedly: %s", exc)
        triage_res = TriageResult(
            category="unclassified",
            confidence=0.20,
            tier=3,
            matched_rule_or_example=None,
            explanation="Triage failed unexpectedly; degraded to safe unclassified baseline.",
        )

    # ── Stage 3: Deterministic Weather Risk Assessment ─────────────────────────
    # Use client coordinates if supplied; otherwise fall back to city coordinates
    w_lat = lat if lat is not None else 17.3850
    w_lon = lon if lon is not None else 78.4867

    try:
        weather_res: ServiceResult[WeatherSummary] = await weather_service.get_weather_safe(w_lat, w_lon)
    except Exception as exc:
        logger.warning("orchestrator: get_weather_safe raised %s. Using unavailable.", exc)
        weather_res = ServiceResult(available=False, error_type="server_error")

    if weather_res.available and weather_res.data:
        risk = weather_service.compute_risk_score(weather_res.data)
        weather_dict = {
            "score": risk.score,
            "level": risk.level,
            "condition": weather_res.data.condition,
            "temp_c": weather_res.data.temp_c,
            "rain_mm_last_hour": weather_res.data.rain_mm_last_hour,
            "status": "available",
        }
        weather_status = "available"
    else:
        weather_dict = {
            "score": 18,
            "level": "safe",
            "condition": "Unavailable (baseline fallback)",
            "temp_c": 25.0,
            "rain_mm_last_hour": 0.0,
            "status": weather_res.error_type or "unavailable",
        }
        weather_status = weather_res.error_type or "unavailable"

    # ── Stage 4: Advisory Action Planning ─────────────────────────────────────
    action_context = ActionPlanContext(
        user_description=description,
        triage_category=triage_res.category,
        weather_risk=weather_dict,
        location_context={"city": effective_city, "lat": lat, "lon": lon},
        available_services={
            "weather": weather_res.available,
            "maps": database_service.hospitals_directory_available(),
            "groq": settings.is_groq_available,
        },
        trusted_contacts=DEFAULT_TRUSTED_CONTACTS,
    )

    action_plan, action_plan_source = await action_planner_service.generate_action_plan_with_provenance(action_context)
    if action_plan_source == "groq":
        groq_status = "available"
    elif not settings.is_groq_available:
        groq_status = "disabled"
    else:
        groq_status = "fallback_used"

    # ── Stage 5: Weakest-Link Confidence Aggregation ───────────────────────────
    w_conf = confidence_service.calculate_weather_confidence(weather_res)
    a_conf = confidence_service.calculate_action_plan_confidence(action_plan_source)
    confidence_res: ConfidenceResult = confidence_service.aggregate_confidence_safe(
        triage_confidence=triage_res.confidence,
        weather_confidence=w_conf,
        action_plan_confidence=a_conf,
    )

    # ── Stage 6: Optional Hospital Lookup (Explicit Location Only) ────────────
    hospitals: list[HospitalOut] = []
    if lat is not None and lon is not None:
        try:
            maps_res = await maps_service.get_nearby_hospitals_safe(lat, lon)
            if maps_res.available and maps_res.data:
                hospitals = maps_res.data
                maps_status = "available"
            else:
                hospitals = []
                maps_status = maps_res.error_type or "unavailable"
        except Exception as exc:
            logger.warning("orchestrator: Hospital search raised %s; returning empty list.", exc)
            hospitals = []
            maps_status = "server_error"
    else:
        maps_status = "not_requested"

    # ── Stage 7: Optional Explicit SOS Execution (Step 3 Flow) ────────────────
    sos_res: Optional[SosResponse] = None
    if request_sos and lat is not None and lon is not None:
        maps_link = f"https://maps.google.com/?q={lat},{lon}"
        now = _NOW_ISO()
        initial_data = {
            "latitude": lat,
            "longitude": lon,
            "situation": situation or description,
            "created_at": now,
            "updated_at": now,
            "notification_status": "pending_notification",
            "message_id": None,
            "error_detail": None,
        }

        try:
            event_id = database_service.create_sos_record(initial_data)

            if not database_service.push_available():
                database_service.update_sos_record(
                    event_id,
                    {"notification_status": "notification_disabled", "updated_at": _NOW_ISO()},
                )
                sos_res = SosResponse(
                    event_id=event_id,
                    status="recorded",
                    notification_status="notification_disabled",
                    maps_link=maps_link,
                    message=f"✅ SOS recorded. Push notifications disabled — call 112. Location: {maps_link}",
                )
            else:
                notify_body = situation or description[:100]
                try:
                    message_id = database_service.send_topic_push(
                        title="🚨 ResQ AI — SOS Alert",
                        body=notify_body,
                        data={"lat": str(lat), "lon": str(lon), "maps_link": maps_link, "event_id": event_id},
                    )
                    database_service.update_sos_record(
                        event_id,
                        {"notification_status": "notification_accepted", "message_id": message_id, "updated_at": _NOW_ISO()},
                    )
                    sos_res = SosResponse(
                        event_id=event_id,
                        status="recorded",
                        notification_status="notification_accepted",
                        maps_link=maps_link,
                        message=f"✅ SOS recorded and alert sent to responders. Your location: {maps_link}",
                    )
                except Exception as exc:
                    safe_detail = f"{type(exc).__name__}: notification delivery failed"
                    database_service.update_sos_record(
                        event_id,
                        {"notification_status": "notification_failed", "error_detail": safe_detail, "updated_at": _NOW_ISO()},
                    )
                    sos_res = SosResponse(
                        event_id=event_id,
                        status="recorded",
                        notification_status="notification_failed",
                        maps_link=maps_link,
                        message=f"✅ SOS recorded, but notification failed. Call 112. Location: {maps_link}",
                    )
        except Exception:
            sos_res = SosResponse(
                event_id=None,
                status="degraded",
                notification_status="notification_disabled",
                maps_link=maps_link,
                message="⚠️ Emergency services could not be reached. Call 112 immediately. SOS not recorded.",
            )

    # ── Stage 7b: Community Context (Section 9.2) ────────────────────────────
    community_insights = _fetch_community_insights(description, effective_city)
    community_status = "available" if community_insights else "none"

    # ── Stage 8: Result Assembly ───────────────────────────────────────────────
    emergency_level = determine_emergency_level(triage_res.category, weather_dict.get("level"))
    database_status = "available" if database_service.database_available() else "unavailable"
    push_status = "available" if database_service.push_available() else "unavailable"

    service_status = {
        "weather": weather_status,
        "maps": maps_status,
        "groq": groq_status,
        "database": database_status,
        "firebase": push_status,
        "community": community_status,
    }
    source_labels = _build_source_labels(
        triage_res,
        weather_status,
        action_plan_source,
        maps_status,
        len(community_insights),
    )

    # Format whats_happening for backward compatibility with existing tests/clients
    if action_plan_source == "groq":
        whats_happening = action_plan.explanation
    else:
        whats_happening = f"Live AI assessment service is currently unavailable. {action_plan.explanation}"

    # Build backward-compatible nearby_help representation
    nearby_help = [
        {
            "name": h.name,
            "url": f"https://maps.google.com/?q={h.lat},{h.lon}" if (h.lat and h.lon) else None,
        }
        for h in hospitals
    ]

    standard_items = [
        "Clean drinking water and non-perishable food",
        "Prescribed medications and personal first-aid supplies",
        "Flashlight, whistle, and charged power bank",
        "Government identification documents in a waterproof bag",
    ]

    return AssessmentResult(
        triage=triage_res,
        weather=weather_dict,
        action_plan=action_plan,
        confidence=confidence_res,
        hospitals=hospitals,
        sos=sos_res,
        service_status=service_status,
        community_insights=community_insights,
        source_labels=source_labels,
        emergency_level=emergency_level,
        whats_happening=whats_happening,
        immediate_first_aid=action_plan.immediate_actions,
        what_not_to_do=action_plan.safety_warnings,
        call_these_services=action_plan.emergency_contacts,
        things_to_carry=standard_items,
        nearby_help=nearby_help,
        raw_text=action_plan.explanation,
    )
