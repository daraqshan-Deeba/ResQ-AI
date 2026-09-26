"""Fast2SMS Quick SMS for SOS alerts. Fail-open; never send to public emergency numbers."""

from __future__ import annotations

import logging
import re
from typing import Literal

import httpx

from app.core.config import settings

logger = logging.getLogger("resq.fast2sms")

SmsStatus = Literal["sent", "failed", "skipped"]

_E164 = re.compile(r"^\+[1-9]\d{6,14}$")
_EMERGENCY_DIGITS = frozenset({"112", "108", "100", "101", "102"})
_FAST2SMS_URL = "https://www.fast2sms.com/dev/bulkV2"


def fast2sms_configured() -> bool:
    return bool(settings.fast2sms_api_key.strip())


def is_smsable_phone(phone: str | None) -> bool:
    raw = (phone or "").strip()
    if not raw or not _E164.match(raw):
        return False
    digits = re.sub(r"\D", "", raw)
    return digits not in _EMERGENCY_DIGITS


def to_fast2sms_number(phone: str) -> str | None:
    """Fast2SMS Quick SMS expects 10-digit Indian mobiles."""
    digits = re.sub(r"\D", "", phone)
    if digits in _EMERGENCY_DIGITS:
        return None
    if len(digits) >= 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        return digits
    return None


def build_sos_sms_body(
    *,
    relation: str | None,
    user_name: str | None,
    maps_link: str,
    has_location: bool,
) -> str:
    who = (relation or "").strip() or "family member"
    if who.isupper():
        who = who.title()
    name = (user_name or "").strip()
    subject = f"Your {who}, {name}," if name else f"Your {who}"
    loc = (
        f"This is the location: {maps_link}"
        if has_location
        else "Their location was not available."
    )
    return (
        f"{subject} has hit an SOS. They might be in danger or might need you. {loc}"
    )


def send_sos_sms(
    *,
    to_phone: str | None,
    relation: str | None,
    user_name: str | None,
    maps_link: str,
    has_location: bool,
) -> SmsStatus:
    """Return sent | skipped | failed. Never raises to the SOS caller."""
    if not is_smsable_phone(to_phone):
        logger.warning("SOS SMS skipped: phone is missing or not a personal mobile")
        return "skipped"
    number = to_fast2sms_number(to_phone or "")
    if not number:
        logger.warning("SOS SMS skipped: phone is not a 10-digit Indian mobile")
        return "skipped"
    if not fast2sms_configured():
        logger.warning("SOS SMS skipped: FAST2SMS_API_KEY is not set")
        return "skipped"

    body = build_sos_sms_body(
        relation=relation,
        user_name=user_name,
        maps_link=maps_link,
        has_location=has_location,
    )
    try:
        with httpx.Client(timeout=10) as client:
            response = client.post(
                _FAST2SMS_URL,
                headers={
                    "Authorization": settings.fast2sms_api_key.strip(),
                    "Content-Type": "application/json",
                },
                json={
                    "route": "q",
                    "message": body,
                    "language": "english",
                    "flash": 0,
                    "numbers": number,
                },
            )
            response.raise_for_status()
            payload = response.json()
        if payload.get("return") is True:
            logger.info("Fast2SMS SOS SMS sent")
            return "sent"
        logger.warning("Fast2SMS SOS SMS rejected")
        return "failed"
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            payload = exc.response.json()
            raw = payload.get("message")
            if isinstance(raw, list):
                detail = "; ".join(str(part) for part in raw[:2])
            elif raw:
                detail = str(raw)[:200]
        except Exception:
            detail = ""
        logger.warning(
            "Fast2SMS SOS SMS failed: HTTP %s %s",
            exc.response.status_code,
            detail,
        )
        return "failed"
    except Exception as exc:
        logger.warning("Fast2SMS SOS SMS failed: %s", type(exc).__name__)
        return "failed"
