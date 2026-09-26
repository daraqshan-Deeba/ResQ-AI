"""Deterministic emergency level from category, weather (when relevant), and safety net."""

from __future__ import annotations

from typing import Iterable

from app.models.schemas import EmergencyCategory

LEVEL_RANK = {
    "Unknown": 0,
    "Low": 1,
    "Moderate": 2,
    "High": 3,
    "Critical": 4,
}

_CATEGORY_LEVEL: dict[str, str] = {
    "electrocution": "Critical",
    "snakebite": "Critical",
    "structural_damage": "High",
    "flooding": "High",
    "cyclone": "High",
    "injury": "Moderate",
    "accident": "Moderate",
    "unclassified": "Unknown",
}


def _max_level(*levels: str | None) -> str:
    best = "Unknown"
    for level in levels:
        if not level:
            continue
        if LEVEL_RANK.get(level, -1) > LEVEL_RANK.get(best, -1):
            best = level
    return best


def category_base_level(category: EmergencyCategory | str) -> str:
    return _CATEGORY_LEVEL.get(str(category), "Unknown")


def weather_level_to_emergency(risk_level: str | None) -> str | None:
    if risk_level == "critical":
        return "Critical"
    if risk_level == "warning":
        return "High"
    if risk_level == "watch":
        return "Moderate"
    return None


def determine_emergency_level(
    category: EmergencyCategory | str,
    risk_level: str | None = None,
    *,
    candidate_categories: Iterable[str] | None = None,
    safety_forced_level: str | None = None,
    weather_relevant: bool = False,
) -> str:
    levels = [category_base_level(category)]
    if candidate_categories:
        levels.extend(category_base_level(c) for c in candidate_categories)
    if weather_relevant:
        levels.append(weather_level_to_emergency(risk_level))
    levels.append(safety_forced_level)
    return _max_level(*levels)
