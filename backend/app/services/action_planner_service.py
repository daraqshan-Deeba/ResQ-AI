"""
Action Planner Service — Step 5: Structured LLM Action Planning

Responsibilities:
  1. Receive trusted structured context (ActionPlanContext).
  2. Construct the constrained Groq prompt requesting strict JSON.
  3. Call call_groq_safe() with response_format={"type": "json_object"}.
  4. Parse and validate JSON into an ActionPlan model.
  5. Enforce deterministic boundaries:
     - The LLM has ZERO severity / emergency_level authority.
     - The LLM cannot overwrite triage category or weather risk.
     - The LLM cannot invent URLs or hospital recommendations.
     - Emergency contacts are strictly restricted to trusted application-provided numbers.
  6. Return a deterministic, category-specific fallback ActionPlan on ANY failure.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

from app.models.schemas import (
    ActionPlan,
    ActionPlanContext,
    ActionPlanSource,
    EmergencyCategory,
)
from app.services.groq_service import call_groq_safe

logger = logging.getLogger("resq.action_planner")

# ─────────────────────────────────────────────────────────────────────────────
# Trusted Emergency Contacts — Single Source of Truth for India
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_TRUSTED_CONTACTS: list[str] = [
    "National Emergency Response: 112",
    "Emergency Medical / Ambulance: 108",
    "Disaster Management Helpline: 1070",
]

# ─────────────────────────────────────────────────────────────────────────────
# Deterministic Fallback Action Plans (Step 5 - Section 8)
# ─────────────────────────────────────────────────────────────────────────────
_FALLBACK_PLANS: dict[EmergencyCategory, dict] = {
    "flooding": {
        "immediate_actions": [
            "Move to higher ground immediately if water is rising around your location.",
            "Avoid walking, swimming, or driving through floodwater.",
            "Turn off the main electrical breaker if safe to reach before water touches it.",
            "Signal for assistance from a visible, elevated position if trapped.",
        ],
        "safety_warnings": [
            "Do not touch submerged electrical appliances, sockets, or fallen wires.",
            "Do not drive into flooded roads or underpasses; moving water can sweep vehicles away.",
            "Avoid drinking tap water in flood zones until declared safe.",
        ],
        "when_to_seek_help": [
            "Water is entering living areas and you cannot safely evacuate.",
            "Vulnerable individuals (elderly, children, injured) are trapped or cut off.",
            "Floodwaters continue to rise rapidly with no higher ground accessible.",
        ],
        "questions_to_ask_user": [
            "Are you currently on an upper floor or elevated safe ground?",
            "Is the water level continuing to rise inside your structure?",
        ],
        "explanation": "Deterministic flood response protocol prioritizing vertical evacuation, electrical isolation, and rescue signaling.",
    },
    "electrocution": {
        "immediate_actions": [
            "Do not touch the victim while electrical current may still be live.",
            "Switch off the main power source or circuit breaker immediately if safely accessible.",
            "Use a dry, non-conductive object (wooden stick, plastic broom) to separate the person if the switch cannot be reached.",
            "Call 108 (Ambulance) and 112 immediately.",
        ],
        "safety_warnings": [
            "Never step into standing water near fallen power lines or exposed wiring.",
            "Do not touch the person with bare hands or wet materials while contact persists.",
            "Do not attempt to move high-voltage power lines yourself.",
        ],
        "when_to_seek_help": [
            "Any electrical shock, loss of consciousness, burns, or difficulty breathing requires emergency medical evaluation.",
            "Fallen power lines in public or residential areas must be reported to 112 and the power utility immediately.",
        ],
        "questions_to_ask_user": [
            "Has the electrical power source been completely disconnected?",
            "Is the victim breathing, conscious, and responsive?",
        ],
        "explanation": "Deterministic electrical hazard protocol prioritizing rescuer safety, power isolation, and immediate emergency medical dispatch.",
    },
    "injury": {
        "immediate_actions": [
            "Apply firm, continuous pressure to bleeding wounds using a clean cloth or sterile dressing.",
            "Keep the injured person lying down, warm, and calm.",
            "Immobilize injured limbs in the position found; do not attempt to straighten broken bones.",
            "Call 108 (Ambulance) for emergency medical assistance.",
        ],
        "safety_warnings": [
            "Do not move the injured person unnecessarily if neck, spinal, or severe trauma is suspected.",
            "Do not remove deeply embedded objects from wounds; stabilize them in place with dressings.",
            "Do not give food or drink to an unconscious or severely injured person.",
        ],
        "when_to_seek_help": [
            "Arterial or spurting bleeding that does not stop after 10 minutes of direct pressure.",
            "Victim is unconscious, disoriented, or having difficulty breathing.",
            "Suspected fracture, spinal injury, or severe head trauma.",
        ],
        "questions_to_ask_user": [
            "Is the injured person conscious, breathing, and able to respond?",
            "Is bleeding controlled or continuing despite continuous pressure?",
        ],
        "explanation": "Deterministic trauma first-aid protocol emphasizing hemorrhage control, spinal immobilization, and urgent medical escalation.",
    },
    "snakebite": {
        "immediate_actions": [
            "Keep the person completely still and calm to slow the spread of venom.",
            "Immobilize the bitten limb at or slightly below heart level.",
            "Remove rings, tight bracelets, and restrictive clothing before swelling begins.",
            "Arrange immediate transport to the nearest hospital with antivenom.",
        ],
        "safety_warnings": [
            "Do NOT cut, slash, or incise the bite wound.",
            "Do NOT attempt to suck out the venom by mouth or mechanical pump.",
            "Do NOT apply an arterial tourniquet, ice pack, or chemical remedies.",
            "Do NOT attempt to capture or kill the snake; note its description or photograph from a safe distance only.",
        ],
        "when_to_seek_help": [
            "All snakebites require urgent medical evaluation at a hospital equipped with anti-snake venom (ASV).",
            "Seek immediate help if swelling spreads, breathing becomes labored, or vision blurs.",
        ],
        "questions_to_ask_user": [
            "Approximately how long ago did the snakebite occur?",
            "Are you experiencing spreading swelling, severe pain, or difficulty swallowing/breathing?",
        ],
        "explanation": "Deterministic snakebite protocol strictly prohibiting harmful folk interventions and prioritizing rapid immobilization and hospital antivenom access.",
    },
    "cyclone": {
        "immediate_actions": [
            "Remain inside a sturdy, permanent (pucca) structure away from exterior walls.",
            "Stay away from glass windows, skylights, and unreinforced roofs.",
            "Unplug electrical appliances to protect against power surges and lightning.",
            "Keep emergency battery lights, water, and identity documents packed and accessible.",
        ],
        "safety_warnings": [
            "Do not venture outside during the 'eye' of the storm; extreme winds will resume abruptly from the opposite direction.",
            "Stay clear of tin roofs, loose signboards, tall trees, and electrical poles.",
            "Avoid driving on coastal roads or low-lying causeways subject to storm surge.",
        ],
        "when_to_seek_help": [
            "Structural components of your shelter begin failing or roof sheets tear off.",
            "Storm surge or floodwater begins inundating your shelter location.",
        ],
        "questions_to_ask_user": [
            "Are you currently sheltering in a concrete (pucca) building?",
            "Is your location under an active coastal evacuation order?",
        ],
        "explanation": "Deterministic cyclone safety protocol prioritizing interior sheltering, storm eye awareness, and wind/surge avoidance.",
    },
    "structural_damage": {
        "immediate_actions": [
            "Evacuate the damaged structure immediately if safe escape routes exist.",
            "Move to an open space clear of exterior walls, overhead cornices, and falling debris.",
            "If trapped under rubble, tap rhythmically on a pipe or wall to signal rescuers rather than shouting continuously.",
            "Call 112 and Disaster Management (1070) immediately.",
        ],
        "safety_warnings": [
            "Do not re-enter a damaged, cracked, or tilted building under any circumstances.",
            "Do not use elevators; use stairwells cautiously after checking for integrity.",
            "Do not ignite matches, lighters, or open flames due to potential ruptured gas lines.",
        ],
        "when_to_seek_help": [
            "Anyone is trapped under collapsed debris or unaccounted for.",
            "Building shows widening cracks, sagging floors, or loud structural creaking.",
        ],
        "questions_to_ask_user": [
            "Is anyone trapped, injured, or unaccounted for inside the building?",
            "Are you currently clear of the exterior collapse impact zone?",
        ],
        "explanation": "Deterministic structural collapse plan focusing on rapid evacuation, perimeter safety, and trapped-person location signaling.",
    },
    "accident": {
        "immediate_actions": [
            "Move to a safe roadside position away from oncoming traffic if physically able.",
            "Activate vehicle hazard lights and place warning triangles if safe to do so.",
            "Check all involved persons for responsiveness, breathing, and major bleeding.",
            "Call 108 (Ambulance) and 112 (Emergency / Police) immediately.",
        ],
        "safety_warnings": [
            "Do not move severely injured or unconscious victims unless there is immediate danger of fire or explosion.",
            "Do not stand in active traffic lanes to photograph or inspect vehicle damage.",
            "Do not remove motorcycle helmets from injured riders unless airway is blocked.",
        ],
        "when_to_seek_help": [
            "Any severe collision, head injury, loss of consciousness, or trapped vehicle occupant requires emergency response.",
            "Fuel spills, smoke, or fire risk at the collision scene require immediate fire and police dispatch.",
        ],
        "questions_to_ask_user": [
            "Are any vehicles on fire or actively leaking fuel?",
            "How many individuals require emergency medical attention?",
        ],
        "explanation": "Deterministic vehicular incident protocol focusing on secondary crash prevention, spinal protection, and rapid multi-service dispatch.",
    },
    "unclassified": {
        "immediate_actions": [
            "Move yourself and others to a secure location away from immediate danger.",
            "Call 112 (National Emergency) or 108 (Medical Ambulance) if urgent assistance is required.",
            "Provide the dispatcher with your exact location and clearly describe what is happening.",
            "Stay calm and monitor local emergency broadcast instructions.",
        ],
        "safety_warnings": [
            "Do not enter unknown hazardous zones without verified information or emergency personnel.",
            "Avoid sharing unverified rumors or speculation on emergency channels.",
        ],
        "when_to_seek_help": [
            "Seek emergency help immediately if there is danger to life, severe injury, or structural threat.",
        ],
        "questions_to_ask_user": [
            "Can you describe the primary danger or hazard you are facing?",
            "Are you or anyone near you currently injured, trapped, or in direct danger?",
        ],
        "explanation": "Deterministic baseline safety guidance providing foundational safety actions and direct emergency contact access.",
    },
}


def get_fallback_action_plan(
    category: EmergencyCategory,
    trusted_contacts: Optional[list[str]] = None,
) -> ActionPlan:
    """Return a deterministic, fully validated fallback ActionPlan for a category."""
    contacts = trusted_contacts if trusted_contacts else DEFAULT_TRUSTED_CONTACTS
    plan_dict = _FALLBACK_PLANS.get(category, _FALLBACK_PLANS["unclassified"]).copy()
    plan_dict["emergency_contacts"] = list(contacts)
    return ActionPlan.model_validate(plan_dict)


# ─────────────────────────────────────────────────────────────────────────────
# Prompt Engineering for Structured JSON Action Planning
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are ResQ AI's Action-Planning Assistant.
Your sole job is to produce a concrete, actionable safety action plan in strict JSON format.

CRITICAL ARCHITECTURAL RULES:
1. Return ONLY valid JSON matching this exact structure:
{{
  "immediate_actions": ["<step 1>", "<step 2>", ...],
  "safety_warnings": ["<warning 1>", "<warning 2>", ...],
  "when_to_seek_help": ["<trigger 1>", ...],
  "questions_to_ask_user": ["<clarifying question 1>", ...],
  "emergency_contacts": ["<trusted contact 1>", ...],
  "explanation": "<concise rationale for recommended actions>"
}}
2. Output NO markdown formatting (do NOT use ```json or ```). Return pure JSON only.
3. Output NO conversational commentary, no preamble, and no postscript.
4. Do NOT determine emergency severity, emergency level, risk level, or urgency.
5. Do NOT invent weather conditions, medical diagnoses, or flood depths.
6. Do NOT recommend or fabricate hospital names, clinic addresses, map links, or URLs.
7. Do NOT invent phone numbers. The emergency_contacts field must ONLY contain contacts from the provided trusted contacts list: {trusted_contacts_str}.
8. Each action string must be practical, direct, and under 300 characters.
9. The explanation must be concise and under 500 characters.
"""


