"""
Import Hyderabad health facilities from HOT OSM / HDX India GeoJSON
into backend/data JSON and Firebase Firestore (merge with existing PHC data).

    cd backend
    python scripts/import_hospitals_hotosm.py
    python scripts/import_hospitals_hotosm.py --dry-run
    python scripts/import_hospitals_hotosm.py --refresh   # re-download zip
    python scripts/import_hospitals_hotosm.py --include-unnamed
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import database_service, supabase_service
from app.services.hotosm_hospital_parser import (
    HOTOSM_POINTS_ZIP_URL,
    download_hotosm_points_zip,
    facility_type_counts,
    load_geojson_from_zip_bytes,
    parse_hotosm_geojson,
)

CACHE_ZIP = Path(__file__).resolve().parents[1] / "data" / "downloads" / "hotosm_ind_health_facilities_points_geojson.zip"
OUTPUT_JSON = Path(__file__).resolve().parents[1] / "data" / "hospitals_hotosm_hyderabad.json"


def _dedupe_key(row: dict) -> str:
    return f"{row['name'].strip().lower()}:{row['lat']}:{row['lon']}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Import HOT OSM HDX hospitals → JSON + Firebase")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, no writes")
    parser.add_argument("--refresh", action="store_true", help="Re-download GeoJSON zip from HDX/S3")
    parser.add_argument(
        "--include-unnamed",
        action="store_true",
        help="Include facilities with no name tag (uses OSM id fallback)",
    )
    args = parser.parse_args()

    cache_path = None if args.refresh else CACHE_ZIP
    if args.refresh and CACHE_ZIP.exists():
        CACHE_ZIP.unlink()

    print(f"Fetching HOT OSM points from:\n  {HOTOSM_POINTS_ZIP_URL}")
    if cache_path and cache_path.exists():
        print(f"Using cached zip → {cache_path}")

    data = download_hotosm_points_zip(cache_path=cache_path if not args.dry_run or cache_path else CACHE_ZIP)
    geojson = load_geojson_from_zip_bytes(data)
    total_features = len(geojson.get("features", []))
    print(f"Loaded {total_features:,} India-wide point features")

    rows = parse_hotosm_geojson(
        geojson,
        hyderabad_only=True,
        include_unnamed=args.include_unnamed,
    )
    print(f"Extracted {len(rows)} emergency-relevant facilities inside Hyderabad bbox")

    counts = facility_type_counts(rows)
    for ft, n in list(counts.items())[:12]:
        print(f"  {ft}: {n}")
    if len(counts) > 12:
        print(f"  … and {len(counts) - 12} more facility types")

    if args.dry_run:
        for row in rows[:8]:
            print(f"  - [{row['facility_type']}] {row['name']} ({row['lat']}, {row['lon']})")
        if len(rows) > 8:
            print(f"  … and {len(rows) - 8} more")
        return

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote dataset → {OUTPUT_JSON}")

    if not database_service.hospitals_directory_available():
        print("Database not configured — JSON only. Set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in .env.")
        return

    backend = "Supabase" if supabase_service.supabase_available else "Firebase (fallback)"
    print(f"Target database: {backend}")

    existing = database_service.list_hospitals()
    existing_keys = {
        f"{(h.get('name') or '').strip().lower()}:{h.get('lat')}:{h.get('lon')}"
        for h in existing
    }
    print(f"Existing hospitals: {len(existing)}")

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
    print(f"Hospitals: added {added} new from HOT OSM, skipped {skipped}, {total} total in database.")


if __name__ == "__main__":
    main()
