"""Versioned emergency protocols loaded from JSON (source of truth for user-facing steps)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.models.schemas import ActionPlan, EmergencyCategory

_PROTOCOL_PATH = Path(__file__).resolve().parents[1] / "data" / "emergency_protocols.json"

TRUSTED_NUMBERS = frozenset({"112", "108", "1070"})


@lru_cache(maxsize=1)
def _load_bundle() -> dict:
    return json.loads(_PROTOCOL_PATH.read_text(encoding="utf-8"))


def default_contacts() -> list[str]:
    return list(_load_bundle().get("contacts") or [])


def get_protocol_plan(key: str, trusted_contacts: list[str] | None = None) -> ActionPlan:
    plans = _load_bundle().get("plans") or {}
    payload = dict(plans.get(key) or plans["unclassified"])
    payload["emergency_contacts"] = list(trusted_contacts or default_contacts())
    return ActionPlan.model_validate(payload)


def protocol_key_for(
    category: EmergencyCategory | str,
    safety_protocol_key: str | None,
    matched_rule: str | None = None,
) -> str:
    if safety_protocol_key:
        return safety_protocol_key
    rule = (matched_rule or "").lower()
    if str(category) == "injury" and "fall / mobility" in rule:
        return "injury_mobility"
    return str(category or "unclassified")
