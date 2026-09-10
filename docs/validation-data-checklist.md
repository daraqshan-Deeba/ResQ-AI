# ResQ AI — Validation Data Checklist

This document defines what data and documents are required for **validated** understanding, classification, prediction, and explainability in ResQ AI. It maps each pipeline stage to concrete assets, what you already have in the repo, and what is still missing.

**Validation rule:** A claim is *validated* only when it can be traced to a deterministic rule, a verified dataset with provenance, or a live API response with a timestamp — and is labeled honestly when it is probabilistic (LLM, unverified community input).

---

## Pipeline overview

| Stage | Decides | Authoritative layer | Confidence when healthy |
|-------|---------|---------------------|------------------------|
| **Understanding** | What was said + local context | Transcription, GPS, live APIs, RAG | Medium–high |
| **Classification** | Incident **type** (flood, injury, …) | Triage Tier 1–2 (deterministic), Tier 3 (LLM fallback) | High (T1/T2), Low (T3) |
| **Prediction** | **Severity / risk** (weather score) | `weather_service` + deterministic risk formula | High when API available |
| **Explainability** | Why the system said this | `TriageResult`, `source_labels`, `limiting_factor` | As good as upstream data |

Classification and prediction are **separated by design** (Principle 2): the LLM never sets severity or overall confidence.

---

## 1. Understanding — context assembly

### Required data

| Asset | Location / source | Validation requirement |
|-------|-------------------|------------------------|
| User description | Assessment API / chat | Non-empty, length limits, schema validation |
| Voice transcript | `POST /api/transcribe` (Groq Whisper) | Label as `ai_transcription`; show original audio unavailable in audit |
| User location | `lat` / `lon` from client | Flag when missing (city fallback used) |
| Live weather | OpenWeather API | `service_status.weather = live_weather_api` or `unavailable` |
| Traffic disruptions | `traffic_service` (OSM + community) | Source tag per incident type |
| Community reports | Supabase `community_reports` | `verified` boolean, `created_at`, `area` |
| Knowledge assets | Supabase `knowledge_assets` + pgvector | `title`, `category`, `source`, `content_text`, embedding |
| Hospitals | Supabase `hospitals` | `source`, `facility_type`, coords (see [DATA_SOURCES](../backend/data/DATA_SOURCES.md)) |
| Shelters | Supabase `shelters` | `source: manual` — admin-entered only |

### Current status

| Asset | Status |
|-------|--------|
| Hospitals (PHC + GHMC + HOT OSM) | **Done** — Supabase `hospitals` table with `source` tags |
| Knowledge assets (8 guides) | **Partial** — general guidance, not official NDMA/WHO citations |
| Community reports (18 demo) | **Partial** — mostly `verified: false` |
| Shelters (10 demo) | **Partial** — manual seed, not occupancy-verified |
| IMD / NDMA official alerts | **Missing** |
| Verified shelter occupancy feed | **Missing** (no public dataset) |

---

## 2. Classification — triage

### Required documents

| Document | Purpose | Location |
|----------|---------|----------|
| **Category taxonomy** | Definitions and boundaries for 7 categories + `unclassified` | `backend/data/triage_category_definitions.json` |
| **Tier 1 keyword table** | Deterministic phrase matching | `app/services/triage_service.py` + `ResQ_AI_Data_Reference.md` §3 |
| **Tier 2 canonical examples** | TF-IDF embedding corpus | `triage_service.py` `_TIER2_EXAMPLES` + `ResQ_AI_Data_Reference.md` §4 |
| **Negative examples** | False-positive guards | `ResQ_AI_Data_Reference.md` §3 (negatives) |
| **Gold-label eval set** | Regression benchmark | `backend/data/triage_eval_gold.json` |
| **Multilingual ML training** | Hindi/Telugu/English classifier | `backend/data/triage_ml_training.json` |
| **ML classifier service** | Tier 2.5 (sklearn, deterministic) | `app/services/triage_ml_service.py` |
| **Eval runner** | Accuracy report per suite | `python scripts/run_triage_eval.py` |
| **ML training report** | Classifier stats + multilingual accuracy | `python scripts/train_triage_classifier.py` |
| **Persisted model artifacts** | `triage_classifier.joblib`, `report_classifier.joblib` | `python scripts/train_models.py` |
| **Report incident classifier** | accident / construction / congestion / flooding | `app/ml/reports.py` |
| **ML status API** | Model metadata | `GET /api/ml/status` |

### Suites in the gold eval set

| Suite | What it tests | CI expectation |
|-------|---------------|----------------|
| `tier1` | Direct keyword matches | Must pass at Tier 1 |
| `tier2` | Paraphrases (embedding similarity) | Must pass at Tier 2 (Tier 1 also acceptable) |
| `multilingual` | Hindi/Telugu (native + romanized) | Must pass via rules or ML classifier |
| `negative` | Non-emergency / historical phrasing | Must return `unclassified` (Tier 3 mocked in CI) |
| `historical` | Past-tense reports | Must return `unclassified` or not high-confidence Tier 1 |

### Run evaluation

