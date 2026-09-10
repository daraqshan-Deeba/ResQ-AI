"""
Train and report metrics for the multilingual triage ML classifier.

    cd backend
    python scripts/train_triage_classifier.py
    python scripts/train_triage_classifier.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.triage import training_stats
from app.services.triage_eval_service import load_gold_dataset, run_eval


async def _eval_multilingual():
    from unittest.mock import AsyncMock, patch

    from app.models.schemas import TriageResult
    from app.services import triage_service

    def mock_t3():
        return TriageResult(
            category="unclassified",
            confidence=0.2,
            tier=3,
            matched_rule_or_example=None,
            explanation="mock",
        )

    cases = [c for c in load_gold_dataset() if c.suite == "multilingual"]
    with patch(
        "app.services.triage_service._tier3_classify",
        new=AsyncMock(return_value=mock_t3()),
    ):
        return await run_eval(cases)


def main() -> None:
    parser = argparse.ArgumentParser(description="Report triage ML classifier training stats")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    stats = training_stats()

    import asyncio

    ml_eval = asyncio.run(_eval_multilingual())

    report = {
        **stats,
        "multilingual_eval": ml_eval.to_dict(),
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("Triage ML classifier")
        print(f"  Training rows: {stats['total_training_rows']}")
        print(f"  ML available: {stats['ml_available']}")
        print(f"  Classes: {', '.join(stats['classes'])}")
        print(f"  By language: {stats['by_language']}")
        print(
            f"  Multilingual eval: {ml_eval.correct}/{ml_eval.total} "
            f"({ml_eval.accuracy * 100:.1f}%)"
        )
        if ml_eval.failures:
            print("  Sample failures:")
            for failure in ml_eval.failures[:5]:
                print(f"    - {failure.text[:60]} → expected {failure.expected_category}, got {failure.actual_category}")


if __name__ == "__main__":
    main()
