"""Protocol-first action planning. LLM may only add clarifying questions."""

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
from app.services.protocol_service import default_contacts, get_protocol_plan, protocol_key_for

logger = logging.getLogger("resq.action_planner")

DEFAULT_TRUSTED_CONTACTS: list[str] = default_contacts()

_BANNED_GUIDANCE = re.compile(
    r"\b(tourniquet|suck (out )?the venom|cut (the )?(bite|wound)|give brandy|kerosene|incise the)\b",
    re.I,
)
_PHONE_TOKEN = re.compile(r"\b\d{3,}\b")
_TRUSTED_NUMBERS = frozenset({"112", "108", "1070"})


def get_fallback_action_plan(
    category: EmergencyCategory | str,
    trusted_contacts: Optional[list[str]] = None,
    *,
    protocol_key: str | None = None,
) -> ActionPlan:
    key = protocol_key or protocol_key_for(str(category), None)
    return get_protocol_plan(key, trusted_contacts or DEFAULT_TRUSTED_CONTACTS)


SYSTEM_PROMPT = """You are ResQ AI's question assistant.
Return ONLY JSON:
{{
  "questions_to_ask_user": ["<short question>", "..."]
}}
Rules:
- Do NOT give first-aid steps, phone numbers, URLs, or hospital names.
- At most 3 questions. Each under 200 characters.
- Questions must change the next action if answered.
"""


def _build_user_prompt(context: ActionPlanContext) -> str:
    return (
        f"Triage category: {context.triage_category}\n"
        f"User description: {context.user_description}\n"
        "Suggest clarifying questions only."
    )


def _text_is_safe(text: str) -> bool:
    if _BANNED_GUIDANCE.search(text):
        return False
    for token in _PHONE_TOKEN.findall(text):
        if token not in _TRUSTED_NUMBERS:
            return False
    return True


def _sanitize_emergency_contacts(
    contacts: list[str],
    trusted_contacts: list[str],
) -> list[str]:
    """Keep contacts only if every digit token is an exact trusted helpline."""
    sanitized: list[str] = []
    for contact in contacts:
        nums = _PHONE_TOKEN.findall(contact)
        if nums and all(num in _TRUSTED_NUMBERS for num in nums):
            sanitized.append(contact)
    return sanitized if sanitized else list(trusted_contacts)


def parse_action_plan_json(
    raw_text: str,
    trusted_contacts: list[str],
) -> ActionPlan:
    if not raw_text or not raw_text.strip():
        raise ValueError("Empty response received from LLM")

    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in response")

    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("Parsed JSON root is not a dictionary")

    plan = ActionPlan.model_validate(data)
    plan.emergency_contacts = _sanitize_emergency_contacts(
        plan.emergency_contacts, trusted_contacts
    )
    blob = " ".join(
        plan.immediate_actions
        + plan.safety_warnings
        + plan.when_to_seek_help
        + plan.questions_to_ask_user
        + [plan.explanation]
    )
    if not _text_is_safe(blob):
        raise ValueError("LLM plan failed safety content gate")
    return plan


async def generate_action_plan_with_provenance(
    context: ActionPlanContext,
    *,
    protocol_key: str | None = None,
    skip_llm: bool = False,
) -> tuple[ActionPlan, ActionPlanSource, str]:
    trusted_contacts = context.trusted_contacts or DEFAULT_TRUSTED_CONTACTS
    key = protocol_key or protocol_key_for(context.triage_category, None)
    protocol = get_protocol_plan(key, trusted_contacts)

    if skip_llm:
        return protocol, "deterministic", "not_needed"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_prompt(context)},
    ]

    try:
        result = await call_groq_safe(
            messages=messages,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.warning("generate_action_plan: call_groq_safe raised %s.", type(exc).__name__)
        return protocol, "deterministic", "fallback_used"

    if not result.available or not result.data:
        groq_status = "disabled" if result.error_type == "service_disabled" else "fallback_used"
        return protocol, "deterministic", groq_status

    groq_status = "available"
    try:
        payload = json.loads(result.data) if result.data.strip().startswith("{") else None
        if payload is None:
            text = result.data.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
                text = re.sub(r"\s*```$", "", text)
            start, end = text.find("{"), text.rfind("}")
            payload = json.loads(text[start : end + 1])
        questions = payload.get("questions_to_ask_user") if isinstance(payload, dict) else None
        if isinstance(questions, list):
            clean = [
                q.strip()
                for q in questions
                if isinstance(q, str) and q.strip() and _text_is_safe(q) and len(q) <= 200
            ][:3]
            if clean:
                protocol.questions_to_ask_user = clean
    except Exception as exc:
        logger.warning("Ignoring LLM enrichment (%s).", exc)

    return protocol, "deterministic", groq_status


async def generate_action_plan(context: ActionPlanContext) -> ActionPlan:
    plan, _, _ = await generate_action_plan_with_provenance(context)
    return plan
