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

import re

import httpx

from app.core.config import settings
from app.models.schemas import AssessmentResponse

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

If you are not confident about a specific number, name, or fact, say so \
plainly rather than inventing it.
"""


async def _call_groq(messages: list[dict], temperature: float = 0.3) -> str:
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.groq_model,
        "messages": messages,
        "temperature": temperature,
        # If your xAI plan/model supports Live Search, add the relevant
        # parameter here — see the module docstring above.
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(GROQ_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]


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
    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION.format(city=city, language=language)},
        {"role": "user", "content": _build_prompt(description, city)},
    ]
    raw_text = await _call_groq(messages, temperature=0.3)
    return parse_response(raw_text)


async def run_chat_reply(history: list[dict], message: str, city: str) -> str:
    """Multi-turn call for the Assistant tab. `history` is a list of
    {"role": "user"|"assistant", "text": "..."} dicts from the frontend."""
    messages = [
        {
            "role": "system",
            "content": (
                f"You are ResQ AI's Responder — a calm monsoon-emergency assistant "
                f"for {city}, India. Keep replies short, concrete, and actionable."
            ),
        }
    ]
    for turn in history:
        role = "user" if turn["role"] == "user" else "assistant"
        messages.append({"role": role, "content": turn["text"]})
    messages.append({"role": "user", "content": message})

    return await _call_groq(messages, temperature=0.4)
