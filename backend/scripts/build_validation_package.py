"""
Build a zip archive for external validation and verification.

    cd backend
    python scripts/build_validation_package.py
    python scripts/build_validation_package.py --output ../ResQ-AI-validation.zip
"""

from __future__ import annotations

import argparse
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
DOCS = ROOT / "docs"
OUTPUT_DEFAULT = ROOT / "ResQ-AI-validation-package.zip"

SKIP_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".next",
    "venv",
    ".venv",
    "downloads",
}
SKIP_FILE_SUFFIXES = {".pyc", ".pyo", ".joblib", ".kml", ".zip", ".sst", ".meta"}
SKIP_FILE_NAMES = {
    ".env",
    ".env.local",
    "firebase-service-account.json",
}
SKIP_PATH_FRAGMENTS = (
    "/data/downloads/",
    "/data/sources/kml/",
    "/data/models/",
    "/Screenshots/",
)

INCLUDE_PATHS = [
    "README.md",
    "docs/",
    "backend/README.md",
    "backend/requirements.txt",
    "backend/run.py",
    "backend/.env.example",
    "backend/app/",
    "backend/tests/",
    "backend/supabase/",
    "backend/data/DATA_SOURCES.md",
    "backend/data/sources/README.md",
    "backend/data/sources/metadata/",
    "backend/data/triage_category_definitions.json",
    "backend/data/triage_eval_gold.json",
    "backend/data/triage_ml_training.json",
    "backend/data/report_ml_training.json",
    "backend/data/knowledge_assets.json",
    "backend/data/community_reports.json",
    "backend/data/shelters.json",
    "backend/data/hospitals_phc_hyderabad.json",
    "backend/data/hospitals_hyd_municipal_hyderabad.json",
    "backend/data/hospitals_hotosm_hyderabad.json",
    "backend/scripts/run_triage_eval.py",
    "backend/scripts/build_triage_eval_gold.py",
    "backend/scripts/train_models.py",
    "backend/scripts/train_triage_classifier.py",
    "backend/scripts/apply_supabase_schema.py",
    "backend/scripts/verify_supabase.py",
    "backend/scripts/scan_secrets.py",
    "backend/scripts/build_validation_package.py",
    "frontend/.env.local.example",
    "frontend/vercel.json",
    "frontend/src/lib/types.ts",
    "frontend/src/lib/api.ts",
    "frontend/src/components/AssessmentResultPanel.tsx",
    "frontend/src/app/api/cron/keepalive/route.ts",
    "frontend/src/app/api/health/route.ts",
    "frontend/src/lib/keepalive.ts",
    ".github/workflows/keepalive.yml",
]

MANIFEST = """# ResQ-AI — External validation package

Generated: {generated_at}

This archive contains code, tests, gold-label data, and documentation needed to
**validate and verify** ResQ-AI without secrets or large binary artifacts.

## What is included

| Area | Contents |
|------|----------|
| **Triage pipeline** | `backend/app/services/triage_service.py`, `triage_ml_service.py`, `app/ml/` |
| **Orchestrator** | `emergency_orchestrator.py`, `confidence_service.py`, `action_planner_service.py` |
| **Gold benchmark** | `backend/data/triage_eval_gold.json` ({gold_cases} cases) |
| **ML training data** | `triage_ml_training.json`, `report_ml_training.json` |
| **Eval tooling** | `scripts/run_triage_eval.py`, `scripts/train_models.py` |
| **Tests** | `backend/tests/` (pytest suite) |
| **Schema** | `backend/supabase/*.sql`, `SCHEMA_ERD.md` |
| **Docs** | `docs/validation-data-checklist.md`, `resq-ai-fix-algorithms.md`, etc. |

## Excluded (by design)

- `.env`, credentials, API keys
- `node_modules`, `.next`, `venv`, `__pycache__`
- Trained `.joblib` models (regenerate with `train_models.py`)
- Raw KML / HDX zip downloads (see `DATA_SOURCES.md`)

## Quick verification (no API keys required)

```powershell
cd backend
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
python -m pytest tests/test_triage_eval_gold.py tests/test_triage_ml_service.py tests/test_report_ml.py tests/test_step4_triage.py tests/test_step6_confidence.py tests/test_step7_orchestrator.py -q
python scripts/train_models.py --force
python scripts/run_triage_eval.py
```

## With API keys (full integration)

Copy `backend/.env.example` to `backend/.env` and fill in Groq, OpenWeather, Supabase.
Then run the full suite: `python -m pytest -q`

## File count

- Files in archive: {file_count}
- Uncompressed size: {size_kb} KB

See `docs/validation-data-checklist.md` for the full validation framework.
"""


def should_skip(path: Path) -> bool:
    if path.name in SKIP_FILE_NAMES:
        return True
    if path.suffix.lower() in SKIP_FILE_SUFFIXES:
        return True
    normalized = path.as_posix().lower()
    if any(fragment in normalized for fragment in SKIP_PATH_FRAGMENTS):
        return True
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def collect_files() -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()

    for rel in INCLUDE_PATHS:
        source = ROOT / rel
        if not source.exists():
            continue
        if source.is_file():
            if not should_skip(source):
                seen.add(source.resolve())
                files.append(source)
            continue

        for path in sorted(source.rglob("*")):
            if not path.is_file() or should_skip(path):
                continue
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                files.append(path)

    return sorted(files, key=lambda p: p.as_posix().lower())


def gold_case_count() -> int:
    path = BACKEND / "data" / "triage_eval_gold.json"
    if not path.exists():
        return 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    return len(payload.get("cases", []))


def build_zip(output: Path) -> tuple[int, int]:
    files = collect_files()
    output.parent.mkdir(parents=True, exist_ok=True)

    total_bytes = 0
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            arcname = path.relative_to(ROOT).as_posix()
            archive.write(path, arcname)
            total_bytes += path.stat().st_size

        readme = MANIFEST.format(
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            gold_cases=gold_case_count(),
            file_count=len(files),
            size_kb=round(total_bytes / 1024),
        )
        archive.writestr("VALIDATION_PACKAGE.md", readme)

    return len(files), output.stat().st_size


def main() -> None:
    parser = argparse.ArgumentParser(description="Build external validation zip package")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DEFAULT,
        help=f"Output zip path (default: {OUTPUT_DEFAULT.name})",
    )
    args = parser.parse_args()

    count, size = build_zip(args.output.resolve())
    print(f"Created: {args.output.resolve()}")
    print(f"  files: {count}")
    print(f"  size:  {size / 1024:.1f} KB ({size / (1024 * 1024):.2f} MB)")


if __name__ == "__main__":
    main()
