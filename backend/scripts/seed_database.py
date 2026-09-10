"""
Seed Supabase tables from backend/data/*.json and ingest knowledge assets.

    cd backend
    python scripts/apply_supabase_schema.py   # run once
    python scripts/seed_database.py
    python scripts/seed_database.py --force   # re-seed even if rows exist
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import database_service, knowledge_service, supabase_service

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _load_json(name: str) -> list[dict]:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _count_table(table: str) -> int:
    if not supabase_service.supabase_available or supabase_service.client is None:
        return 0
    resp = supabase_service.client.table(table).select("id", count="exact").execute()
    return resp.count or len(resp.data or [])


def seed_shelters(force: bool) -> int:
    if _count_table("shelters") > 0 and not force:
        print(f"  shelters: skipped ({_count_table('shelters')} rows exist)")
        return 0
    rows = _load_json("shelters.json")
    for row in rows:
        database_service.add_shelter(row)
    print(f"  shelters: inserted {len(rows)}")
    return len(rows)


def seed_community_reports(force: bool) -> int:
    if _count_table("community_reports") > 0 and not force:
        print(f"  community_reports: skipped ({_count_table('community_reports')} rows exist)")
        return 0
    if not supabase_service.supabase_available or supabase_service.client is None:
        print("  community_reports: Supabase unavailable")
        return 0

    rows = _load_json("community_reports.json")
    now = datetime.now(timezone.utc).isoformat()
    payload = [
        {
            "area": r["area"],
            "message": r["message"],
            "reporter_name": r.get("reporter_name"),
            "verified": bool(r.get("verified", False)),
            "created_at": now,
        }
        for r in rows
    ]
    supabase_service.client.table("community_reports").insert(payload).execute()
    print(f"  community_reports: inserted {len(payload)}")
    return len(payload)


HOSPITAL_JSON_FILES = (
    "hospitals_phc_hyderabad.json",
    "hospitals_hyd_municipal_hyderabad.json",
    "hospitals_hotosm_hyderabad.json",
)


def _dedupe_hospital_key(row: dict) -> str:
    return f"{(row.get('name') or '').strip().lower()}:{row.get('lat')}:{row.get('lon')}"


def seed_hospitals(force: bool) -> int:
    if _count_table("hospitals") > 0 and not force:
        print(f"  hospitals: skipped ({_count_table('hospitals')} rows exist)")
        return 0

    merged: list[dict] = []
    seen: set[str] = set()
    for filename in HOSPITAL_JSON_FILES:
        path = DATA_DIR / filename
        if not path.exists():
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            key = _dedupe_hospital_key(row)
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)

    if not merged:
        print("  hospitals: no JSON files found — run import_hospitals_kml.py / import_hospitals_hotosm.py")
        return 0

    added = database_service.add_hospitals_batch(merged, chunk_size=250)
    print(f"  hospitals: inserted {added} from bundled JSON ({len(merged)} unique rows)")
    return added


def seed_knowledge_assets(force: bool) -> int:
    if _count_table("knowledge_assets") > 0 and not force:
        print(f"  knowledge_assets: skipped ({_count_table('knowledge_assets')} rows exist)")
        return 0
    if not knowledge_service.knowledge_available():
        print("  knowledge_assets: Supabase unavailable")
        return 0

    rows = _load_json("knowledge_assets.json")
    for row in rows:
        knowledge_service.ingest_asset(
            title=row["title"],
            content_text=row["content_text"],
            asset_type="document",
            area=row.get("area"),
            source_type="reference_doc",
            metadata={
                "category": row.get("category"),
                "source": "ResQ_AI_Data_Reference.md",
            },
        )
    print(f"  knowledge_assets: ingested {len(rows)} (embeddings computed)")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed ResQ AI Supabase data")
    parser.add_argument("--force", action="store_true", help="Insert even if tables have rows")
    args = parser.parse_args()

    if not supabase_service.supabase_available:
        print("Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env")
        print("Then run: python scripts/apply_supabase_schema.py")
        sys.exit(1)

    print("Seeding Supabase from backend/data/ …")
    total = 0
    total += seed_shelters(args.force)
    total += seed_community_reports(args.force)
    total += seed_knowledge_assets(args.force)
    total += seed_hospitals(args.force)
    print(f"Done. {total} records added this run.")
    print("More hospitals: python scripts/import_hospitals_kml.py && python scripts/import_hospitals_hotosm.py")


if __name__ == "__main__":
    main()
