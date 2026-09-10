"""
Step 6 Tests — Centralized Confidence Aggregation Layer

Test Inventory:
  Basic Aggregation (1-5):
    1. All high -> high confidence.
    2. One weak signal -> overall equals the weakest signal.
    3. Triage is the weakest signal -> limiting_factor is 'triage'.
    4. Weather is the weakest signal -> limiting_factor is 'weather'.
    5. Action plan is the weakest signal -> limiting_factor is 'action_plan'.

  Threshold Tests (6-9):
    6. Score exactly 0.80 -> high.
    7. Score 0.79 -> medium.
    8. Score exactly 0.50 -> medium.
    9. Score 0.49 -> low.

  Provenance Tests (10-11):
    10. Deterministic action plan -> confidence 1.0.
    11. Groq action plan -> confidence 0.35.

  Weather Confidence Tests (12-16):
    12. Weather available -> weather confidence 1.0.
    13. Weather unavailable -> weather confidence 0.20.
    14. Weather service disabled -> weather confidence 0.20.
    15. Weather timeout -> weather confidence 0.20.
    16. Weather network error -> weather confidence 0.20.

  Triage Confidence Preservation Tests (17-20):
    17. Tier 1 triage confidence (0.93) preserved in aggregation.
    18. Tier 2 triage confidence (0.82 / 0.72) preserved in aggregation.
    19. Tier 3 Groq triage confidence (0.35) preserved in aggregation.
    20. Unclassified triage confidence (0.20) preserved in aggregation.

  Safety & Authority Boundary Tests (21-25):
    21. LLM confidence field cannot influence aggregator.
    22. LLM severity cannot influence aggregator.
    23. LLM emergency level cannot influence aggregator.
    24. Weather risk score cannot be substituted for weather confidence.
    25. Confidence cannot alter deterministic weather risk calculation.

  Invalid Input Tests (26-31):
    26. Negative confidence rejected.
    27. Confidence > 1.0 rejected.
    28. NaN confidence rejected.
    29. Infinity confidence rejected.
    30. Missing confidence rejected.
    31. None confidence rejected.

  Determinism Test (32):
    32. Identical inputs yield identical ConfidenceResult objects.
"""

import math
import pytest
from pydantic import ValidationError

from app.models.schemas import (
    ConfidenceResult,
    RiskScore,
    ServiceResult,
    TriageResult,
    WeatherSummary,
)
from app.services.confidence_service import (
    ACTION_PLAN_CONFIDENCE_DETERMINISTIC,
    ACTION_PLAN_CONFIDENCE_GROQ,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_MEDIUM_THRESHOLD,
    WEATHER_CONFIDENCE_AVAILABLE,
    WEATHER_CONFIDENCE_UNAVAILABLE,
    aggregate_confidence,
    aggregate_confidence_safe,
    calculate_action_plan_confidence,
    calculate_weather_confidence,
    determine_confidence_level,
    determine_limiting_factor,
)
from app.services.weather_service import compute_risk_score


# ─────────────────────────────────────────────────────────────────────────────
# 1. BASIC AGGREGATION TESTS (1–5)
# ─────────────────────────────────────────────────────────────────────────────

def test_1_all_high_yields_high():
    """When all subsystems have high confidence (>= 0.80), overall confidence is high."""
    result = aggregate_confidence(
        triage_confidence=0.93,
        weather_confidence=1.00,
        action_plan_confidence=1.00,
    )
    assert result.overall_confidence == 0.93
    assert result.confidence_level == "high"
    assert result.limiting_factor == "triage"


def test_2_one_weak_signal_pulls_overall_down():
    """Weakest link principle: a single low signal prevents a high overall result."""
    result = aggregate_confidence(
        triage_confidence=0.93,
        weather_confidence=0.20,
        action_plan_confidence=1.00,
    )
    assert result.overall_confidence == 0.20
    assert result.confidence_level == "low"
    assert result.limiting_factor == "weather"


def test_3_triage_weakest_limiting_factor():
    """When triage is the weakest subsystem, limiting_factor is 'triage'."""
    result = aggregate_confidence(
        triage_confidence=0.20,
        weather_confidence=1.00,
        action_plan_confidence=1.00,
    )
    assert result.overall_confidence == 0.20
    assert result.confidence_level == "low"
    assert result.limiting_factor == "triage"