```powershell
cd backend
python scripts/run_triage_eval.py
python scripts/run_triage_eval.py --fail-on-error   # CI mode
python -m pytest tests/test_triage_eval_gold.py -q
```

### Current status

| Item | Status |
|------|--------|
| 3-tier triage cascade | **Done** |
| Gold eval set (~100 cases) | **Done** — `triage_eval_gold.json` |
| Automated eval + pytest | **Done** |
| Multilingual (Telugu/Hindi) phrases | **Missing** |
| Clinician / NDMA-reviewed taxonomy | **Missing** |

---

## 3. Prediction — weather risk (not LLM)

### Required data

| Asset | Role | Validation |
|-------|------|------------|
| OpenWeather observations | Rain, wind, temp | API key, response timestamp |
| Risk formula | 0–100 score + `watch/warning/critical` | Documented in `weather_service` |
| User coordinates | Location-specific risk | Must match weather query coords |

### Current status

| Item | Status |
|------|--------|
| Live weather + risk score | **Done** |
| Calibrated Hyderabad flood model | **Missing** (drainage factor is placeholder) |
| IMD cyclone / heavy-rain alerts | **Missing** |
| Triage category modulating risk | **Not implemented** |

---

## 4. Action planning

### Required documents

| Document | Role | Trust level |
|----------|------|-------------|
| Deterministic templates per category | Fallback when Groq fails | **High** (1.0 confidence) |
| Trusted emergency contacts | 112, 108, 1070, … | Must be **periodically verified** |
| Official protocols (optional) | NDMA flood guide, snakebite protocol | **High** if sourced and cited |
| `ActionPlan` schema | Blocks URLs, severity leaks | Enforced in `schemas.py` |

### Current status

| Item | Status |
|------|--------|
| Deterministic fallbacks | **Done** — `action_planner_service.py` |
| General guidance in knowledge base | **Done** — label as `general_guidance` |
| Verified NDMA/WHO document extracts | **Missing** |
| Helpline verification log | **Missing** |

---

## 5. Explainability — audit trail

Every assessment should be explainable via API fields:

| Field | Explains |
|-------|----------|
| `triage.tier` | Which cascade stage decided the category |
| `triage.matched_rule_or_example` | Exact keyword or embedding match |
| `triage.explanation` | Human-readable classification reason |
| `action_plan.explanation` | Why these steps were recommended |
| `confidence.limiting_factor` | Weakest subsystem (`triage`, `weather`, `action_plan`) |
| `source_labels` | Provenance per subsystem |
| `community_insights[].source` | `community_report` vs `knowledge_asset` |
| `community_insights[].similarity` | RAG retrieval score |

### Recommended audit extensions (not yet built)

- Model / rules version string (`triage_rules_v1.0`)
- Dataset refresh dates per Firebase hospital `source`
- Assessment log table (input hash, outputs, API timestamps)
- Reviewer sign-off on knowledge assets (`last_reviewed_by`, `last_reviewed_at`)

---

## 6. Dataset provenance metadata

Each external dataset should ship with metadata JSON (pattern: `backend/data/sources/metadata/hotosm_ind_health_facilities_osm_metadata.json`):

| Field | Example |
|-------|---------|
| `dataset_id` | HDX UUID |
| `download_url` | S3 / portal link |
| `last_modified` | ISO date |
| `format` | KML, GeoJSON, JSON |
| `record_count` | After import filter |
| `license` | OSM ODbL, Public Domain |

### Imported hospital sources

| Source tag | File / origin | Records (approx.) |
|------------|---------------|-------------------|
| `telangana_phc_kml` | `2d9812bb-…kml` | 365 |
| `hyd_municipal_kml` | `058a954c-…kml` | 933 |
| `hotosm_hdx` | HDX India health facilities GeoJSON | 1,856 (Hyderabad bbox) |

---

## 7. Priority backlog

| Priority | Item | Why |
|----------|------|-----|
| **P0** | Run `run_triage_eval.py` in CI | Prevents classification regressions |
| **P0** | Verify helplines (112, 108, 1070) annually | Wrong numbers are a safety risk |
| **P1** | `source` + `last_reviewed` on knowledge assets | Honest explainability |
| **P1** | Community report moderation workflow | Ground truth for local context |
| **P2** | IMD alert API integration | Validated prediction beyond rain mm |
| **P2** | Telugu/Hindi triage phrases | Real user language in Hyderabad |
| **P3** | Official NDMA protocol PDFs in knowledge base | Citable high-trust guidance |

---

## 8. File index

| Path | Description |
|------|-------------|
| `docs/validation-data-checklist.md` | This document |
| `docs/ResQ_AI_Data_Reference.md` | Authored triage phrases and action templates |
| `backend/data/DATA_SOURCES.md` | Hospital/shelter install links |
| `backend/data/triage_category_definitions.json` | Category taxonomy |
| `backend/data/triage_eval_gold.json` | Gold-label triage benchmark |
| `backend/data/knowledge_assets.json` | RAG seed content |
| `backend/scripts/run_triage_eval.py` | Eval runner + metrics report |
| `backend/tests/test_triage_eval_gold.py` | Pytest gate for gold set |

---

*Last updated: 2026-09-10*
