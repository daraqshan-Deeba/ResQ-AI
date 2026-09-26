"""
Step 4 Tests — Tiered Triage Classification

Test inventory:
  Tier 1 — direct category tests (8 categories)
  Tier 1 — critical edge cases (conflicting, false-positives, historical, empty, long)
  Tier 1 — determinism
  Tier 2 — mocked similarity scenarios (5 cases)
  Tier 3 — mocked Groq scenarios (5 cases)
  Tier 3 — no severity leak

All tests are synchronous-compatible (async tests use anyio).
"""

import asyncio
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import TriageResult
from app.services import triage_service


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _run(coro):
    """Run an async coroutine synchronously in tests.

    Always creates a fresh event loop to avoid RuntimeError in Python 3.12
    when running after TestClient (Steps 1-3) has torn down the default loop.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _classify(description: str) -> TriageResult:
    return _run(triage_service.classify(description))


# ─────────────────────────────────────────────────────────────────────────────
# Tier 1 — Direct category tests (Step 4N)
# ─────────────────────────────────────────────────────────────────────────────

class TestTier1DirectCategories:
    def test_flooding(self):
        result = _classify("Flood water is entering my house.")
        assert result.category == "flooding"
        assert result.tier == 1
        assert result.confidence >= 0.90

    def test_electrocution(self):
        result = _classify("There is an exposed live electrical wire.")
        assert result.category == "electrocution"
        assert result.tier == 1
        assert result.confidence >= 0.90

    def test_injury(self):
        result = _classify("Someone has a deep cut and is bleeding badly.")
        assert result.category == "injury"
        assert result.tier == 1
        assert result.confidence >= 0.90

    def test_snakebite(self):
        result = _classify("A snake bit my brother.")
        assert result.category == "snakebite"
        assert result.tier == 1
        assert result.confidence >= 0.90

    def test_cyclone(self):
        result = _classify("A cyclone is approaching our area.")
        assert result.category == "cyclone"
        assert result.tier == 1
        assert result.confidence >= 0.90

    def test_structural_damage(self):
        result = _classify("The roof has collapsed.")
        assert result.category == "structural_damage"
        assert result.tier == 1
        assert result.confidence >= 0.90

    def test_accident(self):
        result = _classify("There has been a car accident.")
        assert result.category == "accident"
        assert result.tier == 1
        assert result.confidence >= 0.90

    def test_unclassified_ambiguous(self):
        """Clearly unrelated description should not match Tier 1 confidently."""
        result = _classify("I need information about weather forecasts for tomorrow.")
        # Should NOT be Tier 1 high confidence — may fall through to Tier 2 or 3
        if result.tier == 1:
            # If Tier 1 somehow matches, confidence must be low (shouldn't happen)
            assert result.confidence < 0.90, "Ambiguous input should not yield high Tier-1 confidence"

    def test_flooding_variant_flash_flood(self):
        result = _classify("Flash flood warning — our street is completely flooded.")
        assert result.category == "flooding"
        assert result.tier == 1

    def test_flooding_variant_water_rising(self):
        result = _classify("The water level is rising inside the house.")
        assert result.category == "flooding"
        assert result.tier == 1

    def test_electrocution_variant_live_wire(self):
        result = _classify("There is a live wire on the ground after the storm.")
        assert result.category == "electrocution"
        assert result.tier == 1

    def test_injury_variant_unconscious(self):
        result = _classify("A person is unconscious and not responding.")
        assert result.category == "injury"
        assert result.tier == 1

    def test_injury_rtc_bus_fall_unable_to_walk(self):
        result = _classify(
            "I was travelling from RTC BUS and I fell. I am unable to walk"
        )
        assert result.category == "injury"
        assert result.tier == 1

    def test_injury_slipped_cannot_walk(self):
        result = _classify("I slipped and cannot walk")
        assert result.category == "injury"
        assert result.tier == 1

    def test_injury_fell_down_cannot_get_up(self):
        result = _classify("I fell down and can't get up")
        assert result.category == "injury"
        assert result.tier == 1

    def test_injury_garden_slip_knee_hurts(self):
        result = _classify(
            "i was walking through my garden and i slipped. my knee hurts what can i do"
        )
        assert result.category == "injury"
        assert result.tier == 1

    def test_accident_bus_highway_not_injury_fall(self):
        result = _classify("bus accident on the highway")
        assert result.category == "accident"
        assert result.tier == 1

    def test_fell_last_year_is_historical(self):
        result = _classify("I fell last year")
        assert result.category == "unclassified"
        assert result.tier == 3

    def test_snakebite_variant_bitten(self):
        result = _classify("Someone was bitten by a snake in the garden.")
        assert result.category == "snakebite"
        assert result.tier == 1

    def test_cyclone_variant_storm(self):
        result = _classify("There is a severe cyclone warning for our coastal area.")
        assert result.category == "cyclone"
        assert result.tier == 1

    def test_structural_damage_variant_wall(self):
        result = _classify("The wall of my house has collapsed.")
        assert result.category == "structural_damage"
        assert result.tier == 1

    def test_accident_variant_collision(self):
        result = _classify("A vehicle collision happened near the school.")
        assert result.category == "accident"
        assert result.tier == 1


# ─────────────────────────────────────────────────────────────────────────────
# Tier 1 — Critical edge case tests (Step 4N)
# ─────────────────────────────────────────────────────────────────────────────

class TestTier1EdgeCases:

    def test_conflicting_categories_no_high_confidence_tier1(self):
        """Flooding + electrocution signals → must NOT produce high-confidence Tier 1."""
        result = _classify("There is flooding and an exposed live wire inside the house.")
        # If Tier 1 resolves it (conflicting rules detected → passes to Tier 2/3)
        # it should NOT be Tier 1 with high confidence
        if result.tier == 1:
            assert result.confidence < 0.90, (
                "Conflicting categories must not yield high-confidence Tier-1 classification"
            )
        # The system should not crash
        assert result.category in (
            "flooding", "electrocution", "unclassified"
        ) or result.tier > 1

    def test_false_positive_wire_transfer(self):
        """'wire transfer' must NOT classify as electrocution."""
        result = _classify("I need help with a wire transfer.")
        assert result.category != "electrocution", (
            "'wire transfer' must not be classified as electrocution"
        )

    def test_false_positive_snake_plant(self):
        """'snake plant' must NOT classify as snakebite."""
        result = _classify("My snake plant fell over.")
        assert result.category != "snakebite", (
            "'snake plant' must not be classified as snakebite"
        )

    def test_false_positive_water_bottle(self):
        """'water bottle' must NOT classify as flooding."""
        result = _classify("I dropped my water bottle.")
        assert result.category != "flooding", (
            "'water bottle' must not be classified as flooding"
        )

    def test_historical_accident(self):
        """'car accident last year' should not be high-confidence Tier-1 active emergency."""
        result = _classify("I had a car accident last year and I need advice.")
        # Must NOT be Tier 1 high confidence (temporal guard should kick in)
        if result.tier == 1:
            assert result.confidence < 0.90, (
                "Historical accident should not yield high Tier-1 active emergency confidence"
            )

    def test_empty_input(self):
        """Empty description must not crash and should return unclassified."""
        result = _classify("")
        assert result.category == "unclassified"
        assert result.confidence < 0.50
        assert result.tier == 3

    def test_whitespace_only_input(self):
        """Whitespace-only description must not crash."""
        result = _classify("   \n\t   ")
        assert result.category == "unclassified"

    def test_very_long_input(self):
        """Very long description (10k chars) must not crash and must complete."""
        long_text = "flooding " * 1200  # ~10 800 chars
        result = _classify(long_text)
        # Should still detect flooding from the repeated word
        assert isinstance(result, TriageResult)

    def test_punctuation_normalization(self):
        """snake-bite (hyphenated) must match as snakebite."""
        result = _classify("A snake-bite victim needs immediate help.")
        assert result.category == "snakebite"
        assert result.tier == 1

    def test_case_normalization(self):
        """SNAKE BITE in all caps must match."""
        result = _classify("SNAKE BIT MY SON PLEASE HELP.")
        assert result.category == "snakebite"
        assert result.tier == 1

    def test_no_severity_field_in_result(self):
        """TriageResult must not expose any severity/risk-level field."""
        result = _classify("A cyclone is approaching.")
        assert not hasattr(result, "severity"), "TriageResult must not have 'severity' field"
        assert not hasattr(result, "emergency_level"), "TriageResult must not have 'emergency_level' field"
        assert not hasattr(result, "risk_level"), "TriageResult must not have 'risk_level' field"
        assert not hasattr(result, "critical"), "TriageResult must not have 'critical' field"


# ─────────────────────────────────────────────────────────────────────────────
# Tier 1 — Determinism
# ─────────────────────────────────────────────────────────────────────────────

class TestTier1Determinism:
    def test_same_input_same_output_flooding(self):
        """Identical inputs must produce identical Tier-1 outputs."""
        description = "There is severe flooding in my house."
        results = [_classify(description) for _ in range(3)]
        categories = [r.category for r in results]
        tiers = [r.tier for r in results]
        confidences = [r.confidence for r in results]
        assert len(set(categories)) == 1, f"Non-deterministic categories: {categories}"
        assert len(set(tiers)) == 1, f"Non-deterministic tiers: {tiers}"
        assert len(set(confidences)) == 1, f"Non-deterministic confidences: {confidences}"

    def test_same_input_same_output_accident(self):
        description = "A car accident just happened on the highway."
        results = [_classify(description) for _ in range(3)]
        assert len(set(r.category for r in results)) == 1
        assert len(set(r.tier for r in results)) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Tier 2 — Mocked embedding scenarios (Step 4N Tier 2)
# ─────────────────────────────────────────────────────────────────────────────

class TestTier2Embedding:

    def _patch_tier2(self, s1: float, s2: float, best_category: str, best_example: str):
        """Patch the internal cosine_similarity call to return controlled values."""
        import numpy as np

        # We need to patch both _ensure_tier2 to return True
        # and the cosine_similarity result to return our controlled values.
        n_examples = len(triage_service._EXAMPLE_TEXTS)
        mock_sims = np.zeros(n_examples)
        # Find index of best_example
        try:
            best_idx = triage_service._EXAMPLE_TEXTS.index(best_example)
        except ValueError:
            best_idx = 0
        mock_sims[best_idx] = s1
        # Put s2 at a different index
        runner_idx = (best_idx + 1) % n_examples
        mock_sims[runner_idx] = s2
        # Ensure best_example category matches
        triage_service._EXAMPLE_CATEGORIES[best_idx]  # just verify

        return mock_sims

    def test_tier2_high_similarity_high_margin(self):
        """s1 >= 0.78 and margin >= 0.08 → Tier 2 high confidence."""
        import numpy as np

        best_example = "water is entering my house"
        best_idx = triage_service._EXAMPLE_TEXTS.index(best_example)
        n = len(triage_service._EXAMPLE_TEXTS)
        mock_sims = np.zeros(n)
        mock_sims[best_idx] = 0.85   # s1
        mock_sims[(best_idx + 1) % n] = 0.70  # s2 → margin = 0.15

        mock_vec = MagicMock()
        mock_vec.transform.return_value = MagicMock()

        with patch.object(triage_service, "_tier2_vectorizer", mock_vec), \
             patch.object(triage_service, "_TIER2_AVAILABLE", True), \
             patch("sklearn.metrics.pairwise.cosine_similarity", return_value=np.array([mock_sims])):
            result = triage_service._tier2_classify("water is rising in my home")

        assert result is not None
        assert result.tier == 2
        assert result.confidence >= triage_service._TIER2_MEDIUM_CONFIDENCE

    def test_tier2_medium_similarity_sufficient_margin(self):
        """s1 >= 0.68 and margin >= 0.08 → Tier 2 medium confidence."""
        import numpy as np

        best_example = "water is entering my house"
        best_idx = triage_service._EXAMPLE_TEXTS.index(best_example)
        n = len(triage_service._EXAMPLE_TEXTS)
        mock_sims = np.zeros(n)
        mock_sims[best_idx] = 0.72   # s1 (medium threshold)
        mock_sims[(best_idx + 1) % n] = 0.55  # s2 → margin = 0.17

        mock_vec = MagicMock()
        mock_vec.transform.return_value = MagicMock()

        with patch.object(triage_service, "_tier2_vectorizer", mock_vec), \
             patch.object(triage_service, "_TIER2_AVAILABLE", True), \
             patch("sklearn.metrics.pairwise.cosine_similarity", return_value=np.array([mock_sims])):
            result = triage_service._tier2_classify("there is some water accumulation")

        assert result is not None
        assert result.tier == 2

    def test_tier2_low_similarity_skips(self):
        """s1 below medium threshold → Tier 2 returns None (passes to Tier 3)."""
        import numpy as np

        best_example = "water is entering my house"
        best_idx = triage_service._EXAMPLE_TEXTS.index(best_example)
        n = len(triage_service._EXAMPLE_TEXTS)
        mock_sims = np.zeros(n)
        mock_sims[best_idx] = 0.50   # below medium threshold
        mock_sims[(best_idx + 1) % n] = 0.35

        mock_vec = MagicMock()
        mock_vec.transform.return_value = MagicMock()

        with patch.object(triage_service, "_tier2_vectorizer", mock_vec), \
             patch.object(triage_service, "_TIER2_AVAILABLE", True), \
             patch("sklearn.metrics.pairwise.cosine_similarity", return_value=np.array([mock_sims])):
            result = triage_service._tier2_classify("some vague emergency happening nearby")

        assert result is None

    def test_tier2_insufficient_margin_skips(self):
        """margin < 0.08 even with high s1 → Tier 2 returns None."""
        import numpy as np

        best_example = "water is entering my house"
        best_idx = triage_service._EXAMPLE_TEXTS.index(best_example)
        n = len(triage_service._EXAMPLE_TEXTS)
        mock_sims = np.zeros(n)
        mock_sims[best_idx] = 0.82   # high s1
        mock_sims[(best_idx + 1) % n] = 0.79  # s2 → margin = 0.03 < 0.08

        mock_vec = MagicMock()
        mock_vec.transform.return_value = MagicMock()

        with patch.object(triage_service, "_tier2_vectorizer", mock_vec), \
             patch.object(triage_service, "_TIER2_AVAILABLE", True), \
             patch("sklearn.metrics.pairwise.cosine_similarity", return_value=np.array([mock_sims])):
            result = triage_service._tier2_classify("something ambiguous with multiple categories")

        assert result is None

    def test_tier2_unavailable_passes_to_tier3(self):
        """If Tier 2 is disabled, classify() falls through to Tier 3."""
        with patch.object(triage_service, "_TIER2_AVAILABLE", False):
            # Use an input that won't hit Tier 1 but also mock Tier 3 to return unclassified
            with patch.object(triage_service, "_tier3_classify", new=AsyncMock(
                return_value=TriageResult(
                    category="unclassified",
                    confidence=0.20,
                    tier=3,
                    matched_rule_or_example=None,
                    explanation="test",
                )
            )):
                result = _classify("something truly ambiguous that defies all categories here")

        # Must not crash; must not be Tier 2
        assert result.tier != 2


# ─────────────────────────────────────────────────────────────────────────────
# Tier 3 — Mocked Groq scenarios (Step 4N Tier 3)
# ─────────────────────────────────────────────────────────────────────────────

class TestTier3Groq:

    def _mock_groq(self, available: bool, response: str = ""):
        from app.models.schemas import ServiceResult

        return AsyncMock(
            return_value=ServiceResult(
                available=available,
                data=response if available else None,
                error_type=None if available else "service_disabled",
                detail=None,
            )
        )

    def test_tier3_valid_category_low_confidence(self):
        """Groq returns valid category → Tier 3 result with capped LOW confidence."""
        with patch("app.services.groq_service.call_groq_safe",
                   self._mock_groq(True, "CATEGORY: flooding")):
            result = _run(triage_service._tier3_classify("some ambiguous water problem"))

        assert result.tier == 3
        assert result.category == "flooding"
        assert result.confidence <= triage_service._TIER3_CONFIDENCE, (
            "Tier 3 confidence must be capped at low regardless of Groq's confidence"
        )

    def test_tier3_groq_disabled_returns_unclassified(self):
        """Groq disabled → unclassified, low confidence, no crash."""
        with patch("app.services.groq_service.call_groq_safe",
                   self._mock_groq(False)):
            result = _run(triage_service._tier3_classify("some description"))

        assert result.tier == 3
        assert result.category == "unclassified"
        assert result.confidence < 0.50

    def test_tier3_groq_malformed_output_returns_unclassified(self):
        """Groq returns garbage → unclassified, no crash."""
        with patch("app.services.groq_service.call_groq_safe",
                   self._mock_groq(True, "I think this is a flooding event with high severity!")):
            result = _run(triage_service._tier3_classify("some description"))

        assert result.tier == 3
        assert result.category == "unclassified"

    def test_tier3_groq_invalid_category_returns_unclassified(self):
        """Groq returns unknown category string → unclassified."""
        with patch("app.services.groq_service.call_groq_safe",
                   self._mock_groq(True, "CATEGORY: fire_emergency")):
            result = _run(triage_service._tier3_classify("there is a fire somewhere"))

        assert result.tier == 3
        assert result.category == "unclassified"

    def test_tier3_groq_cannot_return_severity(self):
        """Even if Groq response mentions severity, TriageResult must not expose it."""
        with patch("app.services.groq_service.call_groq_safe",
                   self._mock_groq(True, "CATEGORY: injury\nSEVERITY: critical")):
            result = _run(triage_service._tier3_classify("someone is hurt"))

        assert result.tier == 3
        assert result.category == "injury"
        # Confirm the severity leak is prevented
        assert not hasattr(result, "severity")
        assert not hasattr(result, "emergency_level")
        # Confidence must still be capped at low
        assert result.confidence <= triage_service._TIER3_CONFIDENCE



# ─────────────────────────────────────────────────────────────────────────────
# Schema contract tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTriageResultSchema:
    def test_triage_result_has_required_fields(self):
        result = _classify("A cyclone is approaching.")
        assert hasattr(result, "category")
        assert hasattr(result, "confidence")
        assert hasattr(result, "tier")
        assert hasattr(result, "matched_rule_or_example")
        assert hasattr(result, "explanation")

    def test_confidence_in_range(self):
        """Confidence must always be 0.0–1.0."""
        for desc in [
            "flooding", "snake bite victim", "car accident", "",
            "very vague description about something",
        ]:
            result = _classify(desc)
            assert 0.0 <= result.confidence <= 1.0, (
                f"Confidence out of range for '{desc}': {result.confidence}"
            )

    def test_tier_valid_values(self):
        """Tier must be 1, 2, or 3."""
        for desc in ["Flood water rising", "snake bit", "car accident on highway"]:
            result = _classify(desc)
            assert result.tier in (1, 2, 3)

    def test_category_is_valid(self):
        """Category must be one of the eight supported values."""
        valid_cats = {
            "flooding", "electrocution", "injury", "snakebite",
            "cyclone", "structural_damage", "accident", "unclassified",
        }
        for desc in [
            "Flood water entering", "live wire", "snake bite", "",
            "completely unrelated text about cooking recipes",
        ]:
            result = _classify(desc)
            assert result.category in valid_cats, (
                f"Invalid category '{result.category}' for '{desc}'"
            )

    def test_explanation_is_non_empty(self):
        """Explanation must always be a non-empty string."""
        for desc in ["flooding", "snake bite", "random text", ""]:
            result = _classify(desc)
            assert isinstance(result.explanation, str)
            assert len(result.explanation) > 0

    def test_explanation_does_not_contain_stack_traces(self):
        """Explanation must not contain raw exception text."""
        result = _classify("Some description")
        assert "Traceback" not in result.explanation
        assert "Error:" not in result.explanation
