# ResQ AI — System Validation, Feature-by-Feature Audit & Engineering Review

**Audit date:** 24 Sep 2026  **Subject:** `ResQ-AI-validation-sanitized.zip` (198 files: Next.js 16 frontend, Flask backend, Supabase SQL, docs, data)
**Mode:** read-only. No project file was edited, no dependency was installed into the project, no `.env` was read (none present).

---

## 0. How this audit was done (read this first)

**Evidence tags used throughout**

| Tag | Meaning |
|---|---|
| **[FACT]** | Verified directly in source, or reproduced by running code in a scratch copy |
| **[INFERENCE]** | Follows from the code, but not run end-to-end |
| **[REC]** | Recommendation (not implemented) |
| **[ALT]** | Another viable design |
| **[UNVERIFIED]** | Cannot be established from the supplied copy (external services, credentials, deployment) |

**What I read:** every backend module under `backend/app/`, all blueprints, all six SQL files, the frontend `src/` (pages, components, hooks, lib, middleware), the design docs (`resq-ai-fix-algorithms.md`, `validation-data-checklist.md`, `security-secrets.md`, `DATA_SOURCES.md`), the test suite structure, the CI workflow, and all datasets' structure and statistics.
**What I only skimmed or did not open:** hospital KML/HOT-OSM parsers and import scripts, `seed_*` scripts, landing/login/register pages, `RegistrationForm`/`phone.ts` internals, `lib/keepalive.ts`, `context-retriever/` (Redis Context Retriever models, not wired into the app), `auth-setup.md`, the 22k-line hospital JSON contents beyond schema/statistics. Findings about those are limited to what's stated.

**Behavioural probes (all in scratch space outside the project):** I ran the project's own code in a throwaway copy with a separate virtualenv (pinned `pydantic==2.9.2`, `scikit-learn==1.5.2`, `flask==3.0.3`, `httpx==0.27.2` from `requirements.txt`), a stub for the Firebase SDK, and **no API keys**. That allowed me to run the triage gold-set, the full orchestrator on adversarial inputs, and the Flask routes through the test client. Probes that simulate an LLM reply are labelled as simulations — they demonstrate what the *validators accept*, not what the model actually returns.
**Not possible here:** live Groq/OpenWeather/TomTom/Supabase/Firebase/Redis behaviour, the deployed backend host, the Next.js build/runtime, real browsers/GPS. These are marked [UNVERIFIED].

**Secrets:** a pattern scan (Groq/OpenAI/Google/JWT/private-key/Supabase-secret shapes) over the whole tree found **no potential secrets**. `plan.py`/`plan_output.json` do contain the author's local Windows user name and drive paths — not a secret, but worth removing before sharing.

**Severity calibration.** The README calls this a prototype and says it doesn't notify emergency services. Severity below is "what would matter if real people relied on it", and I've noted where the code already discloses a limitation.

---

## 1. Executive system map

```text
Browser (Next.js 16, React 19)
 ├─ Supabase Auth (Google OAuth) ── cookie session, middleware guards /dashboard, /register   [pages only]
 ├─ Supabase (direct, anon key)  ── profiles table (RLS: own row)
 └─ fetch ───────────────► Flask API (NO authentication, NO rate limiting, CORS allow-list)
                              │
     /api/assessment ─► Emergency Orchestrator (sequential)
                              ├─ 1 validate  ─ 2 Triage: rules → TF-IDF cosine → sklearn LR → Groq LLM → "unclassified"
                              ├─ 3 OpenWeather current obs → heuristic risk score (rain only)
                              ├─ 4 Groq JSON action plan  (fallback: authored per-category protocol)
                              ├─ 5 weakest-link confidence (min of triage, weather-availability, plan-provenance)
                              ├─ 6 hospitals (DB directory + haversine, 5 km)   [only if lat/lon sent]
                              ├─ 7 optional SOS   [frontend never uses this path]
                              └─ 7b community context (keyword match on reports + pgvector knowledge)
     /api/sos ────────► persist event (Supabase|Firestore) → FCM *topic* broadcast → update status
     /api/chat ───────► Groq chat (+ Redis Agent Memory recall)
     /api/transcribe ─► Groq Whisper
     /api/weather, /weather/risk, /traffic/nearby, /hospitals, /shelters, /reports, /knowledge/*, /device-token, /ml/status, /cron/keepalive
                              │
     Supabase Postgres+pgvector+Storage │ Firebase (FCM; Firestore fallback) │ Redis Agent Memory │ OpenWeather │ Overpass │ TomTom │ Groq
```

**In one paragraph.** ResQ AI is a Hyderabad-centred emergency *information* app. The strongest engineering is in the orchestrator's separation of concerns: severity is derived by code, not by the LLM; LLM output is schema-validated with a deterministic fallback; SOS is persisted before it is notified; provenance labels and a service-status map travel with each result. The weakest parts are (1) what happens **outside the seven hard-coded hazard types**, (2) what the UI shows when a dependency **fails** (several fallbacks fabricate benign-looking values), (3) SOS delivery, which is a **topic broadcast** to whoever subscribed rather than a notification to a defined responder or contact, (4) a **fully unauthenticated backend**, and (5) an ML evaluation that is largely **testing on the training data**.

### Top findings at a glance

| # | Sev | Finding | Where |
|---|---|---|---|
| C1 | **Critical** | Fire, cardiac arrest, choking, drowning, gas leak, assault, self-harm → `unclassified` → emergency level **"Low"**, rendered with the green "safe" badge. Two hazards at once → also `unclassified`/Low. | `emergency_orchestrator.determine_emergency_level`, `triage_service.classify`, `AssessmentResultPanel.tsx` |
| C2 | **Critical** | SOS pushes exact lat/lon to one global FCM topic; device registration is unauthenticated, so anyone with an FCM token can subscribe and receive every SOS. Success text says "sent to responders" though no responder exists. Profile emergency contacts are never used. | `firebase_service.send_topic_push/register_device`, `sos.py` |
| C3 | **Critical** | Whole Flask API is unauthenticated with no rate limiting; SOS/report/upload/LLM/Whisper endpoints are open. Backend uses the Supabase **service-role** key. | `main.py`, all blueprints |
| C4 | **High** | The vetted per-hazard protocol is used only as *fallback*; a schema-valid LLM plan replaces it. Free-text numbers/medical advice are not content-checked; contact sanitiser accepts `1080` because it contains `108`. | `action_planner_service.py` |
| C5 | **High** | Failure paths fabricate reassurance: weather-unavailable renders 25 °C / score 18 / "safe"; `/weather/risk` returns "safe" baseline with HTTP 200; traffic shows "No accidents… reported" when all sources failed; hospitals endpoint returns `[]`→"No hospitals found nearby" on any failure; no location ⇒ Hyderabad weather shown as yours. | `orchestrator`, `weather.py`, `DashboardLocationPanel.tsx`, `hospitals.py` |
| C6 | **High** | Hospitals page never sends the user's location → always lists hospitals nearest to central Hyderabad. Directory has no phone numbers and no emergency-capability field. | `hospitals/page.tsx`, `maps_service.py`, data |
| C7 | **High** | Supabase policies: anon **INSERT** on `community_reports` (`with check (true)` — caller can set `verified=true`); storage INSERT/UPDATE policies named "service role" but not restricted to that role. | `schema.sql`, `schema_vectors.sql` |
| C8 | **High** | Confidence: any LLM-generated plan caps overall confidence at 0.35 ("low") — constant, uninformative; the degraded no-LLM path can show 93 % "high". Weather availability drags confidence for hazards where weather is irrelevant. | `confidence_service.py`, orchestrator |
| C9 | **High** | Triage logic gaps: negation ("no flooding here") → High; "last week"/"used to" guard silences *current* life-threats; only 7 hazards. | `triage_service.py` |
| C10 | **High** | ML validity: 101/178 gold cases (57 %) are verbatim in training data; 175/223 training rows (78 %) are gold items. With gold texts removed from training, multilingual accuracy is 50 % (37/74). Tier 1 has zero native-script phrases. | `triage_ml_training.json`, `triage_eval_gold.json` |
| C11 | **High** | `requirements.txt` doesn't reproduce the author's environment: with the pinned versions the ML tier and the community-traffic path raise `ValidationError` (numpy `str_` vs pydantic 2.9.2 `Literal`) → 11/269 tests fail; ML tier silently disabled; `/api/traffic/nearby` can 500. | `ml/triage.py`, `traffic_service.py` |
| C12 | Medium | SOS: DB error that is not a `RuntimeError` → 500 HTML; NaN/out-of-range coords accepted; no idempotency; no client timeout/retry/offline queue; no `tel:` link; no fallback message when GPS fails. | `sos.py`, `SosConfirmModal.tsx`, `api.ts` |
| C13 | Medium | Language selector (Telugu/Hindi) has no effect on assessment output — `language` is accepted then dropped in the orchestrator. | `emergency_orchestrator.py` |

