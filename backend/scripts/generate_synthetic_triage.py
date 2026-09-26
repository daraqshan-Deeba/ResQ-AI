"""
Generate a gold-holdout-safe synthetic triage JSONL corpus.

    cd backend
    python scripts/generate_synthetic_triage.py
    python scripts/generate_synthetic_triage.py --count 1000000 --seed 42
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.paths import SYNTHETIC_TRIAGE_JSONL
from app.ml.synthetic_triage import generate_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic triage JSONL")
    parser.add_argument("--count", type=int, default=1_000_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output",
        type=Path,
        default=SYNTHETIC_TRIAGE_JSONL,
        help="Target .jsonl or .jsonl.gz path",
    )
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = generate_dataset(
        count=args.count,
        seed=args.seed,
        output=args.output,
        sample_size=args.sample_size,
    )
    payload = {
        "count": result.count,
        "path": str(result.path),
        "sample_path": str(result.sample_path),
        "manifest_path": str(result.manifest_path),
        "by_category": result.by_category,
        "by_language": result.by_language,
        "by_tier": result.by_tier,
    }
    if args.json:
        print(json.dumps(payload, indent=2))
        return
    print(f"Wrote {result.count} rows → {result.path}")
    print(f"Sample  → {result.sample_path}")
    print(f"Manifest → {result.manifest_path}")
    print(f"By category: {result.by_category}")
    print(f"By tier: {result.by_tier}")


if __name__ == "__main__":
    main()