def _build_user_prompt(context: ActionPlanContext) -> str:
    weather_info = "Not provided"
    if context.weather_risk:
        weather_info = (
            f"Score: {context.weather_risk.get('score')}, "
            f"Level: {context.weather_risk.get('level')}"
        )

    location_info = "India (general)"
    if context.location_context:
        city = context.location_context.get("city")
        lat = context.location_context.get("lat")
        lon = context.location_context.get("lon")
        location_info = f"City: {city}, Lat: {lat}, Lon: {lon}"

    trusted_contacts_list = context.trusted_contacts or DEFAULT_TRUSTED_CONTACTS
    contacts_str = "; ".join(trusted_contacts_list)

    return (
        f"EMERGENCY CONTEXT:\n"
        f"- Triage Category: {context.triage_category}\n"
        f"- User Description: {context.user_description}\n"
        f"- Location: {location_info}\n"
        f"- Weather Risk Reference: {weather_info}\n"
        f"- Trusted Emergency Helplines: {contacts_str}\n\n"
        f"Generate the structured action plan JSON for this situation."
    )


# ─────────────────────────────────────────────────────────────────────────────
# JSON Parsing and Validation
# ─────────────────────────────────────────────────────────────────────────────

def _sanitize_emergency_contacts(
    contacts: list[str],
    trusted_contacts: list[str],
) -> list[str]:
    """Ensure emergency_contacts contains only numbers from the trusted contacts list."""
    trusted_nums: set[str] = {
        num for tc in trusted_contacts for num in re.findall(r"\b\d+\b", tc)
    }
    # Keep only contacts containing a trusted phone number
    sanitized = [c for c in contacts if any(num in c for num in trusted_nums)]
    return sanitized if sanitized else list(trusted_contacts)


