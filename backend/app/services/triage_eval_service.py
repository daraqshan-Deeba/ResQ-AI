"""
Gold-label triage evaluation — load benchmark cases and score classification accuracy.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.models.schemas import EmergencyCategory, TriageResult
from app.services import triage_service

logger = logging.getLogger("resq.triage_eval")

DEFAULT_GOLD_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "triage_eval_gold.json"
)

EvalSuite = Literal["tier1", "tier2", "negative", "historical", "multilingual"]


@dataclass
class GoldCase:
    id: str
    text: str
    expected_category: EmergencyCategory
    suite: EvalSuite
    notes: str | None = None
    source: str | None = None
    max_tier: int | None = None  # tier1 suite expects tier == 1
    min_tier: int | None = None  # tier2 suite expects tier >= 2 if not tier1


@dataclass
class EvalFailure:
    case_id: str
    text: str
    expected_category: str
    actual_category: str
    actual_tier: int
    suite: str
    notes: str | None = None


@dataclass
class EvalReport:
    total: int
    correct: int
    accuracy: float
    by_suite: dict[str, dict[str, Any]]
    by_category: dict[str, dict[str, Any]]
    failures: list[EvalFailure] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "correct": self.correct,
            "accuracy": round(self.accuracy, 4),
            "by_suite": self.by_suite,
            "by_category": self.by_category,
            "failures": [
                {
                    "id": f.case_id,
                    "text": f.text,
                    "expected": f.expected_category,
                    "actual": f.actual_category,
                    "tier": f.actual_tier,
                    "suite": f.suite,
                    "notes": f.notes,
                }
                for f in self.failures
            ],
        }


def load_gold_dataset(path: Path | str | None = None) -> list[GoldCase]:
    dataset_path = Path(path) if path else DEFAULT_GOLD_PATH
    raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases: list[GoldCase] = []
    for row in raw.get("cases", []):
        cases.append(
            GoldCase(
                id=row["id"],
                text=row["text"],
                expected_category=row["expected_category"],
                suite=row["suite"],
                notes=row.get("notes"),
                source=row.get("source"),
                max_tier=row.get("max_tier"),
                min_tier=row.get("min_tier"),
            )
        )
    return cases


def _case_passes(case: GoldCase, result: TriageResult) -> bool:
    if result.category != case.expected_category:
        return False
    if case.max_tier is not None and result.tier > case.max_tier:
        return False
    if case.min_tier is not None and result.tier < case.min_tier:
        return False
    return True


async def evaluate_case(case: GoldCase) -> tuple[bool, TriageResult]:
    result = await triage_service.classify(case.text)
    return _case_passes(case, result), result


async def run_eval(
    cases: list[GoldCase] | None = None,
    *,
    gold_path: Path | str | None = None,
) -> EvalReport:
    if cases is None:
        cases = load_gold_dataset(gold_path)

    failures: list[EvalFailure] = []
    suite_stats: dict[str, dict[str, int]] = {}
    category_stats: dict[str, dict[str, int]] = {}
    correct = 0

    for case in cases:
        passed, result = await evaluate_case(case)
        if passed:
            correct += 1
        else:
            failures.append(
                EvalFailure(
                    case_id=case.id,
                    text=case.text,
                    expected_category=case.expected_category,
                    actual_category=result.category,
                    actual_tier=result.tier,
                    suite=case.suite,
                    notes=case.notes,
                )
            )

        suite_stats.setdefault(case.suite, {"total": 0, "correct": 0})
        suite_stats[case.suite]["total"] += 1
        if passed:
            suite_stats[case.suite]["correct"] += 1

        cat = case.expected_category
        category_stats.setdefault(cat, {"total": 0, "correct": 0})
        category_stats[cat]["total"] += 1
        if passed:
            category_stats[cat]["correct"] += 1

    total = len(cases)
    by_suite = {
        suite: {
            **stats,
            "accuracy": round(stats["correct"] / stats["total"], 4) if stats["total"] else 0.0,
        }
        for suite, stats in sorted(suite_stats.items())
    }
    by_category = {
        cat: {
            **stats,
            "accuracy": round(stats["correct"] / stats["total"], 4) if stats["total"] else 0.0,
        }
        for cat, stats in sorted(category_stats.items())
    }

    return EvalReport(
        total=total,
        correct=correct,
        accuracy=correct / total if total else 0.0,
        by_suite=by_suite,
        by_category=by_category,
        failures=failures,
    )


def format_report(report: EvalReport) -> str:
    lines = [
        f"Triage gold eval: {report.correct}/{report.total} correct ({report.accuracy * 100:.1f}%)",
        "",
        "By suite:",
    ]
    for suite, stats in report.by_suite.items():
        lines.append(
            f"  {suite}: {stats['correct']}/{stats['total']} ({stats['accuracy'] * 100:.1f}%)"
        )
    lines.append("")
    lines.append("By expected category:")
    for cat, stats in report.by_category.items():
        lines.append(
            f"  {cat}: {stats['correct']}/{stats['total']} ({stats['accuracy'] * 100:.1f}%)"
        )
    if report.failures:
        lines.append("")
        lines.append(f"Failures ({len(report.failures)}):")
        for failure in report.failures[:20]:
            lines.append(
                f"  [{failure.suite}] {failure.case_id}: expected={failure.expected_category} "
                f"got={failure.actual_category} (tier {failure.actual_tier}) — {failure.text[:70]}"
            )
        if len(report.failures) > 20:
            lines.append(f"  … and {len(report.failures) - 20} more")
    return "\n".join(lines)
