"""
Gold-label triage evaluation — regression gate for classification accuracy.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.models.schemas import TriageResult
from app.services.triage_eval_service import load_gold_dataset, run_eval
from app.ml.triage import reset_triage_model
from app.services.triage_ml_service import reset_ml_classifier


def _mock_tier3_unclassified() -> TriageResult:
    return TriageResult(
        category="unclassified",
        confidence=0.20,
        tier=3,
        matched_rule_or_example=None,
        explanation="Mocked Tier 3 for deterministic eval.",
    )


def _run_eval(suite: str | None = None):
    reset_ml_classifier()
    reset_triage_model()
    cases = load_gold_dataset()
    if suite:
        cases = [c for c in cases if c.suite == suite]

    async def _inner():
        with patch(
            "app.services.triage_service._tier3_classify",
            new=AsyncMock(return_value=_mock_tier3_unclassified()),
        ):
            return await run_eval(cases)

    return asyncio.run(_inner())


def test_gold_dataset_loads():
    cases = load_gold_dataset()
    assert len(cases) >= 90
    assert all(c.id and c.text and c.expected_category for c in cases)


def test_gold_eval_tier1_suite():
    report = _run_eval("tier1")
    assert report.accuracy >= 0.95, report.failures[:5]


def test_gold_eval_tier2_suite():
    report = _run_eval("tier2")
    assert report.accuracy >= 0.90, report.failures[:5]


def test_gold_eval_negative_suite():
    report = _run_eval("negative")
    assert report.accuracy >= 0.90, report.failures[:5]


def test_gold_eval_historical_suite():
    report = _run_eval("historical")
    assert report.accuracy >= 0.80, report.failures[:5]


def test_gold_eval_multilingual_suite():
    report = _run_eval("multilingual")
    assert report.total >= 50
    assert report.accuracy >= 0.85, report.failures[:8]


def test_gold_eval_overall():
    report = _run_eval()
    assert report.accuracy >= 0.90, report.failures[:10]