def parse_action_plan_json(
    raw_text: str,
    trusted_contacts: list[str],
) -> ActionPlan:
    """Parse, unwrap markdown if present, and validate raw LLM JSON output into ActionPlan.

    Raises ValueError or ValidationError if invalid.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Empty response received from LLM")

    text = raw_text.strip()

    # Safely strip markdown code block fences if present (e.g. ```json ... ```)
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    # Locate outermost JSON object braces
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in response")

    json_str = text[start : end + 1]
    data = json.loads(json_str)

    if not isinstance(data, dict):
        raise ValueError("Parsed JSON root is not a dictionary")

    # Validate against Pydantic schema
    plan = ActionPlan.model_validate(data)

    # Sanitize emergency contacts against trusted numbers
    plan.emergency_contacts = _sanitize_emergency_contacts(
        plan.emergency_contacts, trusted_contacts
    )

    return plan


# ─────────────────────────────────────────────────────────────────────────────
# Main Public Interface
# ─────────────────────────────────────────────────────────────────────────────

async def generate_action_plan_with_provenance(
    context: ActionPlanContext,
) -> tuple[ActionPlan, ActionPlanSource]:
    """Generate a strictly validated emergency action plan with explicit provenance.

    Returns:
        tuple of (ActionPlan, ActionPlanSource) where source is either:
        - "groq": plan was generated by Groq and passed full Pydantic validation
        - "deterministic": safe fallback plan returned due to failure/absence of LLM
    """
    trusted_contacts = context.trusted_contacts or DEFAULT_TRUSTED_CONTACTS
    fallback = get_fallback_action_plan(context.triage_category, trusted_contacts)

    system_content = SYSTEM_PROMPT.format(
        trusted_contacts_str="; ".join(trusted_contacts)
    )
    user_content = _build_user_prompt(context)

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]

    try:
        # Request JSON mode from Groq
        result = await call_groq_safe(
            messages=messages,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.warning(
            "generate_action_plan: call_groq_safe raised %s. Returning fallback.",
            type(exc).__name__,
        )
        return fallback, "deterministic"

    if not result.available or not result.data:
        logger.info(
            "generate_action_plan: Groq unavailable (%s: %s). Returning deterministic fallback for '%s'.",
            result.error_type,
            result.detail,
            context.triage_category,
        )
        return fallback, "deterministic"

    try:
        plan = parse_action_plan_json(result.data, trusted_contacts)
        logger.debug(
            "generate_action_plan: Successfully generated and validated action plan for category '%s'.",
            context.triage_category,
        )
        return plan, "groq"
    except Exception as exc:
        logger.warning(
            "generate_action_plan: Failed to parse/validate LLM output (%s). Returning deterministic fallback.",
            exc,
        )
        return fallback, "deterministic"


async def generate_action_plan(context: ActionPlanContext) -> ActionPlan:
    """Generate a strictly validated emergency action plan (backward-compatible convenience wrapper)."""
    plan, _ = await generate_action_plan_with_provenance(context)
    return plan

