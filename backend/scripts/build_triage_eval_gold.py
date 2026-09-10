"""
Generate backend/data/triage_eval_gold.json from curated case lists.

    cd backend
    python scripts/build_triage_eval_gold.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "triage_eval_gold.json"

TIER1_CASES: dict[str, list[str]] = {
    "flooding": [
        "water is rising fast",
        "house is flooding",
        "water entering my home",
        "flash flood",
        "water level rising quickly",
        "trapped by floodwater",
        "street is underwater",
        "heavy flooding in my area",
        "car stuck in flood water",
        "basement is flooding",
    ],
    "electrocution": [
        "live wire down",
        "electric shock",
        "power line fell",
        "touched a live wire",
        "transformer sparking",
        "downed power cable",
        "wire sparking in water",
        "exposed wiring near water",
        "smell of burning wires",
        "shocked by appliance",
    ],
    "injury": [
        "deep cut",
        "broken bone",
        "head injury",
        "unconscious person",
        "severe bleeding",
        "bone sticking out",
        "someone fell and is hurt",
        "spinal injury",
        "person not responding",
        "lost a lot of blood",
    ],
    "snakebite": [
        "snake bite",
        "bitten by a snake",
        "venomous snake",
        "need antivenom",
        "fang marks on skin",
        "snake bit my hand",
        "someone was bitten by a snake",
        "snake attacked",
        "swelling after snake bite",
        "cobra bite",
    ],
    "cyclone": [
        "cyclone warning",
        "storm surge",
        "roof blown off",
        "cyclone alert issued",
        "strong winds approaching",
        "trees falling due to wind",
        "extreme wind speed",
        "cyclone hitting our area",
        "wind damage to house",
        "storm approaching fast",
    ],
    "structural_damage": [
        "building collapsed",
        "roof caved in",
        "trapped under rubble",
        "ceiling fell",
        "house is collapsing",
        "wall came down",
        "structure is unstable",
        "debris blocking the door",
        "trapped inside damaged building",
        "wall crack spreading",
    ],
    "accident": [
        "car accident",
        "road accident",
        "hit by a car",
        "motorcycle accident",
        "multi-car crash",
        "pedestrian hit by vehicle",
        "truck collision",
        "accident on the highway",
        "vehicle overturned",
        "vehicle collision",
    ],
}

TIER2_CASES: dict[str, list[str]] = {
    "flooding": [
        "our ground floor is under water",
        "the river has overflowed into the neighbourhood",
        "water came in through the door during the storm",
    ],
    "electrocution": [
        "sparks are coming from a broken wire",
        "an electric pole has fallen in the street",
        "the transformer is sparking dangerously",
    ],
    "injury": [
        "someone fell from a height and is seriously hurt",
        "the victim has severe head injuries",
        "someone is bleeding very heavily from a wound",
    ],
    "snakebite": [
        "a person was attacked by a cobra",
        "someone stepped on a snake and got bitten",
    ],
    "cyclone": [
        "the tropical storm is intensifying rapidly",
        "cyclone storm surge is flooding coastal areas",
    ],
    "structural_damage": [
        "the building has partially collapsed",
        "the roof of our house fell in",
        "there are people trapped under building rubble",
    ],
    "accident": [
        "two vehicles have crashed into each other",
        "a pedestrian was hit by a speeding car",
        "there is a serious crash on the main road",
    ],
}

NEGATIVE_CASES = [
    ("neg-001", "the accident happened last year"),
    ("neg-002", "I read about a flood in the news"),
    ("neg-003", "just checking if this app works"),
    ("neg-004", "what should I do if there is ever a flood"),
    ("neg-005", "there was a fire drill at work today"),
    ("neg-006", "testing this input"),
    ("neg-007", "snake plant in my garden"),
    ("neg-008", "water bottle fell on the floor"),
    ("neg-009", "barbed wire fence needs repair"),
    ("neg-010", "I saw a documentary about cyclones"),
]

HISTORICAL_CASES = [
    ("hist-001", "years ago I had a car accident"),
    ("hist-002", "the accident happened last month"),
    ("hist-003", "months ago there was flooding in Chennai"),
    ("hist-004", "used to worry about cyclones when I lived on the coast"),
    ("hist-005", "weeks ago my neighbor had a minor cut"),
]

ML_TRAINING_JSON = Path(__file__).resolve().parents[1] / "data" / "triage_ml_training.json"


def _multilingual_eval_cases() -> list[dict]:
    if not ML_TRAINING_JSON.exists():
        return []
    payload = json.loads(ML_TRAINING_JSON.read_text(encoding="utf-8"))
    cases: list[dict] = []
    for idx, item in enumerate(payload.get("examples", []), start=1):
        text = (item.get("text") or "").strip()
        category = item.get("category")
        if not text or not category:
            continue
        lang = item.get("language", "unknown")
        cases.append(
            {
                "id": f"ml-{lang}-{idx:03d}",
                "text": text,
                "expected_category": category,
                "suite": "multilingual",
                "source": "triage_ml_training.json",
            }
        )
    return cases


def main() -> None:
    cases: list[dict] = []

    for category, phrases in TIER1_CASES.items():
        for idx, text in enumerate(phrases, start=1):
            cases.append(
                {
                    "id": f"{category[:4]}-t1-{idx:02d}",
                    "text": text,
                    "expected_category": category,
                    "suite": "tier1",
                    "max_tier": 1,
                    "source": "ResQ_AI_Data_Reference.md#tier1",
                }
            )

    for category, phrases in TIER2_CASES.items():
        for idx, text in enumerate(phrases, start=1):
            cases.append(
                {
                    "id": f"{category[:4]}-t2-{idx:02d}",
                    "text": text,
                    "expected_category": category,
                    "suite": "tier2",
                    "source": "triage_service._TIER2_EXAMPLES",
                }
            )

    for case_id, text in NEGATIVE_CASES:
        cases.append(
            {
                "id": case_id,
                "text": text,
                "expected_category": "unclassified",
                "suite": "negative",
                "source": "ResQ_AI_Data_Reference.md#negatives",
            }
        )

    for case_id, text in HISTORICAL_CASES:
        cases.append(
            {
                "id": case_id,
                "text": text,
                "expected_category": "unclassified",
                "suite": "historical",
                "source": "temporal_guard",
            }
        )

    cases.extend(_multilingual_eval_cases())

    payload = {
        "version": "1.1",
        "updated": "2026-09-10",
        "description": "Gold-label triage benchmark for ResQ AI classification regression testing.",
        "category_definitions": "triage_category_definitions.json",
        "case_count": len(cases),
        "cases": cases,
    }

    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(cases)} cases → {OUTPUT}")


if __name__ == "__main__":
    main()
