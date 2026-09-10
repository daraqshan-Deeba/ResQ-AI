"""
Train and persist all ResQ AI sklearn models.

    cd backend
    python scripts/train_models.py
    python scripts/train_models.py --force
    python scripts/train_models.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.reports import reset_report_model, train_report_model, training_stats as report_stats
from app.ml.triage import reset_triage_model, train_triage_model, training_stats as triage_stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Train persisted ML models")
    parser.add_argument("--force", action="store_true", help="Retrain even if .joblib exists")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    reset_triage_model()
    reset_report_model()

    triage_path = train_triage_model(force=args.force)
    report_path = train_report_model(force=args.force)

    reset_triage_model()
    reset_report_model()

    summary = {
        "triage": triage_stats(),
        "reports": report_stats(),
        "artifacts": {
            "triage_classifier": str(triage_path),
            "report_classifier": str(report_path),
        },
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print("Trained models:")
        print(f"  triage  → {triage_path}")
        print(f"           rows={summary['triage']['total_training_rows']} classes={summary['triage']['classes']}")
        print(f"  reports → {report_path}")
        print(f"           rows={summary['reports']['total_training_rows']} classes={summary['reports']['classes']}")


if __name__ == "__main__":
    main()
