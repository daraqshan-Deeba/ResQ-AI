"""
Fetch hospitals in Greater Hyderabad from OpenStreetMap (Overpass API)
and seed Firebase Firestore.

    cd backend
    python scripts/fetch_hospitals_overpass.py
    python scripts/fetch_hospitals_overpass.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import database_service, supabase_service

# Use GET — overpass-api.de returns 406 on some POST clients.
OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"
# Central Hyderabad — smaller bbox keeps Overpass fast
BBOX = (17.35, 78.42, 17.48, 78.55)
QUERY = """
[out:json][timeout:25];
(
  node["amenity"="hospital"]({south},{west},{north},{east});
  node["amenity"="clinic"]({south},{west},{north},{east});
);
out body;
"""
FALLBACK_JSON = Path(__file__).resolve().parents[1] / "data" / "hospitals_hyderabad.json"


def _load_fallback_hospitals() -> list[dict]:
    if not FALLBACK_JSON.exists():
        return []
    import json

    return json.loads(FALLBACK_JSON.read_text(encoding="utf-8"))


def fetch_hospitals() -> list[dict]:
    south, west, north, east = BBOX
    query = QUERY.format(south=south, west=west, north=north, east=east)
    try:
        resp = httpx.get(OVERPASS_URL, params={"data": query}, timeout=60)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
    except Exception as exc:
        print(f"Overpass unavailable ({exc}). Using bundled fallback JSON.")
        return _load_fallback_hospitals()

    rows: list[dict] = []
    seen: set[str] = set()
    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name") or tags.get("operator")
        if not name:
            continue
        lat = el.get("lat")
        lon = el.get("lon")
        center = el.get("center") or {}
        if lat is None:
            lat = center.get("lat")
        if lon is None:
            lon = center.get("lon")
        if lat is None or lon is None:
            continue

        key = f"{name.strip().lower()}:{round(float(lat), 4)}:{round(float(lon), 4)}"
        if key in seen:
            continue
        seen.add(key)

        address_parts = [
            tags.get("addr:street"),
            tags.get("addr:suburb"),
            tags.get("addr:city"),
        ]
        address = ", ".join(p for p in address_parts if p) or tags.get("addr:full")

        phone = tags.get("phone") or tags.get("contact:phone")
        rows.append(
            {
                "name": name.strip(),
                "address": address or "Hyderabad, Telangana",
                "lat": float(lat),
                "lon": float(lon),
                "phone": phone,
                "source": "openstreetmap",
            }
        )
    rows.sort(key=lambda r: r["name"])
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch OSM hospitals and seed Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Fetch only, do not write")
    parser.add_argument("--limit", type=int, default=80, help="Max hospitals to seed")
    args = parser.parse_args()

    print("Fetching hospitals from OpenStreetMap Overpass API…")
    hospitals = fetch_hospitals()
    print(f"Found {len(hospitals)} facilities in bbox {BBOX}")

    if args.dry_run:
        for row in hospitals[:10]:
            print(f"  - {row['name']} ({row['lat']:.4f}, {row['lon']:.4f})")
        if len(hospitals) > 10:
            print(f"  … and {len(hospitals) - 10} more")
        return

    if not database_service.hospitals_directory_available():
        print("Database not configured. Set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in .env first.")
        sys.exit(1)

    backend = "Supabase" if supabase_service.supabase_available else "Firebase (fallback)"
    print(f"Target database: {backend}")

    existing = database_service.list_hospitals()
    existing_keys = {
        f"{(h.get('name') or '').strip().lower()}:{round(float(h.get('lat') or 0), 4)}"
        for h in existing
    }

    added = 0
    for row in hospitals[: args.limit]:
        key = f"{row['name'].lower()}:{round(row['lat'], 4)}"
        if key in existing_keys:
            continue
        database_service.add_hospital(row)
        added += 1

    print(f"Seeded {added} new hospitals ({len(existing)} already present).")


if __name__ == "__main__":
    main()
