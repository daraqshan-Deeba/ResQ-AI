"""
Run gold-label triage evaluation and print accuracy report.

    cd backend
    python scripts/run_triage_eval.py
    python scripts/run_triage_eval.py --json
    python scripts/run_triage_eval.py --fail-on-error
    python scripts/run_triage_eval.py --suite tier1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.schemas import TriageResult
from app.services.triage_eval_service import (
    DEFAULT_GOLD_PATH,
    format_report,
    load_gold_dataset,
    run_eval,
)


def _mock_tier3_unclassified() -> TriageResult:
    return TriageResult(
        category="unclassified",
        confidence=0.20,
        tier=3,
        matched_rule_or_example=None,
        explanation="Mocked Tier 3 for deterministic negative/historical eval.",
    )


async def _main_async(args: argparse.Namespace) -> int:
    cases = load_gold_dataset(args.gold)
    if args.suite:
        cases = [c for c in cases if c.suite == args.suite]

    # Mock Tier 3 so negatives/historical cases are deterministic without Groq.
    with patch(
        "app.services.triage_service._tier3_classify",
        new=AsyncMock(return_value=_mock_tier3_unclassified()),
    ):
        report = await run_eval(cases)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(format_report(report))

    if args.fail_on_error and report.failures:
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run triage gold-label evaluation")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD_PATH, help="Path to gold JSON")
    parser.add_argument("--suite", choices=["tier1", "tier2", "negative", "historical"], help="Filter suite")
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    parser.add_argument("--fail-on-error", action="store_true", help="Exit 1 if any case fails")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_main_async(args)))


if __name__ == "__main__":
    main()