---

## 2. Repository structure

```text
ResQ-AI/
├─ frontend/                       Next.js 16.3.4 (App Router) · React 19.2 · TS · Tailwind 4 · React Compiler
│  ├─ src/app/                     pages: /, /login, /register, /dashboard/{assessment,hospitals,shelters,reports,settings,…}
│  │                               api routes: /api/health, /api/cron/keepalive ; auth/callback
│  ├─ src/components/              AssessmentResultPanel, SosConfirmModal, ChatWidget, DashboardLocationPanel, …
│  ├─ src/hooks/                   useUserLocation, useVoiceInput (MediaRecorder → /api/transcribe)
│  ├─ src/lib/                     api.ts (fetch wrapper), supabase/{client,server,middleware}, firebase.ts, types.ts
│  └─ public/firebase-messaging-sw.js
├─ backend/                        Flask 3 (async views) + Pydantic v2
│  ├─ app/main.py                  app factory, CORS, blueprint registration, /health
│  ├─ app/blueprints/ (13)         thin HTTP layer — assessment, sos, chat, weather, hospitals, shelters, reports, traffic,
│  │                               transcribe, knowledge, device, ml, keepalive
│  ├─ app/services/                emergency_orchestrator, triage_service, action_planner_service, confidence_service,
│  │                               weather_service, maps_service (hospital directory), traffic_service, groq_service,
│  │                               transcription_service, knowledge_service, embedding_service, agent_memory_service,
│  │                               database_service (facade), supabase_service, firebase_service, supabase_cache, …
│  ├─ app/ml/                      text_classifier (TF-IDF word+char → LogisticRegression), triage.py, reports.py
│  ├─ app/models/schemas.py        all Pydantic models (single file)
│  ├─ data/                        hospitals (4 JSON), shelters, community_reports, knowledge_assets, triage gold/training, models/ (.gitkeep only)
│  ├─ supabase/*.sql               6 schema files (+ SCHEMA_ERD.md)
│  ├─ scripts/                     seed/import/train/eval/scan_secrets
│  └─ tests/                       20 files, 258 test functions (269 collected)
├─ docs/                           design principles & fix algorithms, data reference, secrets, cron keep-alive
├─ context-retriever/              Redis Context Retriever entity models — not referenced by the app
├─ .github/workflows/keepalive.yml every-5-min ping (anti cold-start)
├─ plan.py, plan_output.json       author's validation runner + a past run (contains local paths)
└─ start.sh                        dev launcher (Flask :8001 + Next :3000)
```

