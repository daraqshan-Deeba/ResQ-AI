"""
Emergency Orchestrator Service — Step 7: Unified Emergency Assessment Pipeline

The orchestrator is the single coordination layer that assembles:
  Stage 1 — Request Validation
  Stage 2 — Understand (optional LLM restatement) + retrieve similar incidents + classify
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
from typing import Any, Optional

from app.core.config import settings
from app.models.schemas import (
    ActionPlanContext,
    AssessmentResult,
    CommunityInsight,
    ConfidenceResult,
    HospitalOut,
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
from app.i18n.languages import is_english_reply
from app.services.action_planner_service import DEFAULT_TRUSTED_CONTACTS
from app.services.evidence_map import required_evidence, weather_relevant as weather_is_relevant
from app.services.protocol_service import protocol_key_for
from app.services.safety_net import detect_life_threats
from app.services.severity import determine_emergency_level

logger = logging.getLogger("resq.orchestrator")


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


# Re-exported for tests
__all__ = [
    "validate_assessment_request",
    "determine_emergency_level",
    "orchestrate_emergency_assessment",
]


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

    # ── Stage 2: Authoritative Triage + safety net ────────────────────────────
    safety = detect_life_threats(description)
    try:
        triage_res, nlu_meta = await triage_service.classify_free_text(
            description,
            skip_llm=bool(safety.hits),
        )
    except Exception as exc:
        logger.error("orchestrator: Triage classification failed unexpectedly: %s", exc)
        triage_res = TriageResult(
            category="unclassified",
            confidence=0.20,
            tier=3,
            matched_rule_or_example=None,
            explanation="Triage failed unexpectedly; treated as unknown, not safe.",
        )
        nlu_meta = {"understood_as": None, "nlu_source": "error", "retrieved": []}
    triage_res.safety_hits = list(safety.hits)
    protocol_key = protocol_key_for(
        triage_res.category,
        safety.protocol_key,
        triage_res.matched_rule_or_example,
    )
    evidence_needed = required_evidence(triage_res.category, protocol_key)
    need_weather = weather_is_relevant(triage_res.category, protocol_key)
    has_location = lat is not None and lon is not None

    # ── Stage 3: Weather only when relevant AND location is known ─────────────
    weather_dict: dict | None
    weather_res: ServiceResult[WeatherSummary]
    if not need_weather:
        weather_status = "not_relevant"
        weather_dict = {"status": "not_relevant", "score": None, "level": None, "condition": None, "temp_c": None}
        weather_res = ServiceResult(available=False, error_type="service_disabled")
    elif not has_location:
        weather_status = "not_requested"
        weather_dict = {"status": "not_requested", "score": None, "level": None, "condition": None, "temp_c": None}
        weather_res = ServiceResult(available=False, error_type="service_disabled")
    else:
        try:
            weather_res = await weather_service.get_weather_safe(lat, lon)
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
            weather_status = weather_res.error_type or "unavailable"
            weather_dict = {
                "score": None,
                "level": None,
                "condition": None,
                "temp_c": None,
                "rain_mm_last_hour": None,
                "status": weather_status,
            }

    # ── Stage 4: Protocol-first action planning ───────────────────────────────
    action_weather = weather_dict if weather_status == "available" else None
    action_context = ActionPlanContext(
        user_description=description,
        triage_category=triage_res.category,
        reply_language=language,
        weather_risk=action_weather,
        location_context={"city": effective_city, "lat": lat, "lon": lon},
        available_services={
            "weather": weather_status == "available",
            "maps": database_service.hospitals_directory_available(),
            "groq": settings.is_groq_available,
        },
        trusted_contacts=DEFAULT_TRUSTED_CONTACTS,
    )

    skip_llm = bool(safety.hits)
    action_plan, action_plan_source, groq_status = await action_planner_service.generate_action_plan_with_provenance(
        action_context,
        protocol_key=protocol_key,
        skip_llm=skip_llm,
    )

    # ── Stage 5: Confidence (relevant components only) ────────────────────────
    w_conf = (
        1.0
        if weather_status in {"not_relevant", "not_requested"}
        else confidence_service.calculate_weather_confidence(weather_res)
    )
    a_conf = confidence_service.calculate_action_plan_confidence("deterministic")
    triage_state = {1: "rule_match", 2: "similar_example", 3: "ai_suggestion"}.get(triage_res.tier, "unknown")
    weather_state = {
        "available": "live",
        "not_relevant": "not_relevant",
        "not_requested": "not_requested",
    }.get(weather_status, "unavailable")
    confidence_res: ConfidenceResult = confidence_service.aggregate_confidence_safe(
        triage_confidence=triage_res.confidence,
        weather_confidence=w_conf,
        action_plan_confidence=a_conf,
        weather_relevant=need_weather and has_location,
        triage_state=triage_state,
        weather_state=weather_state,
        guidance_state="protocol_plus_ai" if groq_status == "available" else "standard_protocol",
    )

    # ── Stage 6: Hospitals when required and location present ─────────────────
    hospitals: list[HospitalOut] = []
    if "hospitals" not in evidence_needed:
        maps_status = "not_relevant"
    elif not has_location:
        maps_status = "not_requested"
    else:
        try:
            maps_res = await maps_service.get_nearby_hospitals_safe(lat, lon)
            if maps_res.available and maps_res.data:
                hospitals = maps_res.data
                maps_status = "available"
            else:
                hospitals = []
                maps_status = maps_res.error_type or "search_failed"
        except Exception as exc:
            logger.warning("orchestrator: Hospital search raised %s.", exc)
            hospitals = []
            maps_status = "search_failed"

    # ── Stage 7: Optional Explicit SOS ────────────────────────────────────────
    sos_res: Optional[SosResponse] = None
    if request_sos and lat is not None and lon is not None:
        from app.services.sos_dispatch import dispatch_sos

        sos_res = dispatch_sos(
            lat=lat,
            lon=lon,
            situation=situation or description,
        )

    # ── Stage 7b: Community Context ───────────────────────────────────────────
    community_insights: list[CommunityInsight] = []
    if "reports" in evidence_needed:
        community_insights = _fetch_community_insights(description, effective_city)
    community_status = "available" if community_insights else "none"

    # ── Stage 8: Result Assembly ───────────────────────────────────────────────
    emergency_level = determine_emergency_level(
        triage_res.category,
        weather_dict.get("level") if isinstance(weather_dict.get("level"), str) else None,
        candidate_categories=triage_res.candidate_categories,
        safety_forced_level=safety.forced_level,
        weather_relevant=need_weather and weather_status == "available",
    )
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
    if nlu_meta.get("nlu_source") and nlu_meta["nlu_source"] != "passthrough":
        source_labels["understood"] = str(nlu_meta["nlu_source"])
    if nlu_meta.get("retrieved"):
        source_labels["similar_incidents"] = "retrieved_examples"
    if groq_status == "available":
        source_labels["wording"] = "groq_grounded"

    citations = [
        {
            "source": "models",
            "label": f"{triage_res.category} · tier {triage_res.tier}",
        },
        {"source": "protocol", "label": protocol_key},
    ]
    for hit in (nlu_meta.get("retrieved") or [])[:3]:
        example = str(hit.get("example") or "").strip()
        if example:
            citations.append({"source": "similar_example", "label": example[:160]})
    if groq_status == "available":
        citations.append(
            {
                "source": "groq",
                "label": "Wording only; first-aid lines copied from the cited protocol",
            }
        )
    try:
        from app.services.evidence_tools import maybe_run_llm_evidence_tools

        tool_trace = await maybe_run_llm_evidence_tools(description)
        if tool_trace:
            source_labels["evidence_tools"] = "llm_evidence_only"
    except Exception as exc:
        logger.warning("orchestrator: optional evidence tools skipped: %s", exc)

    whats_happening = action_plan.explanation
    if emergency_level == "Unknown":
        whats_happening = (
            "This situation is not classified as a known hazard type. "
            "Treat it as urgent: call 112 or 108 now. " + whats_happening
        )

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
    evac_keys = {"flooding", "cyclone", "fire", "structural_damage"}
    things_to_carry = standard_items if protocol_key in evac_keys else []

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
        safety_hits=list(safety.hits),
        protocol_key=protocol_key,
        understood_as=nlu_meta.get("understood_as")
        if is_english_reply(language)
        else (action_plan.explanation or nlu_meta.get("understood_as")),
        retrieved_examples=list(nlu_meta.get("retrieved") or []),
        citations=citations,
        emergency_level=emergency_level,
        whats_happening=whats_happening,
        immediate_first_aid=action_plan.immediate_actions,
        what_not_to_do=action_plan.safety_warnings,
        call_these_services=action_plan.emergency_contacts,
        things_to_carry=things_to_carry,
        nearby_help=nearby_help,
        raw_text=action_plan.explanation,
    )
