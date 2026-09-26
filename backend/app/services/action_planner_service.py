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
from app.i18n.languages import groq_language_phrase, is_english_reply
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


SYSTEM_PROMPT = """You write the user-facing words for ResQ AI after models have already classified the case.
Return ONLY JSON:
{{
  "headline": "<summary of THIS user's situation, max 180 characters, MUST be in the reply language>",
  "questions_to_ask_user": ["<short question in the reply language>", "..."],
  "selected_actions": ["<exact English copy from PROTOCOL immediate_actions>", "..."],
  "selected_warnings": ["<exact English copy from PROTOCOL safety_warnings>", "..."],
  "translated_actions": ["<same order as selected_actions, translated into the reply language>"],
  "translated_warnings": ["<same order as selected_warnings, translated into the reply language>"],
  "translated_seek_help": ["<each PROTOCOL when_to_seek_help line, same order, translated>"]
}}
Reply language: {language}
Rules:
- Category, tier, and severity are already decided. Do not change them.
- selected_actions and selected_warnings MUST be exact English copies from PROTOCOL. Do not invent procedures.
- Pick the protocol lines that fit this description (for example a slip and sore knee is not a spinal trauma speech).
- headline and questions MUST be in the reply language. If the reply language is not English, do not write them in English.
- translated_* must keep the same meaning and keep numbers 112, 108, 1070 unchanged.
- Do NOT include SOS commands, URLs, hospital names, or phone numbers other than 112/108/1070 if they already appear in PROTOCOL.
- At most 3 questions, each under 200 characters.
"""


def _build_user_prompt(context: ActionPlanContext, protocol: ActionPlan, protocol_key: str) -> str:
    return (
        f"User description: {context.user_description}\n"
        f"Authoritative category: {context.triage_category}\n"
        f"Protocol key: {protocol_key}\n"
        f"Language: {groq_language_phrase(context.reply_language)}\n"
        "PROTOCOL immediate_actions:\n"
        + "\n".join(f"- {step}" for step in protocol.immediate_actions)
        + "\nPROTOCOL safety_warnings:\n"
        + "\n".join(f"- {step}" for step in protocol.safety_warnings)
        + "\nPROTOCOL when_to_seek_help:\n"
        + "\n".join(f"- {step}" for step in protocol.when_to_seek_help)
        + f"\nWrite the headline and questions in {groq_language_phrase(context.reply_language)}."
        + " Then select exact English protocol lines and translate those lines."
    )


def _norm_step(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _select_protocol_lines(selected: object, allowed: list[str]) -> list[str]:
    if not isinstance(selected, list) or not allowed:
        return []
    index = {_norm_step(item): item for item in allowed}
    picked: list[str] = []
    seen: set[str] = set()
    for raw in selected:
        if not isinstance(raw, str):
            continue
        key = _norm_step(raw)
        match = index.get(key)
        if match and match not in seen:
            picked.append(match)
            seen.add(match)
    return picked


def _apply_aligned_translations(source: list[str], translated: object) -> list[str]:
    if not source or not isinstance(translated, list) or len(translated) != len(source):
        return source
    out: list[str] = []
    for original, raw in zip(source, translated):
        if not isinstance(raw, str):
            return source
        text = raw.strip()
        if not text or not _text_is_safe(text):
            return source
        out.append(text[:500])
        _ = original
    return out



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
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                language=groq_language_phrase(context.reply_language or "English")
            ),
        },
        {"role": "user", "content": _build_user_prompt(context, protocol, key)},
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
        if isinstance(payload, dict):
            headline = payload.get("headline") or payload.get("whats_happening")
            if isinstance(headline, str) and headline.strip() and _text_is_safe(headline):
                protocol.explanation = headline.strip()[:300]
            actions = _select_protocol_lines(
                payload.get("selected_actions"), protocol.immediate_actions
            )
            if len(actions) >= 2:
                protocol.immediate_actions = actions
            warnings = _select_protocol_lines(
                payload.get("selected_warnings"), protocol.safety_warnings
            )
            if len(warnings) >= 1:
                protocol.safety_warnings = warnings
            if not is_english_reply(context.reply_language):
                protocol.immediate_actions = _apply_aligned_translations(
                    protocol.immediate_actions, payload.get("translated_actions")
                )
                protocol.safety_warnings = _apply_aligned_translations(
                    protocol.safety_warnings, payload.get("translated_warnings")
                )
                protocol.when_to_seek_help = _apply_aligned_translations(
                    protocol.when_to_seek_help, payload.get("translated_seek_help")
                )
    except Exception as exc:
        logger.warning("Ignoring LLM enrichment (%s).", exc)

    return protocol, "deterministic", groq_status


async def generate_action_plan(context: ActionPlanContext) -> ActionPlan:
    plan, _, _ = await generate_action_plan_with_provenance(context)
    return plan
