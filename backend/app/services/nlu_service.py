"""NLU restatement — understand free text. Never sets category or severity."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import settings
from app.services.groq_service import call_groq_safe

logger = logging.getLogger("resq.nlu")

_FORBIDDEN_KEYS = {
    "category",
    "severity",
    "emergency_level",
    "level",
    "protocol",
    "sos",
    "confidence",
    "tier",
}

_SYSTEM = """You restate emergency descriptions for a safety system.
Return JSON only: {"canonical": string, "active_now": boolean, "facts": string[]}
canonical: one or two plain sentences in English describing what is happening now
(even if the user wrote in Hindi, Telugu, Tamil, or another supported language).
If the event is only historical, set active_now false and keep that in canonical.
facts: short phrases such as "fell", "sprained leg", "cannot walk".
Do NOT output category, severity, protocol, SOS, confidence, or advice.
Do NOT invent injuries that the user did not mention."""


def parse_nlu_payload(raw: str | None) -> dict[str, Any] | None:
    if not raw or not str(raw).strip():
        return None
    text = str(raw).strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        text = text[start : end + 1]
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if any(key in payload for key in _FORBIDDEN_KEYS):
        logger.info("NLU payload dropped: contained a forbidden decision field.")
        return None
    canonical = str(payload.get("canonical") or "").strip()
    if not canonical:
        return None
    facts = payload.get("facts") if isinstance(payload.get("facts"), list) else []
    return {
        "canonical": canonical[:500],
        "active_now": bool(payload.get("active_now", True)),
        "facts": [str(item)[:80] for item in facts[:12]],
        "source": "llm_restatement",
    }


async def understand_utterance(description: str) -> dict[str, Any]:
    fallback = {
        "canonical": (description or "").strip()[:500],
        "active_now": True,
        "facts": [],
        "source": "passthrough",
    }
    if not description or not description.strip():
        return fallback
    if not settings.nlu_understand_enabled or not settings.is_groq_available:
        return fallback

    result = await call_groq_safe(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": description[:1500]},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
        max_tokens=220,
    )
    if not result.available:
        return fallback
    parsed = parse_nlu_payload(result.data)
    return parsed or fallback
