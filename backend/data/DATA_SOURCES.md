# ResQ AI — Data sources & install links

There is **no Kaggle dataset** for Hyderabad hospitals/shelters that is independently verified. Use these official/open sources instead.

## Hospitals (Supabase `hospitals` table)

| Source | Link | Format |
|--------|------|--------|
| **Telangana PHC KML** | `data/sources/kml/2d9812bb-…kml` | KML — `scripts/import_hospitals_kml.py` |
| **GHMC Hyderabad Hospitals KML** | `data/sources/kml/058a954c-…kml` | KML — `scripts/import_hospitals_kml.py --kml data/sources/kml/058a954c-…kml` |
| **HOT OSM / HDX India (supplement)** | https://data.humdata.org/dataset/eb18fd07-1656-4b5b-b865-aa2cb6a5c101 | GeoJSON zip — `scripts/import_hospitals_hotosm.py` |
| **OpenStreetMap Overpass (supplement)** | https://overpass.kumi.systems/api/interpreter | JSON — `scripts/fetch_hospitals_overpass.py` |
| **HDX India Health Facilities (bulk)** | https://data.humdata.org/dataset/health-facilities-in-india | CSV/Shapefile |
| **Telangana open data portal** | https://data.opencity.in/dataset/hyderabad-public-health-centres/resource/location-of-hospitals-in-hyderabad---2018 | KML |

**Install hospitals from KML (merge into Firebase):**
```powershell
cd backend
python scripts/import_hospitals_kml.py
python scripts/import_hospitals_kml.py --kml data/sources/kml/058a954c-e370-4b81-8716-0a2197ea5a01.kml
```
Outputs: `data/hospitals_phc_hyderabad.json`, `data/hospitals_hyd_municipal_hyderabad.json` + merged Supabase `hospitals` table. Use `--replace` only if you want to wipe existing rows first.

**One-shot Supabase setup (schema + seed including hospitals from bundled JSON):**
```powershell
python scripts/apply_supabase_schema.py
python scripts/seed_database.py --force
```

**Supplement with HOT OSM / HDX GeoJSON (recommended bulk OSM):**
```powershell
python scripts/import_hospitals_hotosm.py
```
Downloads ~5.5 MB GeoJSON zip (cached in `data/downloads/`), filters Hyderabad bbox, merges new rows into Supabase without removing existing PHC records. Metadata: `data/sources/metadata/hotosm_ind_health_facilities_osm_metadata.json`.

**Supplement with Overpass API (optional):**
```powershell
python scripts/fetch_hospitals_overpass.py
```
Uses [Overpass kumi.systems](https://overpass.kumi.systems/api/interpreter) first; falls back to `data/hospitals_hyderabad.json` if the API times out.

## Shelters, community reports, knowledge base (Supabase)

Bundled JSON in `backend/data/` — seeded by:
```powershell
cd backend
python scripts/apply_supabase_schema.py
python scripts/seed_database.py
```

## Triage phrases & action-plan text

Authored content from `docs/ResQ_AI_Data_Reference.md` — merged into:
- `app/services/triage_service.py` (Tier 1 keywords + Tier 2 embedding examples)
- `app/services/action_planner_service.py` (deterministic fallbacks)
- `data/knowledge_assets.json` → Supabase `knowledge_assets` with pgvector embeddings

**Gold-label classification benchmark:**
```powershell
python scripts/build_triage_eval_gold.py   # regenerate 104-case JSON
python scripts/run_triage_eval.py --fail-on-error
python -m pytest tests/test_triage_eval_gold.py -q
```
See `docs/validation-data-checklist.md` for the full validation framework.

## Optional: Kaggle CLI

If you find a related dataset on Kaggle later:
```powershell
pip install kaggle
# Place kaggle.json in %USERPROFILE%\.kaggle\
kaggle datasets download -d <dataset> -p backend/data/downloads
```

Most India health-facility Kaggle sets trace back to the same OSM/HDX sources above.
