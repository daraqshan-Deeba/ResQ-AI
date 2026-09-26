"""Hazard → evidence requirements. LLM tools may only fetch these, never decide."""

from __future__ import annotations

from typing import Literal

EvidenceKind = Literal["weather", "hospitals", "reports"]

# Snakebite/injury still list hospitals when location is present.
# Weather is only for hydromet hazards.
_MAP: dict[str, frozenset[EvidenceKind]] = {
    "flooding": frozenset({"weather", "hospitals", "reports"}),
    "cyclone": frozenset({"weather", "reports"}),
    "electrocution": frozenset({"hospitals"}),
    "snakebite": frozenset({"hospitals"}),
    "injury": frozenset({"hospitals"}),
    "accident": frozenset({"hospitals", "reports"}),
    "structural_damage": frozenset({"hospitals", "reports"}),
    "unclassified": frozenset({"hospitals", "reports"}),
    "fire": frozenset({"hospitals"}),
    "gas_leak": frozenset({"hospitals"}),
    "medical_emergency": frozenset({"hospitals"}),
    "drowning": frozenset({"hospitals"}),
    "self_harm": frozenset(),
    "assault": frozenset({"hospitals"}),
}

EVIDENCE_TOOL_NAMES = ("fetch_weather", "fetch_hospitals", "search_reports")

GROQ_EVIDENCE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "fetch_weather",
            "description": "Fetch live weather for coordinates. Use only for flood/storm context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                },
                "required": ["lat", "lon"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_hospitals",
            "description": "List nearby hospitals from the ResQ directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lat": {"type": "number"},
                    "lon": {"type": "number"},
                },
                "required": ["lat", "lon"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_reports",
            "description": "Search community reports as unverified local evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "area": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
]


def required_evidence(category: str, protocol_key: str | None = None) -> frozenset[EvidenceKind]:
    key = protocol_key or category
    return _MAP.get(key) or _MAP.get(category) or frozenset({"hospitals", "reports"})


def weather_relevant(category: str, protocol_key: str | None = None) -> bool:
    return "weather" in required_evidence(category, protocol_key)
