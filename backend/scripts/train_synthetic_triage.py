"""
Train a ≥1M-parameter hashed linear model on synthetic triage JSONL.

This writes a *separate* artifact and does not replace the production
TF-IDF logistic model used in the live cascade.

    cd backend
    python scripts/train_synthetic_triage.py
    python scripts/train_synthetic_triage.py --label-field category
    python scripts/train_synthetic_triage.py --label-field tier --limit 50000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.paths import SYNTHETIC_TRIAGE_JSONL
from app.ml.synthetic_triage import MIN_PARAMS_1M, train_hashed_model


def main() -> None:
    parser = argparse.ArgumentParser(description="Train ≥1M-parameter synthetic triage model")
    parser.add_argument("--data", type=Path, default=SYNTHETIC_TRIAGE_JSONL)
    parser.add_argument("--label-field", choices=("category", "tier"), default="category")
    parser.add_argument("--limit", type=int, default=None, help="Optional row cap")
    parser.add_argument("--batch-size", type=int, default=8192)
    parser.add_argument("--min-params", type=int, default=MIN_PARAMS_1M)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.data.exists():
        raise SystemExit(
            f"Missing {args.data}. Run: python scripts/generate_synthetic_triage.py"
        )

    summary = train_hashed_model(
        data_path=args.data,
        label_field=args.label_field,
        limit=args.limit,
        batch_size=args.batch_size,
        min_params=args.min_params,
    )
    if args.json:
        print(json.dumps(summary, indent=2))
        return
    print("Synthetic model (not used by live cascade):")
    print(f"  path   → {summary['path']}")
    print(f"  rows   → {summary['training_rows']}")
    print(f"  params → {summary['parameter_count']:,}")
    print(f"  labels → {summary['label_field']}: {', '.join(summary['classes'])}")


if __name__ == "__main__":
    main()
