"""
Confidence Aggregation Service — Step 6

Implements the centralized confidence aggregation layer following the
weakest-link principle (overall_confidence = min(triage, weather, action_plan)).

Architectural Rules:
  1. Weakest-link aggregation: No averaging, no hiding uncertainty.
  2. No LLM authority: LLM confidence or severity claims are strictly ignored.
  3. Risk and confidence remain strictly separate:
     - Confidence measures signal reliability (0.0 to 1.0).
     - Risk measures physical situation danger (e.g. 0-100 flood score).
  4. Centralized deterministic thresholds:
     - High:   overall >= 0.80
     - Medium: 0.50 <= overall < 0.80
     - Low:    overall < 0.50
  5. Deterministic tie-breaking for limiting_factor:
     1. triage
     2. weather
     3. action_plan
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

from app.models.schemas import (
    ActionPlanSource,
    ConfidenceLevel,
    ConfidenceResult,
    ServiceResult,
    WeatherSummary,
)

logger = logging.getLogger("resq.confidence")

# ─────────────────────────────────────────────────────────────────────────────
# Centralized Thresholds and Constants
# ─────────────────────────────────────────────────────────────────────────────
CONFIDENCE_HIGH_THRESHOLD: float = 0.80
CONFIDENCE_MEDIUM_THRESHOLD: float = 0.50

WEATHER_CONFIDENCE_AVAILABLE: float = 1.0
WEATHER_CONFIDENCE_UNAVAILABLE: float = 0.20

ACTION_PLAN_CONFIDENCE_DETERMINISTIC: float = 1.0
ACTION_PLAN_CONFIDENCE_GROQ: float = 0.35


# ─────────────────────────────────────────────────────────────────────────────
# Subsystem Confidence Helpers
# ─────────────────────────────────────────────────────────────────────────────

def calculate_weather_confidence(
    weather_result: Optional[ServiceResult[WeatherSummary] | bool],
) -> float:
    """Calculate confidence in the weather signal based on availability.

    - Available (real weather data successfully obtained): 1.0
    - Unavailable (service disabled, timed out, network error, rate limited): 0.20
    """
    if weather_result is None:
        return WEATHER_CONFIDENCE_UNAVAILABLE
    if isinstance(weather_result, bool):
        return WEATHER_CONFIDENCE_AVAILABLE if weather_result else WEATHER_CONFIDENCE_UNAVAILABLE
    if isinstance(weather_result, ServiceResult):
        return (
            WEATHER_CONFIDENCE_AVAILABLE
            if (weather_result.available and weather_result.data is not None)
            else WEATHER_CONFIDENCE_UNAVAILABLE
        )
    return WEATHER_CONFIDENCE_UNAVAILABLE


def calculate_action_plan_confidence(source: ActionPlanSource | str) -> float:
    """Calculate confidence in the action plan based on its provenance.

    - Deterministic fallback (curated application protocol): 1.0
    - Groq LLM (probabilistic generative model): 0.35
    """
    if source == "deterministic":
        return ACTION_PLAN_CONFIDENCE_DETERMINISTIC
    elif source == "groq":
        return ACTION_PLAN_CONFIDENCE_GROQ
    else:
        logger.warning("Unknown action plan source '%s'; using conservative score.", source)
        return ACTION_PLAN_CONFIDENCE_GROQ


def determine_confidence_level(score: float) -> ConfidenceLevel:
    """Categorize overall confidence using deterministic thresholds.

    - high:   >= 0.80
    - medium: 0.50 <= score < 0.80
    - low:    < 0.50
    """
    s = round(score, 4)
    if s >= CONFIDENCE_HIGH_THRESHOLD:
        return "high"
    elif s >= CONFIDENCE_MEDIUM_THRESHOLD:
        return "medium"
    else:
        return "low"


def determine_limiting_factor(
    triage_conf: float,
    weather_conf: float,
    action_conf: float,
) -> str:
    """Identify which component is responsible for the weakest confidence.

    Deterministic tie-breaking priority when multiple components share the minimum:
      1. triage
      2. weather
      3. action_plan
    """
    min_val = min(triage_conf, weather_conf, action_conf)
    if math.isclose(triage_conf, min_val, abs_tol=1e-6):
        return "triage"
    elif math.isclose(weather_conf, min_val, abs_tol=1e-6):
        return "weather"
    else:
        return "action_plan"


def validate_confidence_score(val: Any, name: str) -> float:
    """Validate that a confidence score is a valid, finite number in [0.0, 1.0].

    Raises:
        ValueError or TypeError on corrupt/invalid confidence data.
    """
    if val is None:
        raise ValueError(f"{name} cannot be None")
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        raise TypeError(f"{name} must be a float or int, got {type(val).__name__}")
    if math.isnan(val):
        raise ValueError(f"{name} cannot be NaN")
    if math.isinf(val):
        raise ValueError(f"{name} cannot be Infinity")
    if val < 0.0 or val > 1.0:
        raise ValueError(f"{name} must be between 0.0 and 1.0, got {val}")
    return float(val)


# ─────────────────────────────────────────────────────────────────────────────
# Central Aggregator
# ─────────────────────────────────────────────────────────────────────────────

def aggregate_confidence(
    triage_confidence: float,
    weather_confidence: float,
    action_plan_confidence: float,
) -> ConfidenceResult:
    """Aggregate subsystem confidences into a single ConfidenceResult via weakest-link.

    Formula:
        overall_confidence = min(triage_confidence, weather_confidence, action_plan_confidence)

    Raises:
        ValueError: If any confidence score is outside [0.0, 1.0], NaN, Infinity, or None.
        TypeError: If any confidence score is not a numeric type.
    """
    t_val = validate_confidence_score(triage_confidence, "triage_confidence")
    w_val = validate_confidence_score(weather_confidence, "weather_confidence")
    a_val = validate_confidence_score(action_plan_confidence, "action_plan_confidence")

    overall = round(min(t_val, w_val, a_val), 4)
    level = determine_confidence_level(overall)
    limiting = determine_limiting_factor(t_val, w_val, a_val)

    return ConfidenceResult(
        overall_confidence=overall,
        confidence_level=level,
        triage_confidence=t_val,
        weather_confidence=w_val,
        action_plan_confidence=a_val,
        limiting_factor=limiting,
    )


def aggregate_confidence_safe(
    triage_confidence: Any,
    weather_confidence: Any,
    action_plan_confidence: Any,
) -> ConfidenceResult:
    """Safe wrapper for confidence aggregation that returns a degraded fallback rather than raising.

    Used when inputs originate from unvalidated or external sources.
    """
    try:
        return aggregate_confidence(
            triage_confidence=triage_confidence,
            weather_confidence=weather_confidence,
            action_plan_confidence=action_plan_confidence,
        )
    except (ValueError, TypeError, Exception) as exc:
        logger.warning("aggregate_confidence_safe: Input validation failed (%s). Returning degraded.", exc)
        return ConfidenceResult(
            overall_confidence=0.0,
            confidence_level="low",
            triage_confidence=0.0,
            weather_confidence=0.0,
            action_plan_confidence=0.0,
            limiting_factor="invalid_input",
        )
