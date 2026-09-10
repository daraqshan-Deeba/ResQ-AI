"""
Import Hyderabad PHC / hospital locations from Telangana open-data KML
into backend/data JSON and Firebase Firestore.

    cd backend
    python scripts/import_hospitals_kml.py
    python scripts/import_hospitals_kml.py --kml data/sources/kml/2d9812bb-6901-4eca-90f9-a91ca50772a0.kml
    python scripts/import_hospitals_kml.py --kml data/sources/kml/058a954c-e370-4b81-8716-0a2197ea5a01.kml
    python scripts/import_hospitals_kml.py --dry-run
    python scripts/import_hospitals_kml.py --replace   # clear existing hospitals first
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data_paths import PHC_KML
from app.services import database_service, supabase_service
from app.services.kml_hospital_parser import (
    _detect_kml_schema,
    facility_type_counts,
    parse_hospital_kml,
)

DEFAULT_KML = PHC_KML
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUTPUT_BY_SCHEMA = {
    "health_facilities": DATA_DIR / "hospitals_phc_hyderabad.json",
    "hyd_hospitals": DATA_DIR / "hospitals_hyd_municipal_hyderabad.json",
}


def _dedupe_key(row: dict) -> str:
    return f"{row['name'].strip().lower()}:{row['lat']}:{row['lon']}"


def _clear_hospitals() -> int:
    return database_service.clear_hospitals()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import PHC KML → JSON + Firebase")
    parser.add_argument("--kml", type=Path, default=DEFAULT_KML, help="Path to KML file")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no writes")
    parser.add_argument("--replace", action="store_true", help="Delete existing hospitals first")
    args = parser.parse_args()

    if not args.kml.exists():
        print(f"KML not found: {args.kml}")
        sys.exit(1)

    schema = _detect_kml_schema(args.kml)
    output_json = OUTPUT_BY_SCHEMA.get(schema, DATA_DIR / "hospitals_kml_import.json")

    print(f"Parsing {args.kml.name} ({schema}) …")
    rows = parse_hospital_kml(args.kml)
    print(f"Extracted {len(rows)} facilities inside Hyderabad bbox")

    counts = facility_type_counts(rows)
    for ft, n in counts.items():
        print(f"  {ft}: {n}")

    if args.dry_run:
        for row in rows[:8]:
            print(f"  - [{row['facility_type']}] {row['name']} ({row['lat']}, {row['lon']})")
        if len(rows) > 8:
            print(f"  … and {len(rows) - 8} more")
        return

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote dataset → {output_json}")

    if not database_service.hospitals_directory_available():
        print("Database not configured — JSON only. Set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in .env.")
        return

    backend = "Supabase" if supabase_service.supabase_available else "Firebase (fallback)"
    print(f"Target database: {backend}")

    if args.replace:
        removed = _clear_hospitals()
        print(f"Cleared {removed} existing hospital records.")

    existing = database_service.list_hospitals()
    existing_keys = {
        f"{(h.get('name') or '').strip().lower()}:{h.get('lat')}:{h.get('lon')}"
        for h in existing
    }

    added = 0
    skipped = 0
    for row in rows:
        key = _dedupe_key(row)
        if key in existing_keys:
            skipped += 1
            continue
        try:
            database_service.add_hospital(row)
            existing_keys.add(key)
            added += 1
        except Exception as exc:
            if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
                skipped += 1
                existing_keys.add(key)
            else:
                raise

    total = database_service.count_hospitals()
    print(f"Hospitals: added {added} new, skipped {skipped} duplicates, {total} total in database.")


if __name__ == "__main__":
    main()
