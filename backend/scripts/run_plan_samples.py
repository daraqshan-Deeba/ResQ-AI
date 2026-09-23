"""Run sample triage classifications for plan.py verification."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.schemas import TriageResult
from app.services import triage_service


SAMPLES = [
    "Water is entering my house and rising fast",
    "Live wire down near standing water",
    "Road accident on NH65 two cars involved",
    "Snake bite on leg need antivenom",
    "It was raining yesterday nothing urgent",
]


async def _run() -> list[dict]:
    mock_t3 = TriageResult(
        category="unclassified",
        confidence=0.20,
        tier=3,
        matched_rule_or_example=None,
        explanation="mocked for sample run",
    )
    results = []
    with patch(
        "app.services.triage_service._tier3_classify",
        new=AsyncMock(return_value=mock_t3),
    ):
        for text in SAMPLES:
            triage = await triage_service.classify(text)
            results.append(
                {
                    "text": text,
                    "category": triage.category,
                    "tier": triage.tier,
                    "confidence": triage.confidence,
                    "matched": triage.matched_rule_or_example,
                }
            )
    return results


def main() -> None:
    results = asyncio.run(_run())
    print(json.dumps({"samples": results}, indent=2))


if __name__ == "__main__":
    main()