def test_4_weather_weakest_limiting_factor():
    """When weather is the weakest subsystem, limiting_factor is 'weather'."""
    result = aggregate_confidence(
        triage_confidence=0.82,
        weather_confidence=0.20,
        action_plan_confidence=0.35,
    )
    assert result.overall_confidence == 0.20
    assert result.limiting_factor == "weather"


def test_5_action_plan_weakest_limiting_factor():
    """When action plan is the weakest subsystem, limiting_factor is 'action_plan'."""
    result = aggregate_confidence(
        triage_confidence=0.93,
        weather_confidence=1.00,
        action_plan_confidence=0.35,
    )
    assert result.overall_confidence == 0.35
    assert result.confidence_level == "low"
    assert result.limiting_factor == "action_plan"


# ─────────────────────────────────────────────────────────────────────────────
# 2. THRESHOLD TESTS (6–9)
# ─────────────────────────────────────────────────────────────────────────────

def test_6_boundary_exactly_point_80_is_high():
    """Overall confidence exactly equal to 0.80 must classify as 'high'."""
    result = aggregate_confidence(0.80, 1.0, 1.0)
    assert result.overall_confidence == 0.80
    assert result.confidence_level == "high"
    assert determine_confidence_level(0.80) == "high"


def test_7_boundary_point_79_is_medium():
    """Overall confidence of 0.79 must classify as 'medium'."""
    result = aggregate_confidence(0.79, 1.0, 1.0)
    assert result.overall_confidence == 0.79
    assert result.confidence_level == "medium"
    assert determine_confidence_level(0.79) == "medium"


def test_8_boundary_exactly_point_50_is_medium():
    """Overall confidence exactly equal to 0.50 must classify as 'medium'."""
    result = aggregate_confidence(0.50, 1.0, 1.0)
    assert result.overall_confidence == 0.50
    assert result.confidence_level == "medium"
    assert determine_confidence_level(0.50) == "medium"


def test_9_boundary_point_49_is_low():
    """Overall confidence of 0.49 must classify as 'low'."""
    result = aggregate_confidence(0.49, 1.0, 1.0)
    assert result.overall_confidence == 0.49
    assert result.confidence_level == "low"
    assert determine_confidence_level(0.49) == "low"


# ─────────────────────────────────────────────────────────────────────────────
# 3. PROVENANCE TESTS (10–11)
# ─────────────────────────────────────────────────────────────────────────────

def test_10_deterministic_action_plan_provenance():
    """Deterministic fallback action plan has high provenance confidence (1.0)."""
    conf = calculate_action_plan_confidence("deterministic")
    assert conf == ACTION_PLAN_CONFIDENCE_DETERMINISTIC
    assert conf == 1.0


def test_11_groq_action_plan_provenance():
    """Groq-generated action plan is capped at conservative confidence (0.35)."""
    conf = calculate_action_plan_confidence("groq")
    assert conf == ACTION_PLAN_CONFIDENCE_GROQ
    assert conf == 0.35


# ─────────────────────────────────────────────────────────────────────────────
# 4. WEATHER CONFIDENCE TESTS (12–16)
# ─────────────────────────────────────────────────────────────────────────────

def test_12_weather_available_high_confidence():
    """When weather service returned real live data, confidence is 1.0."""
    mock_summary = WeatherSummary(
        temp_c=28.0,
        condition="Rain",
        rain_mm_last_hour=15.0,
        alert_active=False,
    )
    result = ServiceResult[WeatherSummary](available=True, data=mock_summary)
    assert calculate_weather_confidence(result) == WEATHER_CONFIDENCE_AVAILABLE
    assert calculate_weather_confidence(True) == 1.0


def test_13_weather_unavailable_conservative_confidence():
    """When weather is unavailable, confidence drops to conservative 0.20."""
    result = ServiceResult[WeatherSummary](available=False, error_type="server_error")
    assert calculate_weather_confidence(result) == WEATHER_CONFIDENCE_UNAVAILABLE
    assert calculate_weather_confidence(False) == 0.20
    assert calculate_weather_confidence(None) == 0.20


def test_14_weather_service_disabled():
    """Service disabled error maps to 0.20 confidence."""
    result = ServiceResult[WeatherSummary](available=False, error_type="service_disabled")
    assert calculate_weather_confidence(result) == 0.20


def test_15_weather_timeout():
    """Timeout error maps to 0.20 confidence."""
    result = ServiceResult[WeatherSummary](available=False, error_type="timeout")
    assert calculate_weather_confidence(result) == 0.20


