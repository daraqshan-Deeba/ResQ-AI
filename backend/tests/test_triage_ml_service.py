import asyncio
from unittest.mock import AsyncMock, patch

from app.models.schemas import TriageResult
from app.services import triage_service
from app.ml.triage import reset_triage_model
from app.services.triage_ml_service import (
    ml_classifier_available,
    reset_ml_classifier,
    training_stats,
)


def setup_function():
    reset_ml_classifier()
    reset_triage_model()


def test_ml_classifier_trains():
    assert ml_classifier_available() is True
    stats = training_stats()
    assert stats["total_training_rows"] >= 50
    assert stats["ml_available"] is True


def test_classify_ml_hindi_flooding():
    result = asyncio.run(triage_service.classify("ghar mein pani tez badh raha hai"))
    assert result.category == "flooding"
    assert result.tier in (1, 2)


def test_classify_ml_telugu_snakebite():
    result = asyncio.run(triage_service.classify("paamu kadithindi garden lo"))
    assert result.category == "snakebite"
    assert result.tier in (1, 2)


def test_classify_ml_devanagari_injury():
    result = asyncio.run(triage_service.classify("खून बह रहा है"))
    assert result.category == "injury"
    assert result.tier in (1, 2)


def test_triage_cascade_uses_ml_before_groq():
    async def _run():
        with patch(
            "app.services.triage_service._tier3_classify",
            new=AsyncMock(
                return_value=TriageResult(
                    category="unclassified",
                    confidence=0.2,
                    tier=3,
                    matched_rule_or_example=None,
                    explanation="should not be called",
                )
            ),
        ) as mock_t3:
            result = await triage_service.classify("tufan aa raha hai hamare area mein")
            assert result.category == "cyclone"
            assert result.tier in (1, 2)
            mock_t3.assert_not_called()

    asyncio.run(_run())
