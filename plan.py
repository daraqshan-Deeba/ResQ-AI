#!/usr/bin/env python3
"""
ResQ-AI validation plan — generate and execute.

The triage cascade implementation lives in:
  backend/app/services/triage_service.py

This script builds a verification plan, prints it, then runs each step.

    python plan.py              # generate + execute full plan
    python plan.py --dry-run    # print plan only
    python plan.py --json       # machine-readable output
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
PLAN_OUTPUT = ROOT / "plan_output.json"


@dataclass
class PlanStep:
    id: str
    title: str
    command: list[str]
    cwd: Path
    optional: bool = False


@dataclass
class StepResult:
    id: str
    title: str
    status: str  # passed | failed | skipped
    returncode: int | None = None
    detail: str = ""


@dataclass
class ValidationPlan:
    generated_at: str
    steps: list[PlanStep] = field(default_factory=list)
    results: list[StepResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        steps = []
        for s in self.steps:
            row = asdict(s)
            row["cwd"] = str(s.cwd)
            steps.append(row)
        return {
            "generated_at": self.generated_at,
            "steps": steps,
            "results": [asdict(r) for r in self.results],
        }


def build_plan() -> ValidationPlan:
    py = sys.executable
    return ValidationPlan(
        generated_at=datetime.now(timezone.utc).isoformat(),
        steps=[
            PlanStep(
                id="train_models",
                title="Train persisted triage + report ML models",
                command=[py, "scripts/train_models.py", "--force"],
                cwd=BACKEND,
            ),
            PlanStep(
                id="triage_eval",
                title="Run gold-label triage evaluation (all suites)",
                command=[py, "scripts/run_triage_eval.py", "--fail-on-error"],
                cwd=BACKEND,
            ),
            PlanStep(
                id="pytest_core",
                title="Pytest — triage, ML, orchestrator, confidence",
                command=[
                    py,
                    "-m",
                    "pytest",
                    "tests/test_triage_eval_gold.py",
                    "tests/test_triage_ml_service.py",
                    "tests/test_report_ml.py",
                    "tests/test_step4_triage.py",
                    "tests/test_step6_confidence.py",
                    "tests/test_step7_orchestrator.py",
                    "tests/test_keepalive.py",
                    "-q",
                    "--tb=line",
                ],
                cwd=BACKEND,
            ),
            PlanStep(
                id="sample_triage",
                title="Sample triage classifications (live cascade)",
                command=[py, "scripts/run_plan_samples.py"],
                cwd=BACKEND,
            ),
        ],
    )


def run_step(step: PlanStep) -> StepResult:
    try:
        proc = subprocess.run(
            step.command,
            cwd=step.cwd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        output_tail = (proc.stdout or "") + (proc.stderr or "")
        tail = "\n".join(output_tail.strip().splitlines()[-8:])
        if proc.returncode == 0:
            return StepResult(
                id=step.id,
                title=step.title,
                status="passed",
                returncode=0,
                detail=tail,
            )
        return StepResult(
            id=step.id,
            title=step.title,
            status="failed",
            returncode=proc.returncode,
            detail=tail or f"exit code {proc.returncode}",
        )
    except subprocess.TimeoutExpired:
        return StepResult(
            id=step.id,
            title=step.title,
            status="failed",
            returncode=None,
            detail="timed out after 600s",
        )
    except Exception as exc:
        return StepResult(
            id=step.id,
            title=step.title,
            status="failed",
            returncode=None,
            detail=str(exc),
        )


def execute_plan(plan: ValidationPlan, *, dry_run: bool = False) -> ValidationPlan:
    if dry_run:
        return plan

    for step in plan.steps:
        print(f"\n>> {step.title} ({step.id})")
        result = run_step(step)
        plan.results.append(result)
        icon = "OK" if result.status == "passed" else "FAIL"
        print(f"  {icon} {result.status}")
        if result.detail:
            for line in result.detail.splitlines():
                print(f"    {line}")

    PLAN_OUTPUT.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and execute ResQ-AI validation plan")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    parser.add_argument("--json", action="store_true", help="Print plan/results as JSON")
    args = parser.parse_args()

    if not BACKEND.is_dir():
        print("ERROR: backend/ directory not found.", file=sys.stderr)
        return 1

    plan = build_plan()

    if args.json and args.dry_run:
        print(json.dumps(plan.to_dict(), indent=2))
        return 0

    if not args.json:
        print("ResQ-AI validation plan")
        print(f"  generated: {plan.generated_at}")
        print(f"  steps: {len(plan.steps)}")
        for i, step in enumerate(plan.steps, 1):
            cmd = " ".join(step.command)
            print(f"  {i}. [{step.id}] {step.title}")
            print(f"     -> {cmd}")

    if args.dry_run:
        print("\n(dry-run — no steps executed)")
        return 0

    plan = execute_plan(plan)

    passed = sum(1 for r in plan.results if r.status == "passed")
    failed = sum(1 for r in plan.results if r.status == "failed")
    summary = {
        "passed": passed,
        "failed": failed,
        "total": len(plan.results),
        "output_file": str(PLAN_OUTPUT),
    }

    if args.json:
        payload = plan.to_dict()
        payload["summary"] = summary
        print(json.dumps(payload, indent=2))
    else:
        print(f"\nDone: {passed}/{len(plan.results)} passed")
        print(f"Full report: {PLAN_OUTPUT}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
