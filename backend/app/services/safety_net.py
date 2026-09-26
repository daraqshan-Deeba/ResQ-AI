"""Deterministic life-threat lexicon — runs before and independently of triage."""

from __future__ import annotations

import re
from dataclasses import dataclass

_CRITICAL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("not_breathing", re.compile(r"\b(not breathing|stopped breathing|can't breathe|cannot breathe|no pulse)\b", re.I)),
    ("not_breathing", re.compile(r"\b(saans nahi|saans band|breathing nahi)\b", re.I)),
    ("choking", re.compile(r"\b(chok(e|ing)|heimlich|food stuck in (the )?throat)\b", re.I)),
    ("drowning", re.compile(r"\b(drown(ing)?|under water and not coming up)\b", re.I)),
    ("cardiac", re.compile(r"\b(heart attack|chest pain|cardiac arrest|severe chest)\b", re.I)),
    ("cardiac", re.compile(r"\b(seene mein dard|dil ka daura)\b", re.I)),
    ("self_harm", re.compile(r"\b(kill myself|end my life|want to die|suicide|self[- ]harm)\b", re.I)),
]

_HIGH_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "fire",
        re.compile(
            r"\b(smoke everywhere|aag lag(?:i| gayi| gaye)?)\b"
            r"|\b(?:fire|flames)\b.{0,48}\b(?:house|home|building|apartment|flat|kitchen|room|office|warehouse)\b"
            r"|\b(?:house|home|building|apartment|flat|kitchen|room|office|warehouse)\b.{0,48}\b(?:on fire|in flames|catching fire|\bfire\b)\b"
            r"|\b(?:clothes|clothing|shirt|dress).{0,24}on fire\b"
            r"|\bi(?:'m| am) on fire\b",
            re.I,
        ),
    ),
    (
        "burn",
        re.compile(
            r"\b(?:phone|mobile|cellphone|laptop|charger|battery|power bank).{0,48}\b(?:flames|on fire|caught fire|catching fire|exploded|burst into)\b"
            r"|\b(?:flames|on fire|caught fire).{0,48}\b(?:phone|mobile|cellphone|laptop|charger)\b"
            r"|\b(?:burnt|burned|burning)\s+(?:my\s+)?(?:hand|hands|arm|finger|fingers|skin|face|leg|palm)\b"
            r"|\bburns? on (?:my )?(?:hand|arm|skin|finger)\b",
            re.I,
        ),
    ),
    ("gas_leak", re.compile(r"\b(gas leak|smell(s)? (of )?gas|lpg leak)\b", re.I)),
    ("assault", re.compile(r"\b(attacking me|being attacked|stabbed|gunshot|weapon)\b", re.I)),
]


@dataclass(frozen=True)
class SafetyNetResult:
    hits: tuple[str, ...]
    forced_level: str | None  # Critical | High | None
    protocol_key: str | None


def detect_life_threats(text: str) -> SafetyNetResult:
    if not text or not text.strip():
        return SafetyNetResult(hits=(), forced_level=None, protocol_key=None)

    hits: list[str] = []
    for label, pattern in _CRITICAL_PATTERNS:
        if pattern.search(text) and label not in hits:
            hits.append(label)
    critical = bool(hits)
    for label, pattern in _HIGH_PATTERNS:
        if pattern.search(text) and label not in hits:
            hits.append(label)

    if not hits:
        return SafetyNetResult(hits=(), forced_level=None, protocol_key=None)

    forced = "Critical" if critical else "High"
    protocol_key = _protocol_for_hits(hits)
    return SafetyNetResult(hits=tuple(hits), forced_level=forced, protocol_key=protocol_key)


def _protocol_for_hits(hits: list[str]) -> str:
    if "fire" in hits:
        return "fire"
    if "burn" in hits:
        return "burn"
    if "gas_leak" in hits:
        return "gas_leak"
    if "cardiac" in hits or "not_breathing" in hits or "choking" in hits:
        return "medical_emergency"
    if "drowning" in hits:
        return "drowning"
    if "self_harm" in hits:
        return "self_harm"
    if "assault" in hits:
        return "assault"
    return "unclassified"