def test_16_weather_network_error():
    """Network connection error maps to 0.20 confidence."""
    result = ServiceResult[WeatherSummary](available=False, error_type="network_error")
    assert calculate_weather_confidence(result) == 0.20


# ─────────────────────────────────────────────────────────────────────────────
# 5. TRIAGE CONFIDENCE PRESERVATION (17–20)
# ─────────────────────────────────────────────────────────────────────────────

def test_17_tier1_triage_confidence_preserved():
    """Tier 1 deterministic rule confidence (0.93) is preserved directly."""
    triage = TriageResult(
        category="flooding",
        confidence=0.93,
        tier=1,
        matched_rule_or_example="flood water",
        explanation="Keyword match",
    )
    result = aggregate_confidence(triage.confidence, 1.0, 1.0)
    assert result.triage_confidence == 0.93
    assert result.overall_confidence == 0.93


def test_18_tier2_triage_confidence_preserved():
    """Tier 2 embedding similarity confidence (0.82 or 0.72) is preserved directly."""
    triage_high = TriageResult(
        category="snakebite",
        confidence=0.82,
        tier=2,
        explanation="Embedding match",
    )
    result_high = aggregate_confidence(triage_high.confidence, 1.0, 1.0)
    assert result_high.triage_confidence == 0.82
    assert result_high.confidence_level == "high"

    triage_med = TriageResult(
        category="snakebite",
        confidence=0.72,
        tier=2,
        explanation="Embedding match",
    )
    result_med = aggregate_confidence(triage_med.confidence, 1.0, 1.0)
    assert result_med.triage_confidence == 0.72
    assert result_med.confidence_level == "medium"


def test_19_tier3_triage_confidence_preserved():
    """Tier 3 Groq triage classification (0.35) is preserved directly."""
    triage = TriageResult(
        category="accident",
        confidence=0.35,
        tier=3,
        explanation="LLM fallback",
    )
    result = aggregate_confidence(triage.confidence, 1.0, 1.0)
    assert result.triage_confidence == 0.35
    assert result.overall_confidence == 0.35
    assert result.confidence_level == "low"


def test_20_unclassified_triage_confidence_preserved():
    """Unclassified triage confidence (0.20) is preserved directly."""
    triage = TriageResult(
        category="unclassified",
        confidence=0.20,
        tier=3,
        explanation="Could not classify",
    )
    result = aggregate_confidence(triage.confidence, 1.0, 1.0)
    assert result.triage_confidence == 0.20
    assert result.overall_confidence == 0.20
    assert result.confidence_level == "low"


# ─────────────────────────────────────────────────────────────────────────────
# 6. SAFETY & AUTHORITY BOUNDARY TESTS (21–25)
# ─────────────────────────────────────────────────────────────────────────────

def test_21_llm_confidence_field_cannot_influence_aggregator():
    """Even if an LLM outputs 'confidence': 0.99, ConfidenceResult rejects extra fields."""
    with pytest.raises(ValidationError):
        ConfidenceResult(
            overall_confidence=0.99,
            confidence_level="high",
            triage_confidence=0.99,
            weather_confidence=1.0,
            action_plan_confidence=1.0,
            limiting_factor="none",
            llm_confidence=0.99,  # forbidden extra field
        )


def test_22_llm_severity_cannot_influence_aggregator():
    """Severity fields injected by LLM are forbidden in ConfidenceResult."""
    with pytest.raises(ValidationError):
        ConfidenceResult(
            overall_confidence=0.85,
            confidence_level="high",
            triage_confidence=0.85,
            weather_confidence=1.0,
            action_plan_confidence=1.0,
            limiting_factor="triage",
            severity="critical",  # forbidden extra field
        )


def test_23_llm_emergency_level_cannot_influence_aggregator():
    """Emergency level injected by LLM is forbidden in ConfidenceResult."""
    with pytest.raises(ValidationError):
        ConfidenceResult(
            overall_confidence=0.85,
            confidence_level="high",
            triage_confidence=0.85,
            weather_confidence=1.0,
            action_plan_confidence=1.0,
            limiting_factor="triage",
            emergency_level="High",  # forbidden extra field
        )