**Absent [FACT]:** Dockerfile, Procfile, WSGI/ASGI server config (`run.py` uses Flask's dev server with `debug=True`), frontend tests, backend CI (only the keep-alive workflow), migrations tool (SQL files are run by hand / `apply_supabase_schema.py`).

---

## 3. Technology stack

| Area | Actual technology (version) | Where | Appropriate? | Alternatives |
|---|---|---|---|---|
| Frontend | Next.js 16.3.4, React 19.2.8, TS 5, Tailwind 4, `babel-plugin-react-compiler` | `frontend/` | Yes. Note: earlier project notes say Next.js 15; `package.json` is authoritative. | Vite SPA + PWA (better offline story) |
| Backend | Python, Flask 3.0.3 with `flask[async]`, Flask-CORS 5.0.0 | `backend/app` | Adequate for prototype; async views run via `asgiref` thread bridge and the code calls sync Supabase/Firestore SDKs inside them. | FastAPI (native async, OpenAPI, dependency-injected auth) |
| Language versions | README: "Python 3.12+"; author's run log: **Python 3.10.0** | `plan_output.json` | **Mismatch** | Pin one, add `.python-version` |
| Validation | Pydantic 2.9.2 (pinned) | `schemas.py`, `http_utils.py` | Good choice; pin is stale (see C11) | — |
| DB | Supabase Postgres (+ `pgvector`, Storage); Firestore as legacy fallback | `supabase_service.py`, `firebase_service.py` | Supabase yes; dual-store is a liability (§21) | Postgres + PostGIS |
| Auth | Supabase Auth, Google OAuth only; `@supabase/ssr` 0.12 | `frontend/src/lib/supabase`, `middleware.ts` | Frontend yes; **backend has none** | JWT verification in Flask (Supabase JWKS) |
| LLM | Groq chat-completions via `httpx`; default model string `qwen/qwen3.6-27b` (README says Llama 3.3 70B) | `groq_service.py`, `config.py` | Reasonable provider; model ID [UNVERIFIED] — a wrong ID yields 404 → silent fallback everywhere | Any provider behind an interface |
| Speech-to-text | Groq `whisper-large-v3` via HTTP | `transcription_service.py` | Good multilingual quality; server-side | On-device Web Speech API (offline, less accurate for Hi/Te) |
| ML | scikit-learn 1.5.2: TF-IDF (word 1-2 + char_wb 3-5) + LogisticRegression; `joblib` persistence | `app/ml/` | OK for a small text classifier; data/eval are the problem | Multilingual sentence embeddings (e5/LaBSE) + LR |
| Embeddings | `fastembed` `BAAI/bge-small-en-v1.5` (384-d; code comment says MiniLM) | `embedding_service.py` | English-only model for a Hi/Te product | `multilingual-e5-small` |
| Vector search | pgvector HNSW + `match_knowledge_assets` RPC | `schema_vectors.sql` | Fine | — |
| Cache | In-process TTL dict (300/120/60 s) | `supabase_cache.py` | Fine for one process; not shared across workers/instances | Redis / HTTP cache headers |
| Agent memory | Redis Agent Memory service via `redis-agent-memory` (unpinned `>=0.3.0`) | `agent_memory_service.py` | Not necessary (§22) | Client-held history |
| Weather | OpenWeather Current Weather 2.5 | `weather_service.py` | Current obs only; no forecast/alerts | IMD feeds, OWM One Call, Open-Meteo |
| Traffic | Overpass (OSM construction/debris) + TomTom incidents (optional key) + community reports | `traffic_service.py` | Partial: no live congestion source | TomTom Flow, HERE |
| Maps | **None server-side.** Distance = haversine; links to Google Maps URLs; OSM iframe on dashboard. `GOOGLE_MAPS_API_KEY` is read in config but **unused** [FACT] | `maps_service.py`, `LocationMap.tsx` | Simple and cheap | Routing API (OSRM/Google) |
| Push | Firebase Cloud Messaging via Admin SDK, topic `resq_alerts`; web SW | `firebase_service.py`, `firebase-messaging-sw.js` | Topic broadcast is the wrong primitive for SOS (§10) | Per-recipient tokens/SMS/WhatsApp |
| Deployment | Frontend: Vercel (`vercel.json` cron). Backend host: **not defined** in repo [UNVERIFIED] | — | — | — |

---

## 4. Architecture reconstruction

Layering is **blueprint → service → Supabase/Firebase/HTTP**. Blueprints are thin except `reports.py` (upload handling). Schemas are one file. `database_service` is a facade choosing Supabase or Firestore **once at import time**.

### Data on each arrow

| Arrow | Payload / format | Validation | Auth | Timeout | Failure / fallback |
|---|---|---|---|---|---|
| Browser → Flask (all) | JSON or multipart via `apiCall/apiUpload` | Pydantic per route; Flask returns **HTML** 400/415/500 on malformed/non-JSON bodies | **None** | **None on client** (no `AbortController`) | Any non-2xx → generic "Something went wrong" (400/422/500 indistinguishable) |
| Flask → Groq (chat completions) | OpenAI-style JSON | `ActionPlan` schema (plan); regex parse (triage) | Bearer key | 30 s | `ServiceResult(available=False, error_type)` → deterministic fallback / static text |
| Flask → OpenWeather | GET lat/lon/units | float parse | key in query string | 10 s | error typed; orchestrator substitutes baseline (see §14) |
| Flask → Supabase | `supabase-py` (PostgREST) with service-role key | — | service role (bypasses RLS) | library default [UNVERIFIED] | list calls swallow errors → `[]`; create calls raise |
| Flask → FCM | `messaging.send(topic=…)` | data values stringified | service account | library default | exception → status `notification_failed` |
| Flask → Overpass / TomTom | POST/GET | coords validated on route | TomTom key in query | 20 s / 15 s | swallowed → `[]` (no per-source status) |
| Flask → Redis Agent Memory | SDK async | — | API key | SDK default | swallowed → no memory |
| Flask → Whisper | multipart audio | MIME prefix + 25 MB | Bearer key | 60 s | typed error → 503/400/502 |
| Browser → Supabase | `supabase-js` anon key | RLS | user JWT | — | — |
| GitHub Actions → Next `/api/cron/keepalive` | Bearer `CRON_SECRET` | `!==` string compare | shared secret | 45 s | 200/207 accepted |

---

## 5. End-to-end data flows

### Journey 1 — Emergency assessment (`POST /api/assessment`)

```text
assessment/page.tsx  submitAssessment()  {description, language, [lat, lon if user ticked "share location"]}
  → apiCall → Flask assessment.create_assessment()
      parse_json(AssessmentRequest)      → 422 JSON on schema errors; Flask HTML 415/400 if body isn't JSON
      orchestrate_emergency_assessment():
        1 validate_assessment_request    (empty / >5000 chars / partial or non-finite coords) → ValueError → HTTP 400 JSON
        2 triage_service.classify        [truncate 2000 chars] historical-guard → T1 rules → T2 TF-IDF → ML LR → T3 Groq → unclassified
        3 weather_service.get_weather_safe(lat|17.385, lon|78.4867)     ← hard-coded Hyderabad when no location
              compute_risk_score (rain only) │ on failure: {score 18, level "safe", temp 25.0, "Unavailable (baseline fallback)"}
        4 action_planner.generate_action_plan_with_provenance   (Groq JSON → validate → else authored fallback)
        5 confidence_service.aggregate_confidence_safe(min(triage, weather_avail, plan_provenance))
        6 maps_service.get_nearby_hospitals_safe(lat,lon)   only if coordinates sent (5 km, top 10)
        7 optional SOS (request_sos) — unused by frontend
        7b _fetch_community_insights (keyword/area match on ALL reports + pgvector knowledge)
        8 determine_emergency_level(category, weather_level) ; assemble AssessmentResult (+ legacy fields)
  → database_service.log_emergency(description, level, city)   ← stores raw text, no user id, after the response is built
  ← JSON → AssessmentResultPanel
```

| Step | Failure modes | Fallback | Security note |
|---|---|---|---|
| Input | non-JSON → HTML 415 | none | 5000-char cap but `history`-style abuse possible via repeated calls (no rate limit) |
| Triage | sklearn missing / model train fails / Groq down | Tier skipped → `unclassified`/0.20 | text goes to Groq (Tier 3) — health data leaves the system |
| Weather | key missing, 4xx/5xx, timeout | baseline object with `status=<error>` | key in query string (log exposure risk with `httpx` debug logging) |
| Action plan | Groq unavailable/invalid | authored protocol (`_FALLBACK_PLANS`) | prompt injection via `description` (blast radius: advice text) |
| Persistence | `log_emergency` swallows errors | none | stores health-related free text indefinitely (no retention) |

---

## 6. Frontend audit

| Feature (file) | State | Loading | Error | Empty | Offline | A11y / mobile / emergency usability |
|---|---|---|---|---|---|---|
| **Get help** (`assessment/page.tsx`) | `useState` ×8; presets fill text; location is opt-in checkbox (coords captured **at tick time**, not at submit) | button "Working…" | banner "{error}. Call 112 if urgent." — but `error` is always the generic string | n/a | none: request has no timeout; no queued retry | Presets for the 7 hazards are good for stressed users. No `tel:` link anywhere. Confidence % coloured red for "low" but meaning unexplained. |
| **Result panel** | pure render | — | amber "Some information is incomplete" list from `service_status` | sections hidden when empty | — | Level badge for `Low` uses the **green "safe"** style (`LEVEL_STYLES.low → badge safe`). Weather card shows fabricated 25 °C when weather failed. Contacts are plain text, not tappable. Text is `text-sm` for critical warnings. |
| **SOS modal** (`SosConfirmModal.tsx`) | `open/status/loading`; Escape closes when not loading | "Getting your location…/Sending SOS…" | "Could not send SOS. Something went wrong…" | — | none | Explicit confirm dialog (good; matches Principle 6). `role=dialog aria-modal`, but no focus trap or initial focus. If GPS fails, **no SOS is sent and no "call 112" prompt is shown** (message says "check browser permissions"). Two modal instances are mounted (layout + floating actions). |
| **Dashboard location panel** | `useUserLocation(true)` → requests geolocation on mount; fetches weather, risk, traffic in parallel | text placeholders | failed sub-calls silently ignored (`if (res.ok) set…`) | "No accidents, road work, or heavy traffic reported within 5 km" | none | See C5: shows reassurance text even when every traffic source failed. Sends coordinates to backend and to `openstreetmap.org` (iframe). |
| **Hospitals** | `useEffect` → `/api/hospitals` (**no lat/lon**) | "Loading…" | "Could not load hospitals." | "No hospitals found nearby." | none | Distances are relative to central Hyderabad, not the user (C6). |
| **Shelters** | list from `/api/shelters` | "Loading…" | error text | "No shelters found nearby." | none | No location, no distance, no timestamp; occupancy bar from manual seed data. |
| **Reports** | form + list | none | `alert()` on failure | "No reports yet" | none | Anyone can post; "Checked" badge only if `verified`. `alert()` blocks on mobile. |
| **Chat drawer/widget** | messages in state; session id in `localStorage`; `actor_id` hard-coded `"resq-web-user"` | "…" placeholder | "⚠️ generic" | — | none | Banner steers urgent cases to Get help / 112 / 108 (good, but the guard is only prompt-text). |
| **Voice** (`useVoiceInput`) | MediaRecorder, 60 s cap, `audio/webm;codecs=opus` | "Converting speech…" | inline amber text | — | none | Transcript is *appended* to the textarea, user can edit before submit (good). Language dropdown values (English/Telugu/Hindi) map to Whisper language codes. |
| **Settings/push** | permission → FCM token → `POST /api/device-token` | — | status text | — | — | Service worker gets Firebase config via `postMessage` from the page; it initialises only after that message, so background notifications may not display after the SW is restarted [INFERENCE]. SW imports Firebase 10.14.1 while npm uses ^12 [FACT]. |

**Cross-cutting [FACT]:** no service worker for offline shell, no PWA manifest, no request timeouts, no retry, no `navigator.onLine` handling, no frontend tests, and `apiCall` collapses every failure to one of two generic strings. **Good [FACT]:** all dynamic text is rendered by React (no `dangerouslySetInnerHTML`/`innerHTML` anywhere), map/URL parameters are numeric, and external links use `rel="noreferrer"`.

---

## 7. Backend audit

### Endpoint inventory

| Endpoint | Method | Purpose | Auth | Input | Output | Notable errors / dependencies |
|---|---|---|---|---|---|---|
| `/api/assessment` | POST | full pipeline | **none** | `AssessmentRequest` | `AssessmentResult` | 400 JSON (validation), HTML 415/400/500; Groq, OWM, DB, embeddings |
| `/api/sos` | POST | persist + push | **none** | `{lat, lon, situation?}` (no range check) | `SosResponse` | 200 even when `degraded`; non-`RuntimeError` DB failure → HTML 500 |
| `/api/chat` | POST | info assistant | **none** | history (unbounded), message, city, session_id, actor_id | `{reply}` | always 200 (errors become friendly text) |
| `/api/transcribe` | POST | Whisper | **none** | multipart audio ≤25 MB | `{text,…}` | 400/502/503; upstream error text (≤300 chars) is echoed to the client |
| `/api/weather` | GET | current weather | none | lat/lon (falsy `0` → default) | `WeatherSummary` | 503 JSON |
| `/api/weather/risk` | GET | risk score | none | same | `RiskScore` | **200 with "safe" baseline on failure** |
| `/api/hospitals` | GET | nearby directory | none | lat/lon (default Hyderabad) | `[HospitalOut]` | **200 `[]` on any failure** |
| `/api/shelters` | GET | list | none | — | list | `[]` on failure |
| `/api/reports` | GET/POST | list/create (+file) | **none** | `ReportIn` or multipart | report | 503 JSON; POST has no rate limit or moderation |
| `/api/traffic/nearby` | GET | incidents | none | lat/lon/radius (NaN radius → 500) | `TrafficOverview` | 200 even when partial |
| `/api/knowledge/search` | GET | vector search | none | q, area, limit ≤20 | results | 503 if Supabase off |
| `/api/knowledge/upload` | POST | **public** upload+index | **none** | multipart ≤5 MB | asset | writes to public bucket + embeds |
| `/api/device-token` | POST | register FCM token | **none** | `{token}` | `{status}` | subscribes token to global topic |
| `/api/ml/status` | GET | model stats | none | — | stats incl. server file paths | info disclosure (low) |
| `/api/cron/keepalive` | GET | warm deps | bearer secret (`==`) | — | checks | 401 otherwise |
| `/health` | GET | liveness | none | — | config booleans + model name | shallow (no dependency check) |

**Structural observations [FACT]**
- **No auth, no rate limiting, no request size limits** beyond per-field checks (Flask `MAX_CONTENT_LENGTH` unset).
- **Duplicated SOS logic**: `blueprints/sos.py` and orchestrator stage 7 implement the same state machine with different exception handling (blueprint catches only `RuntimeError` around record creation; orchestrator catches `Exception`).
- **Dead/contradictory code**: `groq_service.run_assessment/parse_response/STATIC_FALLBACK_ASSESSMENT` are unused and implement the *old* "LLM decides EMERGENCY LEVEL" contract that the design forbids; the module docstring still says "Grok (xAI)".
- **Falsy-zero bug**: `request.args.get(..., type=float) or default` in `weather.py`/`hospitals.py` treats `0.0` as missing (harmless in India, wrong in general).
- **Inconsistent error format**: JSON `{"detail": …}` from routes, but Flask's HTML for 400/415/500 (no global error handlers).
- **Sync SDK calls inside `async def` views** (Supabase/Firestore/embedding model) block the worker thread; acceptable at this scale.
- **Business logic in routes**: `reports.py::_create_report_with_attachment` (MIME, extraction, storage, DB, embedding) — belongs in a service.

---

## 8. Emergency Assessment audit

## Feature: Emergency Assessment

### 1. Purpose
Turn a free-text (or voice-transcribed) description into one prioritised response: hazard type, deterministic emergency level, action steps, honest confidence, nearby hospitals and local context.

### 2. Current implementation
`orchestrator.orchestrate_emergency_assessment` (8 stages, §5). **[FACT]** Level is computed by `determine_emergency_level(category, weather_level)`: `electrocution|snakebite|risk=critical → Critical`; `structural_damage|flooding|cyclone|risk=warning → High`; `injury|accident|risk=watch → Moderate`; else `Moderate` if classified, **`Low` if `unclassified`**. The LLM cannot set level or confidence (design principle honoured in this path).

### 3. End-to-end flow
```text
User → assessment/page.tsx → POST /api/assessment → orchestrator → {triage, weather, plan, confidence, hospitals, community}
     → AssessmentResultPanel (badge, confidence %, "Do this now", "Do not do this", "Seek help if", contacts, hospitals, local reports)
```

### 4. Expected behavior
1. Collect: text, optional location (explicit consent), optional language. 2. Validate. 3. Normalise. 4. Triage with an explicit **"unknown ≠ safe"** state. 5. Gather context only where it is relevant to the hazard. 6. Risk from deterministic rules. 7. Action content from vetted protocols first. 8. Confidence broken out per component. 9. Response always leads with a tap-to-call 112/108. 10. UI never colours "we don't know" as "safe".

### 5. Current vs expected
| Aspect | Current | Expected |
|---|---|---|
| Unknown hazard | `Low`, green badge, generic plan (**probe: fire, heart attack, choking, drowning, gas leak, assault, self-harm all → Low**) | "Unclassified — treat as urgent", ≥ Moderate, red/amber, big call button |
| Multi-hazard | Tier 1 conflict → ML/Tier 3 → usually `unclassified`/Low (**flood + accident with injuries → Low**) | Multi-label; level = max of hazards |
| Negation | "There is no flooding here" → flooding, 0.93, **High** | Detect negation / hypothetical / question form |
| Location absent | weather fetched for **17.385, 78.4867**, shown as "live weather" | weather "not available — location not shared" |
| Weather unavailable | 25 °C, score 18, `safe` in `weather` object (status field says why) | `null` values, "unknown" |
| Language | selector accepted, ignored | plan generated/translated in chosen language, or selector hidden |
| Persistence | raw text logged after the fact, no user id | opt-in, retention-limited, linked to user |

### 6. Failure scenarios
Groq down → deterministic plan, `whats_happening` prefixed "Live AI assessment service is currently unavailable" (honest). Weather down → banner lists `weather: …` **and** the weather card still renders synthetic numbers. Hospitals fail → `maps: server_error` banner but hospital section simply absent. DB down → `database: unavailable`; assessment still succeeds (good). Embedding model cold-start (fastembed downloads/loads on first community lookup) can add seconds to the request [INFERENCE].

### 7. Safety considerations
**Dangerous behaviours verified:** unknown/multi-hazard → Low; negation → High; historical guard suppresses current life-threat ("bitten by a snake last week and now cannot breathe" → `unclassified`/Low); emergency numbers are **India-only constants** regardless of where the user is (`DEFAULT_TRUSTED_CONTACTS`). **Good:** LLM cannot lower severity; phone numbers in the structured `emergency_contacts` field come from constants; input coordinate validation is strict in this path.

### 8. Security considerations
Unauthenticated endpoint that fans out to Groq, OpenWeather, embeddings and DB → cost/DoS vector; user text is placed in the LLM prompt (prompt injection can alter advice text); raw descriptions (potentially health/location data) are stored in `emergency_logs` without consent/retention.

### 9. Performance considerations
Worst-case sequential latency ≈ Tier-3 Groq 30 s + weather 10 s + plan 30 s (+ embedding/DB) ≈ 70 s+; typical path (Tier-1 hit) is one weather call + one LLM call. Weather, hospitals and community lookup are independent and safe to parallelise (§29).

### 10. Alternative approaches
(A) Keep single synchronous endpoint (simple). (B) Two-phase: return the deterministic plan immediately, stream LLM elaboration as an optional "more guidance" panel — best for poor connectivity. (C) Fully client-side offline protocol cards with server enrichment.

### 11. Recommended target design [REC]
Phase-B above; a **safety-net lexicon** (fire, smoke, chest pain, not breathing, choking, drowning, gas, weapon/attack, suicidal…) that forces `level ≥ High` and a "call 112 now" banner regardless of classifier output; `unclassified` ⇒ `unknown` level (own colour), never `Low`; multi-label triage; weather gated by hazard relevance.

### 12. Codebase placement
Level/escalation rules → `domain/severity.py`; orchestrator stays in `application/`; nothing severity-related in routes or prompts.

### 13. Testing strategy
Scenario table (§27) with one test per row; property tests "no input yields Low without an explicit non-emergency classification"; golden tests for the unknown-hazard lexicon.

### 14. Validation status
**PARTIALLY IMPLEMENTED.** Pipeline, provenance labels, deterministic level, validation and graceful partial failure are implemented; unsafe defaults above are verified by probe.

---

## 9. Triage audit

## Feature: Triage classification

### 1. Purpose
Decide *what kind* of incident is described (never severity) among: `flooding, electrocution, injury, snakebite, cyclone, structural_damage, accident, unclassified`.

### 2. Current implementation — the actual cascade [FACT]
File `services/triage_service.py::classify`, `app/ml/triage.py`.

| # | Layer | Input | Output / confidence | Threshold / failure | Cost | Multilingual |
|---|---|---|---|---|---|---|
| 0 | **Historical guard** (`last year/month/week`, `years/months/weeks ago`, `used to`) | normalised text | returns `unclassified`, 0.20 **immediately** | any match | µs | English only |
| 1 | Tier 1 regex phrases | normalised text | one category → 0.93; **≥2 categories → `None`** | none / conflict → next | µs | romanised Hindi/Telugu phrases only; **0 native-script phrases** |
| 2 | Tier 2 TF-IDF (1–3-gram) cosine to ~56 authored sentences | text | 0.82 if sim ≥ 0.78 & margin ≥ 0.08; 0.72 if ≥ 0.68 & margin ≥ 0.08 | else `None` | ms | vectoriser fitted on English text |
| 2.5 | sklearn LR on word+char TF-IDF (223 rows) | text | 0.80 if p ≥ 0.55 & margin ≥ 0.08 else 0.72; needs p ≥ 0.32, margin ≥ 0.04. **If it predicts `unclassified` it returns 0.78 and the cascade stops** (Tier 3 never runs) | else `None` | ms | native script + romanised, from 77 hi/te rows |
| 3 | Groq classification, temp 0, prompt "CATEGORY: x", input cut to 500 chars | text | category, confidence fixed **0.35**; unknown label/parse failure → `unclassified` | Groq down → `unclassified` 0.20 | up to 30 s | model-dependent |
| – | default | – | `unclassified`, 0.20 | – | – | – |

### 3. End-to-end flow
```text
text → normalise (NFC, lower, hyphens→space) → historical guard → T1 → T2 → ML → T3(LLM) → unclassified → orchestrator
```

### 4. Expected behavior
Fast deterministic layers first; explicit uncertainty; conflicts and unknowns **escalate** (not default to lowest severity); multi-label output; language-agnostic coverage; evaluation on data the model has never seen.

### 5. Current vs expected
| Aspect | Current | Expected |
|---|---|---|
| Hazard coverage | 7 (no fire, cardiac, choking, drowning, gas, earthquake, assault, poisoning, self-harm) | broader taxonomy + generic "life-threat" class |
| Conflicts | dropped to `unclassified`/Low | multi-label, max-severity |
| Negation/hypothetical | none (`"no flooding here"` → flooding 0.93) | negation & question detection |
| Past-tense guard | discards everything | reduce confidence, still surface |
| T2 margin | `s2` = second-best *example* even if same category, so near-duplicate examples in one category shrink the margin | margin vs best *other-category* score |
| ML "unclassified" | 0.78 confidence, ends cascade | treat as "no signal" → next layer |
| Native script | ML only | rules + multilingual embeddings |
| Model artifact | `data/models/*.joblib` are gitignored → model **trained in-request on first use** (and permanently disabled if the FS is read-only) | trained in CI, versioned, loaded at start |

### 6. Failure scenarios / probe results
| Input | Result |
|---|---|
| "fire in my building and smoke everywhere", "heart attack, severe chest pain", "child is choking", "someone drowning", "gas leak", "two men are attacking me", "want to end my life" | `unclassified` 0.20 → level **Low** |
| "There is no flooding here, just checking" | flooding, T1, 0.93 → **High** |
| "bitten by a snake last week and now cannot breathe" | historical guard → `unclassified` → Low |
| "live wire used to be safe but now sparking, water rising" | `used to` → `unclassified` → Low |
| "flood water rising and also a car accident with injuries" | T1 conflict → `unclassified` → Low |
| "Earthquake shaking, building cracked" | `structural_damage` via T2, 0.72 → High |
| "पानी घर में घुस रहा है" | flooding, ML, 0.80 |
| "mera bhai ko saanp ne kata" | snakebite, ML, 0.72 → Critical |
| "snake plant in my garden" (ML trained without gold texts) | **snakebite** (false positive) |

### 7. Safety considerations
The worst error is a **false negative for a real emergency mapped to the lowest level**. Deterministic rules being auditable is a real strength, but the fall-through default is wrong. "Human/escalation path" does not exist: no dispatcher, no "call now" for low-confidence results beyond a bullet in the generic plan.

### 8. Security considerations
Tier 3 sends user text to a third party. Inputs are truncated (2000/500 chars). `joblib.load` deserialises a pickle from `data/models/` — safe only while that directory is trusted/immutable.

### 9. Performance considerations
T1/T2/ML are sub-millisecond–ms; T3 dominates tail latency. The ML model is trained inside the first request when the artifact is absent [FACT] (≈ seconds on a cold worker) and the TF-IDF matrix is built lazily on first call.

### 10. Alternative approaches
| Approach | Benefits | Drawbacks | When |
|---|---|---|---|
| A Rules only | auditable, instant, offline | brittle across languages/paraphrase | safety net layer |
| B Classical ML (current LR) | cheap, multilingual via char n-grams | needs real labelled data; poor calibration on OOD | after real data collected |
| C LLM zero-shot | broad coverage, handles unseen hazards | non-deterministic, latency, cost, privacy | unknown-hazard *detection* only |
| D Hybrid cascade (current) | cost-efficient | order/threshold errors compound | keep, but change fall-through semantics |
| E Parallel ensemble + agreement | uses disagreement as signal (agree → high; disagree → "urgent/unknown") | slightly more compute | recommended |

### 11. Recommended target design [REC]
Run T1, T2 and ML **in parallel** (all are microseconds); output a **set** of `(hazard, evidence)`; agreement → confidence "high", disagreement → `ambiguous` with severity = max over candidates; add safety-net lexicon and negation/question detectors; ML "unclassified" is just an abstention; T3 only for abstentions and always labelled "AI suggestion"; unknown ⇒ `unknown_urgent`. Thresholds should come from a held-out set (see §26).

### 12. Codebase placement
`domain/triage/` (rules, lexicon, negation), `ml/triage/` (model, training, artifact loading), `application/triage_service.py` (ensemble/policy), `integrations/llm/`.

### 13. Testing strategy
Held-out, independently authored multilingual set (native + romanised + code-mixed); adversarial suite (negation, past tense, multi-hazard, misspellings, ASR errors); per-class recall as a gate (recall for life-threat classes ≥ target) rather than overall accuracy.

### 14. Validation status
**IMPLEMENTED** as designed in the docs; **logic gaps above are verified**; ML tier **BROKEN under the pinned requirements** (C11) and **UNVERIFIED for generalisation** (C10).

---

## 10. SOS audit

## Feature: SOS

### 1. Purpose
Let a user in danger send a location-bearing alert with minimum steps, and know honestly what happened.

### 2. Current implementation [FACT]
Frontend: FAB (or mobile top-bar) → `SosConfirmModal` → **Confirm** → `getCurrentPosition(highAccuracy, 15 s, maximumAge 0)` → `POST /api/sos {lat, lon}` (assessment page variant also sends `situation`). Backend `sos.trigger_sos`: build maps link → `create_sos_record(status=pending_notification)` → if FCM unavailable set `notification_disabled` → else `send_topic_push(topic=resq_alerts, data={lat, lon, maps_link, event_id})` → `update_sos_record(notification_accepted|notification_failed)` → `SosResponse{event_id,status,notification_status,maps_link,message}`.

### 3. End-to-end flow
```text
User → FAB → confirm modal → GPS → POST /api/sos → [persist event] → [FCM topic push] → [update status] → message shown
```

### 4. Expected behavior — production lifecycle
```text
Press → guard against accidents (confirm / hold / countdown with cancel) → capture location {lat, lon, accuracy, captured_at, source}
→ create event with client idempotency key → persist → dispatch to a DEFINED recipient set (trusted contacts, responder org/dispatcher)
→ show tap-to-call 112 immediately → show per-channel delivery state → retry/fallback (SMS deep-link, queue) → allow "I'm safe"/cancel → record final state
```

### 5. Current vs expected
| Aspect | Current | Expected |
|---|---|---|
| Recipient | **All devices subscribed to one FCM topic** (any user who enabled alerts) | trusted contacts from profile (collected but **never used**) and/or a responder endpoint |
| Subscription control | `POST /api/device-token` unauthenticated → `subscribe_to_topic` | authenticated, per-user tokens |
| Payload | exact lat/lon + free-text situation to the topic | to named recipients only |
| Success wording | "alert sent to responders" / "Your live location" | "FCM accepted; delivery not confirmed"; link is static |
| "Delivered" | `notification_accepted` = FCM accepted the message | delivered / acknowledged states |
| Coordinates | no range/finite check on `/api/sos` (NaN and 999 accepted → `maps_link …q=nan,78.4`) | validate; store accuracy + capture time |
| Idempotency | none (3 taps → 3 events + 3 broadcasts, probe) | idempotency key, cooldown |
| Auth / owner | none; `user_id` column exists but is never set | authenticated user id on every event |
| Cancel/resolve | none | cancel / false-alarm / resolved |

### 6. Failure scenarios (all 12 requested cases)
| # | Case | Current behaviour | Robust design |
|---|---|---|---|
| 1 | GPS available | works; no accuracy/timestamp captured | store accuracy, `captured_at`, source |
| 2 | GPS unavailable | modal says "Could not get your location"; **nothing is sent, no call button** | send event flagged `no_location` (+last known/city), show `tel:112` |
| 3 | Internet available | normal | — |
| 4 | Internet unavailable | fetch rejects → generic "Could not send SOS…"; no queue/retry/SMS fallback | offline queue + Background Sync, `sms:`/`tel:` deep-links |
| 5 | Backend unavailable | same generic error; **no `tel:112` prompt in the modal** | fixed emergency-call footer that never depends on the API |
| 6 | Notification service unavailable | record kept, status `notification_disabled/failed`, message says call 112 (**good, honest**) | plus alternate channel (SMS) |
| 7 | Database unavailable | `RuntimeError` → 200 `degraded` message with 112 (**no push attempted**, unlike design doc §8.3); any *other* exception from the DB client (probe) → **HTML 500** | try push regardless; always return JSON |
| 8 | Accidental press | two-step confirm (**good**); no hold/countdown, no cancel after send | short cancel window, "false alarm" state |
| 9 | Repeated presses | button only disabled while request is in flight; each press = new event + broadcast | dedupe by key/time window |
| 10 | App closed after press | in-flight fetch aborted by navigation; no `keepalive`/beacon | `keepalive: true`, service worker queue |
| 11 | Notify OK but persist fails | not reachable (persist happens first — **better than the design doc**) | keep |
| 12 | Persist OK, notify fails | handled: `notification_failed`, sanitised `error_detail`. Mirror case: `update_sos_record` swallows errors, so DB may remain `pending_notification` while the user was told "accepted" | outbox pattern with retry |

### 7. Safety considerations [FACT unless noted]
**False positives:** anyone can POST arbitrary coordinates (no auth) → fake alerts to all subscribers. **Duplicates:** yes. **Lost alerts:** GPS-denied and offline cases. **Misleading success:** "sent to responders". **Stale/incorrect location:** fresh fix requested (good) but accuracy unknown and NaN/out-of-range accepted. **Missing delivery confirmation:** yes. Whether any real responder subscribes to the topic is [UNVERIFIED]; README itself says the prototype does not notify emergency services or contacts.

### 8. Security considerations
Precise-location broadcast to a shared topic; unauthenticated subscription; unauthenticated event creation; no rate limiting; `situation` free text stored and pushed verbatim; FCM data payload visible to every subscriber; `sos_events` RLS enabled with no policies (deny-all to anon — **good**).

### 9. Performance considerations
Two DB round trips + one FCM call, sequential; fine. Client has no timeout, so poor networks can hang the confirm button state.

### 10. Alternative approaches
| Approach | Benefits | Drawbacks |
|---|---|---|
| A Topic push (current) | trivial | broadcast, privacy, no recipient semantics |
| B Per-contact push/SMS/WhatsApp (Twilio/MSG91) | real recipients; works without app installed | cost, consent/verification of contacts |
| C Dispatcher console + webhook | responder acknowledgement, audit | needs an operating organisation |
| D OS-level handoff (`tel:112`, `sms:`) | works offline, zero backend | no server record |
| E Hybrid B + D (+C when an operator exists) | resilient | more engineering |
Integration with India's official 112 service is an [ALT] whose availability/API terms I cannot verify from this project.

### 11. Recommended target design [REC]
Hybrid E: always render call/SMS actions first; server event with idempotency key and state machine (`created → dispatched → delivered → acknowledged → cancelled|resolved|false_alarm`); recipients = the user's verified emergency contact(s) (use the profile data you already collect); delivery-attempt table; outbox worker with backoff; remove the global topic for SOS (keep a separate opt-in topic for *public advisories*).

### 12. Codebase placement
`application/sos_service.py` (state machine, single implementation used by route and orchestrator), `integrations/notify/{fcm,sms}.py`, `domain/sos_events.py`; routes only translate HTTP.

### 13. Testing strategy
Existing `test_step3_sos_persistence.py` (10 tests) covers the notify/persist matrix with mocks. Add: idempotency, NaN/range, non-`RuntimeError` DB failure, outbox retry, no-GPS path, front-end e2e (offline, GPS denied, double tap).

### 14. Validation status
**PARTIALLY IMPLEMENTED.** Persist-then-notify and honest status codes are real and well-tested; recipient model, auth, delivery confirmation, dedupe and offline behaviour are absent.

---

## 11. AI Assistant / LLM audit

### LLM call inventory [FACT]
| # | Call | Provider/model | Prompt | Settings | Output handling | Timeout/retry | Fallback |
|---|---|---|---|---|---|---|---|
| 1 | Tier-3 triage | Groq, `settings.groq_model` | closed-set "CATEGORY: x", user text ≤500 chars | temp 0.0 | regex + closed label set; confidence forced 0.35 | 30 s / none | `unclassified` |
| 2 | Action plan | same | strict-JSON schema in system prompt; user text, category, **city + exact lat/lon**, weather score/level, trusted numbers | temp 0.2, `response_format=json_object` | Pydantic (`ActionPlan`: lengths, URL rejection) + contact sanitiser | 30 s / none | authored category protocol |
| 3 | Chat | same | "general information assistant… direct urgent cases to Get help / 112 / 108" + optional Redis memory | temp 0.4 | raw text, no validation/filter | 30 s / none | fixed "temporarily unavailable, call 112/108" |
| 4 | *(dead)* `run_assessment` | same | legacy 7-section prompt where the LLM outputs "EMERGENCY LEVEL" | temp 0.3 | regex parse | — | static flood-specific plan |
| 5 | Whisper | `whisper-large-v3` | audio | — | JSON `text` | 60 s / none | error to UI |

### Answers
- **Where should an LLM be used?** Rephrasing/translating *vetted* guidance, generating clarifying questions, non-urgent Q&A, unknown-hazard *suggestions* clearly labelled as such.
- **Where should it not?** Severity, emergency numbers, drug/dose/medical-procedure content, evacuation directives, hospital recommendations, SOS decisions. **Verified:** severity/confidence/contacts are not LLM-controlled in the orchestrator path.
- **Can deterministic logic replace it?** For the 7 covered hazards, largely yes — the authored `_FALLBACK_PLANS` already exist; today they are only the fallback.
- **Safety risks [FACT]:** (a) a schema-valid LLM plan **replaces** the vetted plan; (b) validation checks shape, URLs and the contacts field only; numbers or procedures written into `immediate_actions`/`when_to_seek_help` pass (simulated payload: "tight tourniquet… cut the wound… give brandy… call 100 or 1090… call 9876543210" was accepted; `"Police: 1080"` survived the contact filter because the check is substring `"108" in "1080"`); (c) prompt injection through `description`; (d) the fabricated baseline weather (`score 18, level safe`) is passed to the model as its "Weather Risk Reference" even when weather was unavailable; (e) exact coordinates are sent to a third party.
- **Is structured JSON validation sufficient?** No — shape ≠ safety.
- **Malformed output?** Caught → deterministic fallback (**good**). **Refusal?** Non-JSON → same. **API down?** Same, with honest UI note.
- **Model-specific risk [UNVERIFIED]:** if the configured model emits reasoning text, `parse_action_plan_json` slices from first `{` to last `}` and Tier 3 searches `CATEGORY:` anywhere; reasoning containing braces or an example label could mis-parse.
- **Chat:** no deterministic emergency-intent guard — "my father has chest pain" reaches the model with only a system-prompt instruction to redirect; history is client-supplied and unbounded (cost/abuse); replies are untrusted text.

### Feature-format summary (Chat assistant)
**Purpose:** general safety Q&A. **Flow:** `ChatWidget → POST /api/chat → (Redis memory recall) → Groq → reply → (Redis write)`. **Current vs expected:** no output guard, no emergency-intent pre-filter, `actor_id` fixed to `"resq-web-user"`. **Failure:** friendly fixed text. **Safety:** see above. **Security:** unauthenticated, unbounded history, third-party retention. **Alternatives:** static FAQ + retrieval over the vetted knowledge base; LLM with deterministic pre-filter. **Target [REC]:** intent classifier (rules) → if emergency, return the Get-help CTA without an LLM call; otherwise RAG over `knowledge_assets`; cap history/message; require login. **Placement:** `application/chat_service.py`. **Tests:** intent-guard table, injection strings, oversized history. **Status: IMPLEMENTED** (as a general assistant); safety guard **PARTIAL**.

---

## 12. Action Planner audit

## Feature: Action planner

### 1. Purpose
Produce concrete steps, warnings, escalation triggers, clarifying questions and contacts for the classified hazard.

### 2. Current implementation [FACT]
`action_planner_service.generate_action_plan_with_provenance`: always builds a fallback plan first, **then always calls Groq**; on a schema-valid response returns it with source `groq`; otherwise the fallback with source `deterministic`.

### 3. End-to-end flow
```text
category + description + city/lat/lon + weather{score,level} + TRUSTED_CONTACTS
   → prompt → Groq JSON → parse (strip fences, first '{'…last '}') → ActionPlan validation → sanitise emergency_contacts → return (source=groq)
   └─ any failure → _FALLBACK_PLANS[category] (source=deterministic)
```

### 4. Expected behavior
Vetted protocol is the source of truth for every action that can hurt a person if wrong; the LLM may add clarifying questions or rephrase; contacts are deterministic; unknown hazards get a conservative generic plan **plus** explicit "call now".

### 5. Current vs expected (per generated element)
| Element | Input → Decision → Validation → Output (current) | Expected |
|---|---|---|
| `immediate_actions`, `safety_warnings`, `when_to_seek_help` | category+text → **LLM free text** → length ≤500, ≤15 items, no URLs → shown as "Do this now" | vetted text; LLM optional, diffed against allow-list / banned-terms |
| `emergency_contacts` | LLM list → keep items containing a trusted number **as substring** → else constants | constants only, rendered as `tel:` links |
| Numbers inside free text | unchecked | regex scan; reject numbers not in allow-list |
| `questions_to_ask_user` | generated, returned in JSON | **never rendered** by `AssessmentResultPanel` [FACT]; no interactive follow-up |
| Weather influence | score/level text in prompt; fabricated "safe" baseline when unavailable | omit when unavailable |
| Unsafe instruction | passes | blocked or replaced by vetted plan |

### 6. Failure scenarios
Groq down → vetted plan (good); malformed → vetted plan; **valid but wrong → shown** (the case that matters).

### 7. Safety considerations
Authored fallbacks are reasonable in tone and explicitly forbid common folk remedies (e.g. snakebite: no cutting/sucking/tourniquet). **Clinical/disaster-management review of these texts is still required — I cannot certify medical correctness [UNVERIFIED].** Emergency numbers are constants `112 / 108 / 1070` for India only; the correct helpline for a given state/city, police 100, fire 101 and mental-health lines are absent [I]. Contact numbers are deterministic **only in the `emergency_contacts` field**.

### 8. Security considerations
Prompt injection can change advice; precise location leaves the system; no per-IP throttling.

### 9. Performance considerations
An LLM call (≤30 s) is on the critical path even when a vetted plan exists.

### 10. Alternative approaches
| Approach | Notes |
|---|---|
| A Deterministic only | safest, offline, limited to known hazards |
| B LLM-first with validation (current) | flexible; validation weak |
| C Deterministic-first + LLM "enrichment" panel | recommended: user gets vetted plan instantly |
| D Retrieval over vetted knowledge base + LLM formatting | scalable to new hazards without free generation |

### 11. Recommended target design [REC]
C: return the vetted plan in the first response; fetch LLM enrichment separately (labelled "AI-generated, unverified"), with a content policy (allow/deny lists, numeric scan, max-diff from protocol). Render contacts as `tel:`. Render `questions_to_ask_user` as chips that re-submit with the answer.

### 12. Codebase placement
`domain/protocols/` (authored plans as data files, versioned, reviewed), `application/action_plan_service.py`, `integrations/llm/`.

### 13. Testing strategy
Snapshot tests over protocols; property tests "no digit-sequence outside allow-list in any user-visible string"; red-team prompts; contract test that UI renders every returned field.

### 14. Validation status
**IMPLEMENTED** with **weak content validation**; deterministic-first principle **NOT** honoured (protocols are fallback only).

---

## 13. Confidence audit

## Feature: Confidence

### 1. Purpose
Tell the user how far to trust the output, with the reason.

### 2. Current implementation [FACT]
`confidence_service.aggregate_confidence`: `overall = min(triage_confidence, weather_confidence, action_plan_confidence)`; thresholds high ≥ 0.80, medium ≥ 0.50, low < 0.50; `limiting_factor` by tie-break order triage → weather → action_plan. `weather_confidence` = 1.0 if the call succeeded else 0.20. `action_plan_confidence` = 1.0 for deterministic, **0.35 for any Groq plan**. Triage confidence = fixed constants per tier (0.93 / 0.82 / 0.72 / 0.80 / 0.72 / 0.78 / 0.35 / 0.20).

### 3. End-to-end flow
```text
triage.confidence + f(weather availability) + f(plan provenance) → min → level → UI "35% · low · limited by action plan"
```

### 4. Expected behavior
Confidence should mean something that can be checked: either a calibrated probability that the *guidance is appropriate*, or an honest list of which inputs were reliable/unavailable/irrelevant.

### 5. Current vs expected
| Scenario | triage | weather | plan | **overall shown** |
|---|---|---|---|---|
| Rule hit, weather OK, LLM plan | 0.93 | 1.0 | 0.35 | **0.35 low** |
| Rule hit, weather OK, LLM down | 0.93 | 1.0 | 1.0 | **0.93 high** |
| Rule hit, no weather key (snakebite) | 0.93 | 0.20 | – | **0.20 low**, limited by *weather* (irrelevant to a snakebite) |
| No location sent (Hyderabad weather) | – | 1.0 | – | weather "reliable" for the wrong place |
| Unclassified | 0.20 | – | – | 0.20 low |

### 6. Failure scenarios
Invalid inputs → `aggregate_confidence_safe` returns 0.0 / `invalid_input` (good). Corrupt data cannot yield false confidence.

### 7. Safety considerations
The normal (LLM) path is **always "low"**, so the number carries no information there, and the **degraded path looks more trustworthy than the healthy one**. This is intentional by design (tests assert 0.35) but the UI does not explain it. Design doc Signal C was to be the *LLM's self-report* and Signal B a count over *all* dependent services (including maps); the code implements constants and weather only.

### 8. Security considerations
None specific.

### 9. Performance considerations
Negligible.

### 10. Alternative approaches
| Approach | Benefits | Drawbacks |
|---|---|---|
| min (current) | no masking of weak links; simple | mixes heterogeneous constants; irrelevant components penalise; not a probability |
| Weighted average | smoother | lets strong signals hide a weak one — unsafe here |
| Calibrated probability | interpretable | needs labelled outcome data you don't have |
| Uncertainty intervals | honest about spread | needs a probabilistic model |
| **Confidence bands / rule-based reliability states** | transparent, auditable, no fake precision | coarser |

### 11. Recommended target design [REC]
Show **three separate chips** — *Type identified* (rule match / similar example / AI suggestion), *Situation data* (live / unavailable / not relevant), *Guidance* (standard protocol / AI-assisted, unverified) — plus one overall state = worst **relevant** state (`weather` is "not relevant" for snakebite). Drop the percentage until calibration data exists. Keep min-style logic on **ordinal states**, not on ad-hoc numbers.

### 12. Codebase placement
`domain/reliability.py` (pure function over component states, hazard→relevant components map).

### 13. Testing strategy
Truth-table tests per (hazard, component state); UI snapshot tests; keep the existing 32 tests but re-express in states.

### 14. Validation status
**IMPLEMENTED** as specified; **semantically weak** (heuristic constants, not calibrated). Docs and code diverge on Signals B/C.
