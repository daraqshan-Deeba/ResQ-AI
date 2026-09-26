"""Deterministic chat pre-filter: emergencies never go to the LLM."""

from __future__ import annotations

from app.services.safety_net import detect_life_threats

_URGENT_HINTS = (
    "emergency",
    "help me now",
    "need ambulance",
    "call 112",
    "call 108",
    "sos",
    "urgent",
    "bleeding",
    "flood",
    "snake",
    "electrocut",
    "accident",
    "collapse",
)


def emergency_intent_reply(message: str) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    safety = detect_life_threats(text)
    lowered = text.lower()
    hinted = any(h in lowered for h in _URGENT_HINTS)
    if not safety.hits and not hinted:
        return None
    return (
        "This sounds like an emergency. I cannot handle it in chat. "
        "Call 112 or 108 now, or open Get help and describe what is happening. "
        "Use SOS only after you have confirmed it."
    )