def test_24_weather_risk_value_cannot_substitute_for_confidence():
    """Weather risk (e.g. score=18 or level='safe') is not a confidence value."""
    # A safe weather risk does not mean weather confidence is high if weather is unavailable!
    weather_unavailable = ServiceResult[WeatherSummary](available=False, error_type="timeout")
    # Even though fallback risk level might be 'safe' with score=18:
    conf = calculate_weather_confidence(weather_unavailable)
    assert conf == 0.20, "Unavailable weather must yield conservative 0.20 confidence, not high"


def test_25_confidence_cannot_alter_deterministic_weather_risk():
    """Computing or aggregating confidence has zero side-effects on deterministic weather risk."""
    summary = WeatherSummary(
        temp_c=30.0,
        condition="Heavy rain",
        rain_mm_last_hour=25.0,
        alert_active=True,
    )
    risk_before = compute_risk_score(summary)

    # Run multiple confidence aggregations
    aggregate_confidence(0.20, 0.20, 0.35)
    aggregate_confidence(1.0, 1.0, 1.0)

    risk_after = compute_risk_score(summary)
    assert risk_before.score == risk_after.score
    assert risk_before.level == risk_after.level
    assert risk_before.rainfall_intensity_pct == risk_after.rainfall_intensity_pct


# ─────────────────────────────────────────────────────────────────────────────
# 7. INVALID INPUT TESTS (26–31)
# ─────────────────────────────────────────────────────────────────────────────

def test_26_negative_confidence_rejected():
    """Negative confidence score is explicitly rejected by validation."""
    with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
        aggregate_confidence(-0.1, 1.0, 1.0)

    safe_res = aggregate_confidence_safe(-0.1, 1.0, 1.0)
    assert safe_res.overall_confidence == 0.0
    assert safe_res.confidence_level == "low"
    assert safe_res.limiting_factor == "invalid_input"


def test_27_confidence_greater_than_one_rejected():
    """Confidence score greater than 1.0 is explicitly rejected by validation."""
    with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
        aggregate_confidence(1.5, 1.0, 1.0)

    safe_res = aggregate_confidence_safe(1.5, 1.0, 1.0)
    assert safe_res.overall_confidence == 0.0
    assert safe_res.limiting_factor == "invalid_input"


def test_28_nan_confidence_rejected():
    """NaN confidence score is explicitly rejected by validation."""
    with pytest.raises(ValueError, match="cannot be NaN"):
        aggregate_confidence(float("nan"), 1.0, 1.0)

    safe_res = aggregate_confidence_safe(float("nan"), 1.0, 1.0)
    assert safe_res.overall_confidence == 0.0
    assert safe_res.limiting_factor == "invalid_input"


def test_29_infinity_confidence_rejected():
    """Infinity confidence score is explicitly rejected by validation."""
    with pytest.raises(ValueError, match="cannot be Infinity"):
        aggregate_confidence(float("inf"), 1.0, 1.0)

    safe_res = aggregate_confidence_safe(float("inf"), 1.0, 1.0)
    assert safe_res.overall_confidence == 0.0
    assert safe_res.limiting_factor == "invalid_input"


def test_30_missing_confidence_rejected():
    """Calling aggregate_confidence without required arguments raises TypeError."""
    with pytest.raises(TypeError):
        aggregate_confidence()  # type: ignore[call-arg]


def test_31_none_confidence_rejected():
    """None confidence score is explicitly rejected by validation."""
    with pytest.raises(ValueError, match="cannot be None"):
        aggregate_confidence(None, 1.0, 1.0)  # type: ignore[arg-type]

    safe_res = aggregate_confidence_safe(None, 1.0, 1.0)
    assert safe_res.overall_confidence == 0.0
    assert safe_res.limiting_factor == "invalid_input"


# ─────────────────────────────────────────────────────────────────────────────
# 8. DETERMINISM TEST (32)
# ─────────────────────────────────────────────────────────────────────────────

def test_32_identical_inputs_yield_identical_results():
    """Confidence aggregator is strictly deterministic; repeated calls return identical values."""
    res1 = aggregate_confidence(0.93, 0.20, 1.00)
    res2 = aggregate_confidence(0.93, 0.20, 1.00)
    res3 = aggregate_confidence(0.93, 0.20, 1.00)

    assert res1.model_dump() == res2.model_dump()
    assert res2.model_dump() == res3.model_dump()
    assert res1.limiting_factor == "weather"
    assert res1.overall_confidence == 0.20
    assert res1.confidence_level == "low"
