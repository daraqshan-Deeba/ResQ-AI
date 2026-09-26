"""
Responder agent — same structured output as before (EMERGENCY LEVEL /
WHAT'S HAPPENING / FIRST AID / etc.), now calling Grok (xAI) instead of
Gemini. Grok's API is OpenAI-compatible, so this is a plain chat-completions
call via httpx — no extra SDK needed.

Note: unlike the earlier Gemini version, this does NOT include live web-search
grounding by default. xAI has offered a "Live Search" feature on some plans/
models, but the exact request shape changes over time — check
https://docs.x.ai for whether your model/plan supports it, then add the
relevant parameter to the payload in `_call_grok()` below if so. Without it,
the NEARBY HELP section will be based on the model's training data, not a
live lookup, so treat those links as a starting point to verify, not gospel.
"""

import logging
import re
from typing import Optional

import httpx

from app.core.config import settings
from app.models.schemas import AssessmentResponse, ServiceResult

logger = logging.getLogger("resq.groq")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_INSTRUCTION = """You are ResQ AI's Responder agent, a calm and precise \
monsoon-emergency assistant for people in and around {city}, India. \
Always reply in {language}. Use ONLY the section headers below, in this exact \
order, each on its own line, followed by content. Do not add extra commentary \
outside these sections.

EMERGENCY LEVEL: <one of Critical, High, Moderate, Low>
WHAT'S HAPPENING: <one or two sentence plain-language summary of the situation>
IMMEDIATE FIRST AID:
1. ...
2. ...
WHAT NOT TO DO:
1. ...
2. ...
CALL THESE SERVICES: <comma-separated list, e.g. Ambulance 108, Disaster Helpline 112>
THINGS TO CARRY:
1. ...
2. ...
NEARBY HELP:
- <name> (<url or "no live lookup available">)
- <name> (<url or "no live lookup available">)

Note: run_assessment() is a leftover isolated helper. The production pipeline is
emergency_orchestrator (deterministic severity + protocol). Do not wire this
module back into /api/assessment.
"""

STATIC_FALLBACK_ASSESSMENT = AssessmentResponse(
    emergency_level="Moderate",
    whats_happening="Live AI assessment service is currently unavailable. General emergency guidance is provided below.",
    immediate_first_aid=[
        "Move to higher ground if in a flood-prone or waterlogged area.",
        "Stay clear of fallen power lines, electric poles, and flooded basements.",
        "If anyone is injured, keep them warm, calm, and apply clean pressure to wounds.",
    ],
    what_not_to_do=[
        "Do not attempt to walk or drive through flowing floodwaters.",
        "Do not touch electrical switches, cords, or appliances while wet or standing in water.",
    ],
    call_these_services=[
        "National Emergency Response: 112",
        "Emergency Medical Ambulance: 108",
        "Disaster Management Helpline: 1070",
    ],
    things_to_carry=[
        "Clean drinking water and non-perishable food",
        "Essential prescribed medications",
        "Flashlight, whistle, and mobile power bank",
        "Important identity documents in a sealed waterproof bag",
    ],
    nearby_help=[],
    raw_text="[Fallback Guidance: Live AI responder is currently offline.]",
)


async def call_groq_safe(
    messages: list[dict],
    temperature: float = 0.3,
    response_format: Optional[dict] = None,
    tools: Optional[list] = None,
) -> ServiceResult[str]:
    api_key = settings.groq_api_key
    if not api_key or not api_key.strip():
        logger.info("Groq API key not configured; AI service disabled.")
        return ServiceResult(
            available=False,
            error_type="service_disabled",
            detail="Groq AI service is disabled or API key is not configured.",
        )

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }
    payload: dict = {
        "model": settings.groq_model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        payload["response_format"] = response_format
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(GROQ_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return ServiceResult(available=True, data=content)

    except httpx.TimeoutException:
        logger.warning("Timeout while connecting to Groq API.")
        return ServiceResult(
            available=False,
            error_type="timeout",
            detail="AI service request timed out.",
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        logger.warning(
            "Groq API returned HTTP %s for model '%s'.",
            status,
            settings.groq_model,
        )
        if status in (401, 403):
            error_type = "auth_error"
            detail = "AI service authorization error."
        elif status == 404:
            error_type = "not_found"
            detail = "AI model or endpoint not found."
        elif status == 429:
            error_type = "rate_limited"
            detail = "AI service rate limit exceeded. Please try again shortly."
        elif status == 504:
            error_type = "timeout"
            detail = "AI service gateway timed out."
        elif status in (500, 502, 503):
            error_type = "server_error"
            detail = "AI service is temporarily unavailable."
        else:
            error_type = "server_error"
            detail = f"AI service responded with status {status}."
        return ServiceResult(available=False, error_type=error_type, detail=detail)
    except httpx.RequestError as exc:
        logger.warning("Network error connecting to Groq API: %s", type(exc).__name__)
        return ServiceResult(
            available=False,
            error_type="network_error",
            detail="Network error while connecting to AI service.",
        )
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        logger.error("Failed to parse Groq API response: %s", exc)
        return ServiceResult(
            available=False,
            error_type="parse_error",
            detail="Malformed response received from AI service.",
        )
    except Exception as exc:
        logger.error("Unexpected error in Groq service: %s", type(exc).__name__)
        return ServiceResult(
            available=False,
            error_type="server_error",
            detail="An unexpected error occurred in AI service.",
        )


async def _call_groq(messages: list[dict], temperature: float = 0.3) -> str:
    """Legacy helper preserved for backward compatibility."""
    res = await call_groq_safe(messages, temperature=temperature)
    return res.data or ""


def _build_prompt(description: str, city: str) -> str:
    return f"Situation reported: {description}\nLocation: {city}"


def _extract_section(text: str, header: str, next_headers: list[str]) -> str:
    pattern = rf"{re.escape(header)}:?\s*(.*?)(?=(?:{'|'.join(map(re.escape, next_headers))})|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _extract_list(block: str) -> list[str]:
    items = re.findall(r"^\s*(?:\d+\.|-)\s*(.+)$", block, re.MULTILINE)
    return [i.strip() for i in items if i.strip()] or ([block.strip()] if block.strip() else [])


def _extract_nearby_help(block: str) -> list[dict]:
    results = []
    for line in block.splitlines():
        m = re.match(r"^\s*-\s*(.+?)\s*\((https?://[^\s)]+)\)", line.strip())
        if m:
            results.append({"name": m.group(1), "url": m.group(2)})
        elif line.strip().startswith("-"):
            results.append({"name": line.strip("- ").strip(), "url": None})
    return results


HEADERS = [
    "EMERGENCY LEVEL",
    "WHAT'S HAPPENING",
    "IMMEDIATE FIRST AID",
    "WHAT NOT TO DO",
    "CALL THESE SERVICES",
    "THINGS TO CARRY",
    "NEARBY HELP",
]


def parse_response(raw_text: str) -> AssessmentResponse:
    def others(current: str) -> list[str]:
        return [h for h in HEADERS if h != current]

    level = _extract_section(raw_text, "EMERGENCY LEVEL", others("EMERGENCY LEVEL")) or "Unknown"
    whats_happening = _extract_section(raw_text, "WHAT'S HAPPENING", others("WHAT'S HAPPENING"))
    first_aid = _extract_list(_extract_section(raw_text, "IMMEDIATE FIRST AID", others("IMMEDIATE FIRST AID")))
    not_to_do = _extract_list(_extract_section(raw_text, "WHAT NOT TO DO", others("WHAT NOT TO DO")))
    services_raw = _extract_section(raw_text, "CALL THESE SERVICES", others("CALL THESE SERVICES"))
    services = [s.strip() for s in services_raw.split(",") if s.strip()]
    carry = _extract_list(_extract_section(raw_text, "THINGS TO CARRY", others("THINGS TO CARRY")))
    nearby = _extract_nearby_help(_extract_section(raw_text, "NEARBY HELP", others("NEARBY HELP")))

    return AssessmentResponse(
        emergency_level=level,
        whats_happening=whats_happening,
        immediate_first_aid=first_aid,
        what_not_to_do=not_to_do,
        call_these_services=services,
        things_to_carry=carry,
        nearby_help=nearby,
        raw_text=raw_text,
    )


async def run_assessment(description: str, city: str, language: str = "English") -> AssessmentResponse:
    """Isolated legacy Groq assessment. Not used by the orchestrator or /api/assessment."""
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION.format(city=city, language=language)},
        {"role": "user", "content": _build_prompt(description, city)},
    ]
    res = await call_groq_safe(messages, temperature=0.3)
    if not res.available or not res.data:
        logger.warning(
            "run_assessment: Groq unavailable (%s: %s). Using static emergency fallback.",
            res.error_type,
            res.detail,
        )
        return STATIC_FALLBACK_ASSESSMENT

    try:
        return parse_response(res.data)
    except Exception as exc:
        logger.error("Failed to parse Groq response: %s", exc)
        return STATIC_FALLBACK_ASSESSMENT


async def run_chat_reply(
    history: list[dict],
    message: str,
    city: str,
    memory_context: str | None = None,
) -> str:
    """Multi-turn call for the Assistant tab."""
    if not settings.groq_api_key or not settings.groq_api_key.strip():
        return (
            "⚠️ The AI Assistant is currently disabled. "
            "For emergency assistance in India, call 112 (National Emergency) or 108 (Ambulance)."
        )

    system_parts = [
        "You are ResQ AI's general information assistant — NOT the primary emergency "
        "assessment system. Keep replies short and factual. Do not assign emergency "
        "severity levels or replace professional emergency services.",
        f"For urgent or life-threatening situations, always direct the user to the "
        f"structured Emergency Assessment flow and to call 112 / 108 immediately.",
        f"You may answer general monsoon-safety questions for {city}, India.",
    ]
    if memory_context:
        system_parts.append(memory_context)

    messages = [{"role": "system", "content": "\n\n".join(system_parts)}]
    for turn in history:
        role = "user" if turn["role"] == "user" else "assistant"
        messages.append({"role": role, "content": turn["text"]})
    messages.append({"role": "user", "content": message})

    res = await call_groq_safe(messages, temperature=0.4)
    if not res.available or not res.data:
        return (
            "⚠️ The AI Assistant is temporarily unavailable. "
            "For emergency help, please contact 112 (National Emergency) or 108 (Ambulance)."
        )
    return res.data
