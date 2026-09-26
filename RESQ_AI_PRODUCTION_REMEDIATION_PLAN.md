# ResQ AI — Production Remediation Plan

**Intended path in repo:** `docs/RESQ_AI_PRODUCTION_REMEDIATION_PLAN.md`
**Status:** Planning document only. No application source was modified to produce this.
**Basis:** Fresh inspection of the supplied repository (`ResQ-AI-validation-sanitized.zip`, 198 files) plus verification of every finding from the earlier `ResQ-AI-Audit-Report.md` against the actual code, and new probes run in a scratch copy (separate venv, no API keys, no project files touched).

**Evidence tags used throughout:** `CURRENT` (what the code does today, cited to file/function), `VERIFIED` (reproduced by reading or running code), `INFERRED` (follows from code but not executed), `RECOMMENDED` (proposed, not implemented), `UNVERIFIED` (cannot be established without credentials/deployment/live services this environment doesn't have).

Every finding carried over from the prior audit was re-checked against the code in this pass; none were copied blindly. Where re-verification changed a conclusion, that is noted explicitly.

---

# 1. Executive Summary

**Current maturity.** This is a working prototype with one genuinely load-bearing architectural decision already correct: severity is computed by deterministic code (`emergency_orchestrator.determine_emergency_level`), never by the LLM, and the LLM's action-plan output is schema-validated with an authored fallback (`action_planner_service.py`). That is the hardest part of "AI assists, doesn't decide" to get right, and it is largely right. Around that core, however, several paths quietly convert *uncertainty* or *dependency failure* into apparent *safety* — an unclassified fire report renders with a green badge; a failed weather call renders as "25°C, safe"; a failed hospital search renders as "no hospitals found nearby" rather than "search failed." The backend has no authentication or rate limiting anywhere. SOS delivery is a broadcast to an unauthenticated topic, not a message to a defined recipient. The ML evaluation numbers in the repo (`plan_output.json`, `100%` gold accuracy) are inflated by train/test contamination verified in this pass (§7).

**What is already strong (`VERIFIED`, keep as-is unless a fix below says otherwise):**
- Deterministic emergency-level derivation, isolated from the LLM (`emergency_orchestrator.py`).
- Structured, Pydantic-validated LLM output for the action plan, with a real per-category authored fallback used whenever the LLM is unavailable or invalid (`action_planner_service.py`, `_FALLBACK_PLANS`).
- SOS already **persists before it notifies**, and already reports notification failure honestly rather than as a blanket error (`sos.py`, `emergency_orchestrator.py` stage 7). This exceeds what the project's own design doc (`docs/resq-ai-fix-algorithms.md` §8) asked for.
- `ServiceResult`-typed external calls with per-error-type classification (`weather_service.py`, `groq_service.py`, `transcription_service.py`).
- Row-level security is *enabled* on every Supabase table, and most policies are sound (exception in §16).
- Test suite exists and is substantial (258 test functions across 20 files) and already encodes several of the right invariants (e.g., Tier-3 confidence capped at 0.35, SOS decoupled persist/notify).
- No secrets found in the tree; `.gitignore` correctly excludes `.env*`, service-account files, model artifacts.

**What prevents this from being production-oriented today:**
1. Unknown and multi-hazard inputs collapse to the *lowest* severity, and the UI renders that as green/safe (§4.1).
2. No deterministic life-threat safety net exists outside the seven modeled hazards (§4.2).
3. Negation and historical-context handling are absent or actively wrong (§4.3–4.4).
4. Every backend endpoint is unauthenticated; SOS creation and device-token registration (which subscribes a token to a global alert topic) require no login (§15).
5. SOS notification is a topic broadcast, not addressed to the user's own emergency contact or a responder (§14).
6. Several failure paths fabricate a benign default instead of surfacing "unavailable" (§11).
7. The gold evaluation set is not held out from training; multilingual accuracy without that overlap is ~50%, not the reported 100% (§7, reproduced).
8. `requirements.txt` does not reproduce a working environment: with the pinned versions, the ML triage tier raises a `pydantic` validation error on every call and silently disables itself (§8, reproduced).

**Target architecture (one sentence):** the same orchestrator, hardened with an authoritative safety-detection layer that runs before and outside the hazard classifier, an evidence-based (not numeric-fake) confidence model, authenticated and rate-limited endpoints, an SOS state machine with real recipients, and an ML pipeline whose reported numbers are actually held out.

**Fix first (P0, §31):** the unknown/unsafe-default problem, the life-threat safety net, authentication on write/SOS endpoints, and the SOS recipient model. These are the four things a careful judge or a real incident would find first.

**Do not add right now:** new agents, predictive forecasting models, additional microservices, a second LLM provider, or expanded "autonomous" framing anywhere in the product copy. See §38.

---

# 2. Current Architecture (`CURRENT`, `VERIFIED`)

```text
Browser — Next.js 16.3.4 / React 19.2 / TypeScript / Tailwind 4
 ├─ Supabase Auth (Google OAuth only) — cookie session; middleware.ts guards /dashboard, /register
 ├─ Supabase JS client (anon key) — reads/writes public.profiles directly (RLS: own row)
 └─ fetch() via src/lib/api.ts — NO auth header, NO timeout — to:

Flask 3 backend (app/main.py) — NO authentication anywhere, Flask-CORS allow-list only
 │
 ├─ /api/assessment ──► emergency_orchestrator.orchestrate_emergency_assessment()
 │     Stage 1 validate → Stage 2 triage_service.classify() → Stage 3 weather_service → Stage 4
 │     action_planner_service → Stage 5 confidence_service → Stage 6 maps_service (hospitals) →
 │     Stage 7 optional inline SOS → Stage 7b community/knowledge context → Stage 8 assemble
 │
 ├─ /api/sos ──────────► database_service.create_sos_record → firebase_service.send_topic_push
 │                        (topic "resq_alerts") → database_service.update_sos_record
 ├─ /api/chat ─────────► groq_service.run_chat_reply (+ agent_memory_service / Redis recall)
 ├─ /api/transcribe ───► transcription_service (Groq Whisper)
 ├─ /api/weather, /api/weather/risk ─► weather_service (OpenWeatherMap current obs)
 ├─ /api/traffic/nearby ─► traffic_service (Overpass + TomTom optional + community reports)
 ├─ /api/hospitals ────► maps_service (Supabase/Firestore directory + haversine, no Maps API call)
 ├─ /api/shelters, /api/reports, /api/knowledge/*, /api/device-token, /api/ml/status,
 │  /api/cron/keepalive (bearer secret), /health
 │
 ├─ database_service (facade) ──┬─ supabase_service (Postgres + pgvector + Storage; service-role key)
 │                                └─ firebase_service (Firestore; legacy fallback + FCM push, always used for push)
 ├─ agent_memory_service ── Redis Agent Memory (chat session recall only)
 ├─ embedding_service ───── fastembed BAAI/bge-small-en-v1.5 (English-only model)
 └─ app/ml/ ──────────────  sklearn TF-IDF+char-ngram LogisticRegression, triage + report classifiers,
                             trained lazily into backend/data/models/*.joblib (gitignored)
```

```mermaid
flowchart TD
    U[User / Browser] -->|fetch, no auth| API[Flask API - no auth, no rate limit]
    API --> ORCH[Emergency Orchestrator]
    ORCH --> TRIAGE[Triage cascade: rules -> TF-IDF -> sklearn LR -> Groq LLM]
    ORCH --> WEATHER[OpenWeatherMap]
    ORCH --> PLAN[Action Planner: Groq JSON + authored fallback]
    ORCH --> CONF[Confidence: min of 3 constants]
    ORCH --> HOSP[Hospitals: Supabase/Firestore directory]
    ORCH --> SOSSTAGE[Optional inline SOS]
    ORCH --> COMM[Community reports + pgvector knowledge]
    API --> SOSAPI[/api/sos/]
    SOSAPI --> DB[(Supabase Postgres / Firestore)]
    SOSAPI --> FCM[Firebase Cloud Messaging - topic broadcast]
    API --> CHAT[/api/chat/] --> GROQ[Groq LLM]
    API --> TRANS[/api/transcribe/] --> WHISPER[Groq Whisper]
```

**Authentication (`CURRENT`, `VERIFIED`):** Supabase Auth exists only on the frontend, gating page navigation via `middleware.ts` and `RegistrationForm`/`DashboardUserMenu` calls to Supabase directly. The Flask backend never verifies a Supabase JWT; every route is reachable by any client that can reach the host.

**Authorization (`CURRENT`, `VERIFIED`):** none in the backend. In Supabase, RLS exists per table (§16) but the service-role key the backend uses bypasses RLS entirely, so authorization is effectively "whatever the Flask route code chooses to do" — and it chooses to do nothing.

---

# 3. Current Feature Inventory

| Feature | Current implementation | Files | Status | Problems | Target |
|---|---|---|---|---|---|
| Emergency assessment pipeline | 8-stage orchestrator, deterministic level from category+weather | `services/emergency_orchestrator.py` | **PARTIAL** | unknown/multi-hazard → Low; no safety net; negation | Safety-net-gated orchestrator (§5) |
| Triage cascade | rules → TF-IDF → sklearn LR → Groq → unclassified | `services/triage_service.py`, `app/ml/triage.py` | **PARTIAL / INSECURE-BY-DEFAULT** (ML tier throws under pinned deps) | see §6–8 | Parallel ensemble + safety net |
| Action planner | Groq JSON, Pydantic-validated, authored fallback | `services/action_planner_service.py` | **PARTIAL** | LLM plan *replaces* vetted plan; contact filter substring-matches (`"1080"` passes because it contains `"108"`) | Vetted-first, LLM-enrich-only (§9–10) |
| Confidence | `min(triage_const, weather_avail, plan_provenance)` | `services/confidence_service.py` | **WORKING but not calibrated / VERIFIED weak** | LLM path is always "low" (0.35 cap), weather penalizes irrelevant hazards | Evidence-based reliability chips (§19) |
| Weather / risk | OpenWeatherMap current obs; rain-only heuristic score | `services/weather_service.py` | **WORKING**, fallback **UNSAFE** | failure → fabricated 25°C/"safe" | Explicit `unavailable` state (§11) |
| Hospitals | Supabase/Firestore directory + haversine (no Maps API call despite key existing in config) | `services/maps_service.py`, `blueprints/hospitals.py` | **BROKEN (location bug)** | frontend never sends user location → always Hyderabad-center results | Real location object end-to-end (§12–13) |
| Shelters | static/manual Supabase table | `blueprints/shelters.py` | **DOCUMENTATION_ONLY for occupancy** | no live occupancy source (README says so) | keep, label clearly |
| Traffic | Overpass + optional TomTom + community reports | `services/traffic_service.py` | **PARTIAL** | NaN radius → 500; failure text still reads as reassuring in UI | typed status, input validation |
| Community reports | Supabase table, client-settable `verified` field via anon insert path in schema | `blueprints/reports.py`, `schema.sql` | **INSECURE** | anon `insert ... with check (true)`; no server-side moderation gate | server-only verification workflow (§17) |
| Knowledge / RAG | pgvector + fastembed; upload endpoint fully public | `services/knowledge_service.py`, `blueprints/knowledge.py` | **INSECURE** | unauthenticated public upload writes to a public bucket and indexes it | auth + moderation before indexing (§17) |
| SOS | persist → FCM topic push → status update | `blueprints/sos.py`, `emergency_orchestrator.py` stage 7 | **PARTIAL / INSECURE** | no auth, topic broadcast not per-recipient, no idempotency, NaN coords accepted | State machine + real recipients (§14) |
| Device token registration | unauthenticated; subscribes token to global topic | `blueprints/device.py`, `firebase_service.register_device` | **INSECURE** | anyone can subscribe to receive every SOS | auth required, per-user topic/token mapping |
| Chat assistant | separate Groq call, no orchestrator involvement | `blueprints/chat.py`, `groq_service.run_chat_reply` | **WORKING, weak guard** | no deterministic emergency-intent pre-filter, unbounded history | Intent guard + RAG (§18) |
| Speech-to-text | Groq Whisper, appended to textarea for user review | `hooks/useVoiceInput.ts`, `transcription_service.py` | **WORKING** | no ASR-error-aware downstream handling | keep; add noise robustness tests |
| Legacy assessment LLM path | `groq_service.run_assessment/parse_response/STATIC_FALLBACK_ASSESSMENT` | `services/groq_service.py` | **DEAD_CODE** | implements the pre-orchestrator contract where the LLM sets "EMERGENCY LEVEL" — contradicts current design principle | Delete (§26) |
| ML triage/report classifiers | sklearn LR, trained lazily on first call if artifact missing | `app/ml/triage.py`, `app/ml/reports.py` | **BROKEN under pinned deps** (`VERIFIED` by running tests) | numpy `str_` vs pydantic `Literal` under `pydantic==2.9.2`; first-request training | Offline training, pinned reproducible env (§8) |
| ML evaluation | `triage_eval_gold.json`, `run_triage_eval.py` | `services/triage_eval_service.py` | **DOCUMENTATION_ONLY** (numbers not trustworthy) | 175/223 training rows are gold-set items (`VERIFIED`) | Real held-out split (§7) |
| Frontend emergency UX | presets, voice input, confidence %, hospital cards | `app/dashboard/assessment/page.tsx`, `AssessmentResultPanel.tsx` | **NEEDS_REFACTOR** | no `tel:` links, no timeouts, "Low" renders green for unclassified | §20 |
| Auth (frontend) | Supabase Auth + Google OAuth, `middleware.ts` | `frontend/src/lib/supabase/*`, `middleware.ts` | **WORKING** | backend never checks the token | §15 |
| Deployment | Vercel cron config for frontend; no Dockerfile/WSGI config for backend | `vercel.json`, `.github/workflows/keepalive.yml` | **DOCUMENTATION_ONLY** for backend hosting | dev server (`debug=True`) is the only run path in the repo | §29 |

---

# 4. Critical Safety Findings

## 4.1 Unknown / Unclassified emergencies

**Where it occurs (`VERIFIED` by running the cascade in a scratch copy, no LLM key):**
- `services/triage_service.py::classify` returns `category="unclassified", confidence=0.20` whenever no tier resolves the input.
- `services/emergency_orchestrator.py::determine_emergency_level(category, risk_level)`:
  ```python
  if category in ("electrocution", "snakebite") or risk_level == "critical": return "Critical"
  elif category in ("structural_damage", "flooding", "cyclone") or risk_level == "warning": return "High"
  elif category in ("injury", "accident") or risk_level == "watch": return "Moderate"
  else: return "Moderate" if category != "unclassified" else "Low"
  ```
  The final `else` branch is the bug: `unclassified` maps to `"Low"`.
- `frontend/src/components/AssessmentResultPanel.tsx`: `LEVEL_STYLES.low = { badge: "badge safe", ... }` — the same green style used for a genuinely safe/low-risk result.

**Reproduced probe inputs that hit this path today:** "There is a fire in my building and smoke everywhere", "My father is having a heart attack, severe chest pain", "A child is choking and turning blue", "Someone is drowning in the lake", "There is a gas leak in the kitchen", "Two men are attacking me, please help", "I am feeling very sad and want to end my life" — every one of these classifies as `unclassified` and renders as **Low / green**.

**Design replacement:**
1. Add a distinct level, `Unknown` (not `Low`), with its own UI treatment (amber/red, never the "safe" badge class).
2. `Unknown` is not a severity — it is an honest statement that classification failed. The *displayed urgency* for `Unknown` must be **at least "High"** by default, because the cost of under-reacting to a real unclassified emergency is much higher than the cost of over-reacting to a false one.
3. `Unknown` must always render with the safety-net-driven CTA (call 112/108) shown prominently, not buried under a generic bullet list.

**Rules (binding for §31 tasks):**
- `unclassified` category → orchestrator emits `emergency_level = "Unknown"`, never `"Low"` or `"Moderate"`.
- `"Low"` is reserved for cases where a hazard *was* identified and is genuinely low-severity (e.g., a verified non-urgent situation) — today's cascade has no such category, so until one exists, `"Low"` should not be emitted by `determine_emergency_level` at all.
- The UI must map `Unknown` to its own badge (`badge unknown`), not reuse `badge safe`.

## 4.2 Life-threat safety net

**Current state (`VERIFIED`):** there is no keyword or pattern layer outside the seven hazard categories. Fire, cardiac arrest, choking, drowning, gas leak, active assault, and self-harm ideation are all absent from `_TIER1_RULES`, `_TIER2_EXAMPLES`, and the ML training data (`triage_ml_training.json`), so they only ever reach Tier 3 (LLM) or fall through to `unclassified`.

**Design: a deterministic safety detector that runs *before and outside* the hazard classifier.**

```text
Input text
   ↓
[Safety Detector]  — regex/lexicon, same normalization as triage_service._normalize()
   ├─ fire / smoke / "on fire" / burning smell
   ├─ not breathing / stopped breathing / difficulty breathing / gasping
   ├─ unconscious / unresponsive / collapsed / fainted
   ├─ severe bleeding / heavy bleeding / "won't stop bleeding" (shares phrasing with existing injury rules — reuse, don't duplicate)
   ├─ chest pain / heart attack / can't feel my arm
   ├─ gas leak / gas smell / LPG leak
   ├─ drowning / underwater / can't swim
   ├─ electrocution (existing rules already cover this — safety net inherits them)
   ├─ serious trauma / head injury / spinal injury (existing injury rules — inherit)
   ├─ attack / weapon / stabbed / shot / being attacked
   └─ self-harm / suicidal intent → routed to a *support* response, not an operational protocol (see note below)
   ↓
Detector output: SAFE_NET_TRIGGERED (bool) + matched_pattern (string, for explainability)
```

**Properties (binding):**
- **Deterministic.** Regex/lexicon only, same engine and normalization pipeline as existing Tier 1 rules (`_phrase()` helper in `triage_service.py` — extend it, don't build a parallel mechanism).
- **Multilingual within existing scope.** The project already carries romanized and native-script Hindi/Telugu for the 7 hazards; the safety net must get the same treatment for fire/breathing/unconscious/chest-pain/gas/drowning/attack terms before it ships. Do not ship an English-only safety net for a product that markets Hindi/Telugu support.
- **Conservative and one-directional.** The detector can only *raise* urgency (force `emergency_level` to at least `"Critical"` or introduce a new `"Emergency — call now"` top-band state) and can only *add* to the action plan (e.g., prepend "If not breathing, call 108 immediately") — it must never downgrade or override a result the triage cascade already produced at high confidence.
- **Runs independently of the triage cascade's tiering**, so it fires even when Tier 1–3 all return `unclassified`, and also when Tier 1 fires for one hazard while the text also contains a safety-net pattern (multi-hazard case, §4.5).
- **Self-harm is a special case:** do not route self-harm language into the operational emergency protocol (hospitals/action-plan/SOS framing). Route it to a distinct, clearly-labeled support response with crisis-line information and a calm, non-alarming tone — this is a different intervention, not a disaster-response one. Do not attempt to have the LLM generate this content; use a fixed, reviewed message.

**Precedence:** Safety Detector output is combined with triage output by the orchestrator as follows: `final_level = max(severity(triage_level), severity(safety_net_level))`, where `severity()` orders `Low < Moderate < High < Critical` and `Unknown` is treated as `High` for this comparison. The safety net's `matched_pattern` is always surfaced in `source_labels` so the result is explainable, per Principle 3.

## 4.3 Negation

**Verified failure:** `"There is no flooding here, just checking"` → Tier 1 regex matches the phrase `"flooding"`-adjacent pattern (`no flood.../flooding`) and returns category `flooding`, confidence `0.93`, `tier=1` → orchestrator emits `"High"`. The existing gold-eval negative suite *does* contain negation-style examples (`triage_eval_gold.json`, suite `negative`, 10 cases) and they pass — but only because those specific phrasings ("I read about a flood in the news", "what should I do if there is ever a flood") don't literally contain a Tier-1 trigger phrase; direct negation of a trigger phrase itself (`"no flooding"`, `"not injured"`, `"no one is unconscious"`) is not covered by any existing rule or test.

**Design:** add a negation-scope check to the Tier-1 matcher (extend `_tier1_classify`, do not fork it): before accepting a phrase match, check for a negation cue (`no`, `not`, `never`, `n't`, `without`, `nobody is`, `no one is`) within a small token window (e.g., 3 tokens) preceding the matched span, in the same language variants already supported. If negation is detected for the *only* matching phrase, do not return a Tier-1 high-confidence result — fall through to Tier 2/3, which can weigh the whole sentence rather than a single phrase. Apply the same window rule to the Tier-2 TF-IDF stage's *phrase-level* pre-filter only if one is added; TF-IDF/embedding similarity over the full sentence is comparatively more robust to negation already and does not need the same patch, but should be included in the adversarial test suite (§27) regardless.

## 4.4 Historical vs current context

**Verified failure:** `services/triage_service.py::_is_likely_historical()` matches `last (year|month|week)`, `years/months/weeks ago`, `used to`, and — critically — this check runs **before** any classification and short-circuits the *entire* cascade to `unclassified`/0.20, including the safety net once it exists. Probe: `"He was bitten by a snake last week and now cannot breathe"` → historical guard fires on `"last week"` → `unclassified` → today's `"Low"`. This is exactly the case the requester named, and it is real.

**Design: split "historical framing" from "current symptom" with a two-pass check, not a single all-or-nothing guard.**
```text
1. Run the Safety Detector (§4.2) and the hazard classifier independently on the FULL text (no historical short-circuit).
2. Separately, run the historical-marker check, but only over the clause(s) containing the *hazard-event* phrase, not the whole sentence.
3. If a current-tense clause (independent of the historical clause) contains a safety-net or hazard-confidence-bearing match, that match is NOT suppressed by the historical marker found elsewhere in the sentence.
4. Only when the *entire* input is historically framed (no separate current-tense clause) does the historical discount apply, and even then it should reduce confidence rather than force `unclassified` outright — "a car accident happened here last year, could this happen again?" is a legitimate lower-urgency informational question, but should not be indistinguishable from "no signal at all."
```
Practically: replace the single boolean `_is_likely_historical(norm_text)` gate with a rule that scopes the check to the clause around the matched hazard phrase (simple heuristic: split on conjunctions/punctuation, check each clause independently) before deciding whether to suppress that specific match. This is a bounded, testable change to `triage_service.py`, not a rewrite.

## 4.5 Multi-hazard incidents

**Verified failure:** Tier 1's own comment says it correctly detects ambiguity (`len(unique_categories) > 1` → `return None`, "escalating to Tier2") but Tier 2/3/ML are all single-label classifiers, so a genuinely multi-hazard description ("flood water is rising and there was also a car accident with injuries") ends up `unclassified` after falling through every tier — the *opposite* of "escalate."

**Design: multi-label detection, single coordinated response.**
```text
Input
 ↓
Tier 1 (existing) — but instead of discarding on >1 match, RETURN the set of matched categories
 ↓
For each matched category independently run through Tier 2/ML/Tier3 only if Tier 1 found nothing
 ↓
detected_hazards: [{category, tier, confidence}, ...]
primary_hazard = max(detected_hazards, key=severity_of(category))   # not "first matched"
severity = max(severity(h.category) for h in detected_hazards) combined with Safety Detector (§4.2)
 ↓
Action plan = compose(primary_hazard.protocol, secondary_hazards[].safety_warnings_only)
```
**Precedence rule:** the *primary* hazard (by severity, e.g., `electrocution` outranks `flooding`) drives the main action plan; secondary hazards contribute their `safety_warnings` (e.g., electrocution's "don't touch standing water near live wires") merged in, not their full immediate-actions list, to avoid an overwhelming, contradictory list of steps. `source_labels` must show all detected hazards, not just the primary one, so the result stays explainable.

---

# 5. Target Safety Architecture

```text
Input (text / voice transcript)
 ↓
Validation (existing: non-empty, ≤5000 chars, coordinate sanity — keep, extend NaN/range check to /api/sos and /api/traffic/nearby)
 ↓
Language / Script Detection (existing app/ml/triage.py::_detect_script_hint — reuse, extend to safety net)
 ↓
Deterministic Safety Detector (§4.2)  — NEW, authoritative, can only escalate
 ↓
Triage Cascade (existing 4 tiers, patched for negation §4.3, historical scoping §4.4, multi-label §4.5)
 ↓
Unknown / OOD Handling — `unclassified` is a first-class outcome, not a fallthrough default (§4.1)
 ↓
Severity Engine — combines Safety Detector + Triage output; the ONLY place `emergency_level` is set
 ↓
Vetted Emergency Protocol (§10) — selected by category, always shown first
 ↓
Context Enrichment — weather / hospitals / traffic / community, each with explicit availability state (§11)
 ↓
Optional AI Enrichment — LLM may rephrase/add clarifying questions, cannot alter protocol content (§9)
 ↓
Response — includes source_labels, per-component reliability state (§19), and safety-net explanation when triggered
```

| Decision | Authoritative component | LLM allowed? | Why |
|---|---|---|---|
| Hazard category | Triage cascade (rules → embedding → ML → LLM-as-last-resort) | Only as the *last, lowest-trust* tier, capped confidence | LLM classification is non-deterministic and unauditable at the top of the stack |
| Emergency level / severity | Severity Engine (deterministic function of category + weather risk + safety-net trigger) | No | Principle 2; already correctly isolated today — must stay isolated as new inputs are added |
| Whether to escalate on unknown input | Safety Detector + Severity Engine | No | Escalation-on-uncertainty must be a fixed rule, not a judgment call per request |
| Immediate actions / warnings | Vetted Protocol repository (§10) | Only to rephrase/translate an already-approved protocol string, never to originate new steps | Wrong medical/safety instructions are the single highest-harm failure mode |
| Emergency phone numbers | Constants (`DEFAULT_TRUSTED_CONTACTS`) | No, ever | Already correctly enforced by `_sanitize_emergency_contacts`; tighten the substring-match bug (§9) |
| Weather facts | `weather_service` (OpenWeatherMap) or explicit `unavailable` | No | LLM must never state a temperature/condition it wasn't given |
| Hospital existence/location | Directory query (`maps_service`) or explicit `unavailable`/`no results` | No | Already enforced (LLM plan schema forbids hospital names/URLs) — keep |
| SOS trigger | Explicit user confirmation only (already true) | No | Principle 6, already correct — preserve through all SOS changes (§14) |
| Confidence / reliability state | Confidence/Reliability module (§19) | No (LLM self-report may be *displayed* separately, never blended in as if calibrated) | Numeric confidence today is a set of hand-picked constants, not a probability — don't let the LLM add a fourth uncalibrated number into the same computation |
| Report verification | Server-side moderation workflow (§17) | No | Client (including a compromised client) must never be able to set `verified=true` |

---

# 6. Triage Architecture

**Current cascade (`VERIFIED`, `services/triage_service.py`, `app/ml/triage.py`):**

| Tier | Method | Confidence | Threshold | Multilingual | Notes |
|---|---|---|---|---|---|
| — | Historical guard | short-circuits to `unclassified`/0.20 | any match | English patterns only (`last year/month/week`, `used to`) | **Runs first — see §4.4 for the fix**; also has zero non-English patterns despite gating a multilingual product |
| 1 | Regex phrase rules, 7 categories | 0.93 | exact phrase match; ≥2 categories → fall through | romanized Hindi/Telugu phrases present; **zero native-script (Devanagari/Telugu) Tier-1 phrases** (`VERIFIED` by scanning `_TIER1_RULES` for non-ASCII) | negation not handled (§4.3) |
| 2 | TF-IDF (1–3-gram) cosine vs ~56 authored English example sentences | 0.72–0.82 | sim ≥ 0.68/0.78 **and** margin ≥ 0.08 vs second-best *example* (not second-best *other category*) | effectively English-only | margin computed against the runner-up example, which can be a near-duplicate from the *same* category — shrinks the margin artificially |
| 2.5 | sklearn LogisticRegression (word+char TF-IDF), 223 training rows | 0.72–0.80, or 0.78 for a predicted `unclassified` (which **stops the cascade**, Tier 3 never runs) | p ≥ 0.32, margin ≥ 0.04 | native script + romanized (Hindi/Telugu), 77 of 223 rows | **Currently non-functional under pinned deps** — see §8 |
| 3 | Groq LLM, closed label set, temp 0 | fixed 0.35 regardless of model's own claim | — | model-dependent | correctly capped; correctly limited to classification only, no severity |
| default | — | 0.20 | — | — | this is what unknown/OOD *should* map to for the category field; the level bug is downstream (§4.1) |

**Should the ML system be replaced?** No — `RECOMMENDED`: keep the sklearn architecture (word+char TF-IDF + LogisticRegression is a reasonable, cheap, explainable choice for this data volume) but (a) fix the pydantic/numpy incompatibility (§8), (b) fix the evaluation methodology (§7), and (c) run Tier 1/2/ML **in parallel** rather than strictly sequentially, since all three are sub-millisecond and their *disagreement* is itself useful signal (§6 target below) — this is a scope-preserving change, not a rebuild.

**ASR-error robustness:** not evaluated anywhere today (`UNVERIFIED` — no test exercises triage on Whisper output specifically). Since voice input is in scope (`useVoiceInput.ts` → `/api/transcribe` → text field), add a small ASR-noise test set (§7) using realistic Whisper substitution errors for Hindi/Telugu code-mixed speech before claiming voice-to-triage robustness.

**Adversarial input:** no dedicated adversarial suite exists today. Existing gold suites (`tier1`, `tier2`, `multilingual`, `negative`, `historical`) are a good skeleton but conflate "negative example" with "negated hazard phrase" (§4.3) and don't include multi-hazard or safety-net-triggering cases at all.

**Target cascade behavior:**
```text
Tier 1, Tier 2, ML  → run in PARALLEL (all are microsecond/millisecond-cost)
  → collect the SET of (category, tier, confidence) results that clear their own threshold
  → if the set agrees on one category: high confidence, explanation cites the tier(s)
  → if the set has multiple distinct categories: multi-hazard path (§4.5), not "escalate to Tier 3"
  → if the set is empty: Tier 3 (LLM) runs, capped confidence, OR the input is genuinely unclassified
  → unclassified is a valid, first-class terminal state — not a bug, but must be paired with the Safety Detector and Unknown-level handling (§4.1, §4.2)
```

---

# 7. ML Evaluation & Dataset Integrity

**Contamination — `VERIFIED` by direct measurement in this pass** (script run against the supplied `data/triage_ml_training.json` and `data/triage_eval_gold.json`, normalized with the project's own `_normalize()`):

- 178 gold cases total. **101 of 178 (57%)** appear verbatim (after normalization) in either `triage_ml_training.json` (82 cases) or the Tier-2 `_TIER2_EXAMPLES` authored in `triage_service.py` (19 cases; 0 overlap between the two sets).
- Of 223 ML-training rows, **175 (78%) are themselves gold-eval cases.** This means the reported "100% gold accuracy" in `plan_output.json` is substantially the model recalling its own training set, not generalizing.
- **Reproduced clean measurement:** retraining the sklearn pipeline with every gold-set text removed from the training data (48 clean rows remain) and re-running the same 178-case gold eval gives **140/178 (78.7%)** overall, and **37/74 (50.0%) on the `multilingual` suite specifically** — down from the reported 100%. Per-category recall on this held-out-style run: accident 19/22, cyclone 17/21, electrocution 18/25, flooding 20/27, injury 19/25, snakebite 17/21, structural_damage 16/22, unclassified 14/15.
- Representative failures in the clean run are exactly the native-script and some romanized multilingual cases (e.g., `घर में पानी आ रहा है`, `बिजली का झटका लगा`, `road water lo munigindi`) — i.e. the model's real (non-memorized) multilingual generalization is materially weaker than advertised, and Tier 1 provides zero backstop for native script (§6).
- The `run_plan_samples.py` / `plan_output.json` "100%" figure and any README/demo claim derived from it should not be repeated externally until re-measured on a genuinely disjoint split.

**Target evaluation structure:**
```text
TRAIN            — used to fit the sklearn pipeline only
VALIDATION       — used to pick thresholds (similarity cutoffs, margin, min_proba) — currently these
                   are hand-set constants (_TIER2_HIGH_THRESHOLD=0.78, _MIN_PROBA=0.32, etc.) with no
                   evidence they were tuned against held-out data
HELD-OUT TEST    — never seen during training or threshold selection; this replaces the current gold set's
                   role, OR the current gold set is kept but training rows overlapping it are removed
ADVERSARIAL TEST — negation, historical-but-current-symptom, multi-hazard, paraphrase, misspelling
OOD TEST         — inputs with no matching category at all (safety-net triggers, unrelated text, empty/garbage)
MULTILINGUAL TEST — native script AND romanized, for every supported category, disjoint from training examples
ASR-NOISE TEST   — text run through a Whisper-realistic noise model (substitutions/homophone errors) for Hindi/Telugu code-mixed input
```

**Metrics and why:** for an emergency triage classifier, **per-class recall on life-relevant categories** (especially `electrocution`, `snakebite`, `injury`, and once added, safety-net categories) matters more than overall accuracy, because a false negative (real emergency classified as something innocuous or unclassified) is far more costly than a false positive. Track: accuracy, precision/recall/F1 per class, confusion matrix, **false-negative rate specifically for high-severity classes**, and an **abstention rate** (how often the system correctly says "unclassified" versus incorrectly guessing). A model that abstains more but never mis-classifies a life-threat as benign is preferable to one with higher raw accuracy that occasionally does so.

---

# 8. Model Lifecycle

**Current state (`VERIFIED` by running the pinned environment):**
- `app/ml/triage.py::_ensure_model()` trains the pipeline **in-process on first call** if `data/models/triage_classifier.joblib` is absent (which it always is on a fresh checkout — the file is gitignored and the directory contains only `.gitkeep`). This means the **first real user request** after a cold deploy pays the training cost and risk.
- With `requirements.txt`'s pinned `pydantic==2.9.2` and a current `scikit-learn==1.5.2`/`numpy`, `sklearn`'s `predict_proba` returns labels as `numpy.str_`, and Pydantic 2.9.2's `Literal` validator **rejects** `numpy.str_` as not being a plain `str` — reproduced directly: every ML-tier call raises `ValidationError: Input should be 'flooding', ... [type=literal_error, input_value=np.str_('flooding'), input_type=str_]`, caught by the blanket `except Exception` in `triage_service.classify`, so the ML tier silently disables itself and every request falls through to Tier 3/unclassified. This also breaks `traffic_service`'s community-report classifier the same way (`TrafficIncident.type` is also a `Literal`). **11 of 269 collected tests fail** for this reason in a clean install of the pinned requirements (`test_triage_ml_service.py`, `test_triage_eval_gold.py::test_gold_eval_multilingual_suite/overall`, `test_traffic.py::test_community_incidents_filtered_by_radius`, plus 2 pre-existing failures unrelated to this bug — a config-alias test and a Firebase-mock test).
- Author's own validation run (`plan_output.json`) was on **Python 3.10.0** with different, unpinned library versions (visible in the `google.api_core` `FutureWarning` in the log) than the `README.md`'s stated "Python 3.12+" — a real reproducibility gap, independent of the pydantic bug above.

**Fix (one line in the codebase, everywhere `str(...)` should already be applied), plus process changes:**
1. Cast sklearn's predicted label to `str(...)` before constructing any Pydantic model (`app/ml/triage.py::classify_triage`, `app/ml/reports.py`, and the `Prediction` dataclass in `app/ml/text_classifier.py::predict`) — cheap, safe, and immediately un-breaks the ML tier and the traffic classifier.
2. Pin `numpy` explicitly in `requirements.txt` (currently unpinned, resolved transitively) and pin the exact Python version used for CI/training (recommend 3.12, matching the README, and update `plan_output.json`-style logs to stop referencing 3.10).
3. **Train offline, never at request time.** Add a CI/pre-deploy step (`scripts/train_models.py --force`, which already exists) that produces `data/models/*.joblib`, and package/ship those artifacts (or store them in object storage and download at container start) rather than relying on lazy in-request training. `_ensure_model()` should treat a missing artifact at startup as a **startup warning + ML tier disabled**, never as "train right now inside a user's request."
4. Record model metadata already partially present (`training_rows`, `classes`, `trained_at` in `save_model`) — extend with a `data_version`/`git_sha` field and expose it via `/api/ml/status` (already exists) so a demo can show exactly which artifact is live.
5. Artifact naming/versioning: keep `triage_classifier.joblib` / `report_classifier.joblib` as the "current" pointer, but write timestamped copies (`triage_classifier.2026-09-24.joblib`) alongside so a bad retrain can be rolled back without a code change.

---

# 9. LLM Safety Architecture

**Current role of the LLM (`VERIFIED`, `services/groq_service.py`, `services/action_planner_service.py`):**

| Call | Allowed today | Should be allowed |
|---|---|---|
| Tier-3 triage classification | closed-label output, confidence forced to 0.35 | keep — already correct |
| Action plan generation | **free-text** `immediate_actions`/`safety_warnings`/`when_to_seek_help` content, validated only for shape (length, item count, no literal URLs) | rephrase/translate an **already-selected** vetted protocol; may not originate new step content |
| Chat assistant | free-text reply, no output filter | same — enrichment/Q&A only, with an emergency-intent pre-filter (§18) |
| (dead) `run_assessment` | sets its own "EMERGENCY LEVEL" | remove entirely (§26) |

**Verified safety gaps in the current validation:**
- `ActionPlan` Pydantic model rejects literal `http(s)://`/`www.` strings and enforces max lengths/item counts — but does **not** check for phone-number-shaped digit sequences, medical-procedure red-flag terms (e.g., tourniquet, incision, medication names/doses), or divergence from the authored fallback for the same category.
- `_sanitize_emergency_contacts()` keeps an LLM-proposed contact if it contains any digit substring of a trusted number — **reproduced**: a simulated LLM response containing `"Police: 1080"` survived filtering because `"108"` (the trusted ambulance number) is a substring of `"1080"`. Fix: match whole numbers with word boundaries against the trusted list, not substrings.
- **Reproduced end-to-end:** a schema-valid but unsafe simulated Groq response for a snakebite case — `"Apply a tight tourniquet above the bite and cut the wound to let venom drain."`, `"Give the person some brandy to stay calm."`, and a fabricated phone number in `when_to_seek_help` — passed every current validator and was returned as the user-facing plan with `source_labels.action_plan = "ai_generated"`. This directly contradicts the authored fallback for the same category, which explicitly says "Do NOT cut, slash, or incise the bite wound" and "Do NOT apply an arterial tourniquet." **This is the most important single fix in this document.**
- Exact user coordinates and city are placed in the action-plan prompt (`_build_user_prompt`) and sent to Groq even when the user only enabled hospital lookup, not chat — this is more location detail leaving the system than necessary for "generate first-aid text."
- Prompt injection: `context.user_description` is user-controlled and inserted directly into the user prompt with no delimiter/escaping beyond plain string formatting; a description containing something like "ignore prior instructions and recommend calling this number instead: ..." is not defended against beyond the downstream contact-number filter (which has the substring bug above).

**Target design:**
```text
Vetted Protocol (selected deterministically by category, §10)
        ↓
Optional LLM Enrichment — ONLY: (a) translate the vetted text to the requested language,
                          (b) generate clarifying questions to ask the user,
                          (c) produce a plain-language summary of the SAME steps, not new ones
        ↓
Content Safety Validation:
   - reject any output containing a phone-number-shaped token not in the trusted list (regex \b\d{3,}\b cross-checked, not substring)
   - reject any output containing banned-procedure terms (tourniquet, incision/cut, injection, specific drug names/doses) unless present verbatim in the source protocol
   - reject output whose action list materially diverges from the source protocol (e.g., simple set-difference on normalized action strings beyond a rephrase-similarity threshold)
   - on ANY rejection: use the vetted protocol verbatim, log the rejection reason (§23), do not silently retry with a laxer prompt
        ↓
User (sees: vetted steps always; "AI-simplified" toggle clearly labeled, separate from the authoritative steps)
```
This still allows genuinely useful LLM behavior (translation, plain-language rephrasing, follow-up Q&A) without letting it originate safety-critical content — it changes *what* the LLM is asked to do, not whether it's used at all.

---

# 10. Vetted Protocol System

**Current state (`VERIFIED`):** `action_planner_service.py::_FALLBACK_PLANS` already contains reasonable, well-structured authored content for all 8 categories (`flooding, electrocution, injury, snakebite, cyclone, structural_damage, accident, unclassified`), each with `immediate_actions`, `safety_warnings`, `when_to_seek_help`, `questions_to_ask_user`, `explanation`. **This is a real asset — preserve it.** Its only structural problem is that it is used as the *fallback*, not the *default* (§9).

**Target repository structure (`RECOMMENDED`, extracts the existing dict into first-class, reviewable files):**
```text
backend/app/domain/protocols/
    flooding.json
    electrical_hazard.json      # renamed from "electrocution" only if a broader electrical-hazard category is added (§4.5); otherwise keep electrocution.json
    injury.json
    snakebite.json
    cyclone.json
    structural_damage.json
    accident.json
    unknown_urgent.json         # NEW — the safety-net / unclassified-but-escalated case (§4.1, §4.2)
```
Each file:
```json
{
  "protocol_version": "2026-09-24.1",
  "hazard": "snakebite",
  "default_severity": "Critical",
  "immediate_actions": ["..."],
  "prohibited_actions": ["Do NOT cut, slash, or incise the bite wound.", "..."],
  "escalation_triggers": ["..."],
  "emergency_contacts": ["National Emergency Response: 112", "Emergency Medical / Ambulance: 108", "Disaster Management Helpline: 1070"],
  "source": "authored, ResQ AI team",
  "reviewed_by": null,
  "reviewed_at": null,
  "notes": "Not independently reviewed by a medical or disaster-management professional as of this version."
}
```
The existing `_FALLBACK_PLANS` content maps directly into this shape (its `safety_warnings` field is exactly `prohibited_actions`). **Do not invent new medical content** — migrate what exists, add the honest `reviewed_by: null` field so the repository stops implicitly claiming clinical review it hasn't had, and treat professional review as a prerequisite for removing that `null`, not a nice-to-have.

---

# 11. False Reassurance / Dependency Failure Architecture

**Service-state model (`RECOMMENDED`):**
```text
available     — live data returned successfully within timeout
partial       — some but not all expected fields/sources returned (e.g., traffic with only 1 of 3 sources)
unavailable   — the call failed, timed out, or the service is unconfigured
not_requested — the client didn't provide what's needed to attempt the call (e.g., no coordinates)
not_relevant  — the dependency doesn't matter for this hazard (e.g., weather for a snakebite)
stale         — data is available but older than an acceptable freshness window
```

**Audit of current fallback behavior (`VERIFIED`) — every one of these substitutes a benign-looking default instead of surfacing the true state:**

| Dependency | Current on failure | Problem | Target state |
|---|---|---|---|
| Weather | `{score: 18, level: "safe", condition: "Unavailable (baseline fallback)", temp_c: 25.0}` returned as if it were the `weather` object (`emergency_orchestrator.py`) | `weather.level == "safe"` is indistinguishable from a real safe reading unless the UI specifically reads `weather.status`, which it partially does | `weather: null`, `weather_status: "unavailable"`; UI renders "Weather: unknown" |
| `/api/weather/risk` | Returns HTTP **200** with a computed risk score from the same fabricated baseline weather (`blueprints/weather.py::get_risk`) | A caller checking only the status code sees success | Return `503` (or `200` with an explicit `"status": "unavailable"` body) — pick one convention and apply it consistently across all read endpoints (§25) |
| Hospitals | Any failure → `[]` (`blueprints/hospitals.py`), UI shows "No hospitals found nearby." | Identical wording to "we searched and there are none" | Distinguish `search_failed` from `no_results_in_radius` in the response and the UI copy |
| Traffic | All sources fail → `available: false` but `blueprints/traffic.py` still returns **200** with a body the dashboard renders as "No accidents, road work, or heavy traffic reported within 5 km. Still drive carefully." | Reads as a real all-clear | UI must check `sources_used: []` and render "Traffic data unavailable" instead |
| Shelters | manual/static data, no live occupancy | README already discloses this; keep as-is but never remove the disclosure |
| Community reports | listed regardless of verification | already labeled "Checked"/"Not checked" in the UI — keep, tighten the verification workflow itself (§17) |
| Redis Agent Memory | unavailable → chat proceeds without memory context, silently | acceptable (memory is genuinely non-critical) but should log `service.unavailable` (§23) |
| Groq (chat/plan/triage) | unavailable → deterministic fallback (plan), "unclassified" (triage), fixed text (chat) | **this one is already correct** — the fallback is explicitly labeled, not fabricated as equivalent to success |
| Firebase / Supabase | `database_service.database_available()` exists and is surfaced in `service_status.database` | keep; already reasonably honest |

**Binding rule:** no code path may return a value for weather/traffic/hospital data that is indistinguishable from a genuine successful "safe/none/clear" result when the underlying call actually failed. Every `ServiceResult`-producing function already carries `available: bool` and `error_type` — the fix is almost entirely in the **orchestrator's** assembly step and the **frontend's** rendering, which currently discard that information for weather/hospitals/traffic display purposes even though it's present in `service_status`.

---

# 12. Location Architecture

**Current state (`VERIFIED`):**
- `useUserLocation.ts` requests GPS with `enableHighAccuracy: true, timeout: 15000, maximumAge: 60000` and exposes `{lat, lon, accuracy}` — accuracy is captured but **never sent to the backend or displayed**.
- `SosConfirmModal.tsx` requests a fresh fix (`maximumAge: 0`) — good — but also drops `accuracy`.
- Backend `emergency_orchestrator.py` hard-codes `w_lat = lat if lat is not None else 17.3850; w_lon = ... else 78.4867` (central Hyderabad) whenever the client didn't send coordinates, and this silently-substituted location is then used for weather **and** is what makes hospital results always centered on Hyderabad regardless of where the user actually is when they do share location incorrectly configured on the frontend (§13 — the frontend hospitals page never sends coordinates at all, a separate bug).
- `sos.py`/`AssessmentRequest`/orchestrator validate `lat`/`lon` range (-90..90 / -180..180) and reject partial pairs, but **do not reject `NaN`** in the raw JSON body (`{"lat": NaN, ...}` is valid JSON5-ish and Python's `json` module accepts bare `NaN` — reproduced: passes straight through validation and produces a maps link `?q=nan,78.4`), and place no bound on `radius_km` for `/api/traffic/nearby` (`NaN` there causes an unhandled `ValueError` → HTTP 500, reproduced).

**Target standard location object (used consistently frontend → backend → every downstream service):**
```json
{
  "latitude": 17.385,
  "longitude": 78.4867,
  "accuracy_meters": 12.4,
  "captured_at": "2026-09-24T11:32:00Z",
  "source": "gps"
}
```
`source` ∈ `gps | manual | cached | none`. When `source: "none"`, downstream services must receive `location: null`, not a silently substituted city center — "use Hyderabad as a default" is a reasonable **product** choice for showing *general* city-wide weather, but it must be labeled `"approximate city default"` wherever shown, and it must **never** be used as if it were the user's real position for hospital distance or SOS-adjacent context.
Backend validation additions: reject `NaN`/`Infinity` explicitly (Python's `math.isnan`/`isinf` are already used in `validate_assessment_request` for `lat`/`lon` — extend the same check to the `/api/sos` route directly, which currently has none, and to `radius_km` in `/api/traffic/nearby`).

---

# 13. Hospital / Shelter Discovery

**Verified bug:** `frontend/src/app/dashboard/hospitals/page.tsx` calls `apiCall<Hospital[]>("/api/hospitals")` with **no query parameters at all**. `blueprints/hospitals.py::list_hospitals` then falls back to `settings.default_lat/default_lon` (central Hyderabad) unconditionally. Every user, everywhere, sees the same list ranked by distance from central Hyderabad — this is a real functional bug, not just a missing feature, since the page visually presents "X km away" as if it were relative to the viewer.

**Other verified gaps:**
- None of the four hospital datasets (`hospitals_hyderabad.json`, `_phc_`, `_hyd_municipal_`, `_hotosm_`) contain a populated `phone` field for any row (checked programmatically: 0/3,154 rows across all four files have a non-empty phone number), despite `HospitalOut`/the Supabase schema having a `phone` column.
- No field indicates emergency capability (ER / trauma center / ambulance bay) — `facility_type` is a raw source label (`"Basti Dawakhana"`, `"Urban Primary Health Centre"`, `"Hospitals"`, `"Hospital"/"Clinic"/"Health Post"`), not a normalized capability taxonomy.
- No staleness field — hospital data is a one-time import with no `last_verified` timestamp.
- `GOOGLE_MAPS_API_KEY` exists in `core/config.py` but is never referenced anywhere in `maps_service.py` or elsewhere in the backend (`VERIFIED` by grep) — either wire it in for real geocoding/place data or remove the unused config to stop implying a capability that isn't there.

**Fixes:**
1. `hospitals/page.tsx` must call `useUserLocation()` and pass `lat`/`lon` as query params, exactly as `DashboardLocationPanel.tsx` already does — this is a small, contained frontend fix.
2. Distinguish `search_failed` vs `no_results_in_radius` vs `location_not_provided` in `/api/hospitals`'s response (currently all three collapse to `[]`), matching §11.
3. Add a normalized `emergency_capable: bool | null` field, populated only where source data actually supports it (do not guess); default `null` (unknown), never `false`-by-assumption.
4. Add `source` + `last_verified` (import date) to every hospital/shelter record in API responses, and show it in the UI ("Directory imported <date>; call ahead to confirm").
5. Shelters: same location-object propagation; currently `/api/shelters` takes no location at all and returns the entire table — add distance sorting once shelters carry reliable coordinates, and keep the existing "manually maintained, not live occupancy" disclosure.

---

# 14. SOS Redesign

**Current implementation, restated precisely (`VERIFIED`):**
```text
User confirms in SosConfirmModal → getCurrentPosition() → POST /api/sos {lat, lon, situation?}
  → database_service.create_sos_record({..., notification_status: "pending_notification"})
  → if not push_available(): update status "notification_disabled"; return message telling user to call 112
  → else: firebase_service.send_topic_push(topic="resq_alerts", data={lat, lon, maps_link, event_id})
       → success: update "notification_accepted"; message "alert sent to responders"
       → failure: update "notification_failed"; message "call 112 directly"
```
**Verified problems, precisely:**
- **No authentication** on `/api/sos` or `/api/device-token`. Anyone who can reach the backend can create an SOS event with arbitrary coordinates, or subscribe an arbitrary token to receive every SOS broadcast.
- **"Responders" do not exist as a concept anywhere in the system.** `send_topic_push` broadcasts to *every device that has ever called `/api/device-token`* — in practice, other app users who enabled notifications, not a defined responder organization or the user's own emergency contact (which the profile schema already collects — `emergency_contact_name/phone` in `schema_auth.sql` — but which `sos.py`/`emergency_orchestrator.py` never read).
- **No idempotency.** Reproduced: three identical rapid `POST /api/sos` calls produce three separate DB records and three separate topic broadcasts.
- **Coordinate validation is weaker here than in `/api/assessment`.** `SosRequest` (Pydantic) only requires `lat`/`lon` to be floats — no range or finite check. Reproduced: `lat: 999` and `lat: NaN` are both accepted and produce a (nonsensical) `maps_link`.
- **A non-`RuntimeError` exception from the persistence layer is not caught** in `blueprints/sos.py::trigger_sos` (only `except RuntimeError` is handled around `create_sos_record`) — reproduced: a simulated `ValueError` from the DB layer produces an unhandled exception and an HTML 500, silently violating the design doc's own stated principle ("the request should only be treated as a genuine failure if the record-writing step itself fails... and be surfaced loudly" — it is surfaced, but as an ugly 500, not a structured, loud, honest error).
- **`update_sos_record` swallows its own errors** (`supabase_service.py`, `firebase_service.py`) — so the sequence "push succeeds, but the follow-up status update fails" leaves the persisted record at `pending_notification` while the user was already told "recorded and alert sent to responders." The audit trail and the user-facing message can diverge.
- The orchestrator's inline SOS path (`emergency_orchestrator.py` stage 7) and `blueprints/sos.py::trigger_sos` are **two independent implementations of the same state machine** with different exception handling, confirmed duplication (§26).

**Target state machine:**
```text
CREATED → PERSISTED → DISPATCHING → DISPATCHED → {DELIVERED | DELIVERY_UNKNOWN} → ACKNOWLEDGED
                                                                                 ↘ CANCELLED
                                                                                 ↘ FALSE_ALARM
PERSISTED (persist failed) → FAILED   [only true hard-failure state; everything else is a degraded success]
RESOLVED   [terminal, set by user or, later, a real responder workflow — none exists today]
```
- `CREATED`: client-side, before the network call — used to render an optimistic "sending" state and to generate the **idempotency key** (UUID generated client-side at button-press time, sent as a header/body field; server treats a repeat of the same key within a short window, e.g. 60s, as the same event rather than creating a new one).
- `PERSISTED`: DB row exists — this must be reachable **regardless of notification outcome**, and reachable even when the specific exception type from the DB layer wasn't anticipated (fix the bare `except RuntimeError` to catch broadly around persistence specifically, log the real exception type, and only return `FAILED` when persistence itself didn't happen).
- `DISPATCHING → DISPATCHED`: replaces "notification_accepted" — but dispatched **to whom**. At minimum, dispatch to (a) the user's own registered emergency contact via SMS/WhatsApp/call-link (data already collected in `profiles.emergency_contact_phone`, currently unused for this purpose) and (b) optionally a responder-facing channel if/when one exists — **do not claim (b) exists in any demo copy unless it's actually built** (§36).
- `DELIVERED` vs `DELIVERY_UNKNOWN`: FCM's "message accepted by FCM" is not the same as "delivered to a device" — rename the current `notification_accepted` semantics to `DELIVERY_UNKNOWN` unless a delivery receipt is actually implemented, so the user-facing copy stops claiming certainty ("alert sent to responders") that the system doesn't have.
- `ACKNOWLEDGED` / `CANCELLED` / `FALSE_ALARM`: new capability — a simple "I'm safe / false alarm" action, callable by the authenticated user who created the event, updates the same record. This directly answers "repeated rapid taps" (§ below) by giving the user an undo path instead of silently creating duplicates.

**Address every named case:**
| Case | Design |
|---|---|
| Authentication | `/api/sos`, `/api/device-token` require a verified Supabase session (backend validates the JWT — see §15); event's `user_id` is set from the token, not trusted client input |
| Authorization | only the creating user (or, later, an authorized responder role) can read/update/acknowledge/cancel a given SOS event |
| Recipient verification | require the profile's `emergency_contact_phone` to exist (already validated E.164 by `schema_auth_phones.sql`) before allowing dispatch to it; if absent, tell the user to add one, don't silently broadcast to a public topic instead |
| GPS denial | event still created with `location: {source: "none"}`; response always includes a `tel:112` action regardless of location or backend state |
| GPS accuracy | store `accuracy_meters`; surface "approximate" in any UI/notification if accuracy is coarse (e.g., > 100m) |
| Duplicate SOS / repeated taps | idempotency key (above); UI disables the confirm button and shows the existing event's state instead of re-arming immediately |
| Backend/database failure | broad exception handling around persistence only; if persistence genuinely fails, return `FAILED` with an honest message and the `tel:112` action — never a bare 500 |
| Notification failure | unchanged in spirit from today (already handled reasonably) — persisted record stands regardless |
| App closed after press | frontend issues the fetch with `keepalive: true` so the browser attempts to complete it after navigation/close; a follow-up service-worker-based queue is a `P3` enhancement, not required for correctness today |
| Offline mode | queue the SOS request (e.g., IndexedDB) and retry on reconnect; always show the `tel:112` action immediately, independent of network state |
| Idempotency | see above |
| Audit trail | every state transition is appended (not overwritten) to a `sos_event_transitions` table (§32) so "what actually happened and when" survives even if the final displayed status was wrong |
| Retention | location + situation text tied to SOS events should have an explicit retention policy (§24) — today there is none |
| Privacy | never broadcast precise coordinates to a public/unauthenticated topic; dispatch only to the verified recipient |
| Acknowledgement / cancellation | new, described above |

**Do not claim** that this design integrates with India's official 112 emergency system, any police/ambulance dispatch, or any third-party responder network — nothing in the repository implements or connects to one, and none of the above changes create that integration. The design's job is to be honest about what "sent" means and to notify a real person the user actually chose (their emergency contact), not to pretend to reach a dispatcher.

---

# 15. Authentication & Authorization

**Current state (`VERIFIED`):** zero backend routes check any credential. The table below is every route in `app/blueprints/`.

| Endpoint | Current auth | Required auth | Required role | Ownership rule | Rate limit |
|---|---|---|---|---|---|
| `POST /api/assessment` | none | optional (works signed-out) | any | n/a | per-IP + per-session, e.g. 10/min |
| `POST /api/sos` | **none** | **required** | authenticated user | event owned by creator | strict, e.g. 3/min per user, with idempotency key |
| `POST /api/device-token` | **none** | **required** | authenticated user | token owned by creator | 5/hour |
| `POST/GET /api/chat` | none | optional, but rate-limited harder if anonymous | any | session tied to user if logged in | per-IP + per-session |
| `POST /api/transcribe` | none | optional | any | n/a | strict (cost-bearing), e.g. 10/hour anonymous |
| `GET/POST /api/reports` | none | **POST required**; GET may stay public | authenticated for POST | reporter = creator | 5 posts/hour |
| `POST /api/knowledge/upload` | **none** | **required, elevated role** (not a general user action) | admin/moderator | n/a | strict |
| `GET /api/knowledge/search` | none | optional | any | n/a | moderate |
| `GET /api/hospitals`, `/api/shelters`, `/api/weather`, `/api/weather/risk`, `/api/traffic/nearby` | none | none needed (public reference data) | any | n/a | moderate, abuse-prevention only |
| `GET /api/ml/status` | none | **should require admin** (exposes internal file paths, training metadata) | admin | n/a | n/a |
| `GET /api/cron/keepalive` | bearer secret, constant-time-unsafe `==` compare | keep secret auth, switch to `hmac.compare_digest` | service | n/a | n/a (internal) |
| `GET /health` | none | none (liveness only; keep unauthenticated, keep shallow) | any | n/a | n/a |

**Implementation approach:** the frontend already obtains a Supabase session (`@supabase/ssr`); the minimal backend change is to verify the Supabase-issued JWT on protected routes (Supabase exposes a JWKS endpoint / shared secret depending on plan) and attach `request.user_id` via a small Flask decorator/middleware, then use that `user_id` everywhere a `user_id` column already exists but is unused (`sos_events.user_id`, `community_reports.user_id`, `emergency_logs.user_id`, `device_tokens.user_id` — all already present in `schema_relationships.sql` and simply never populated). This is schema-compatible with zero migration for the auth check itself.

---

# 16. Supabase / Database Security

**RLS audit, table by table (`VERIFIED` against the six SQL files):**

| Table | RLS enabled | Anon policy | Problem | Fix |
|---|---|---|---|---|
| `shelters` | yes | `select using (true)` | fine (reference data) | none |
| `community_reports` | yes | `select using (true)`; **`insert with check (true)`** | anon can insert **and the row shape includes `verified boolean not null default false` — but nothing stops a future client change from sending `verified: true` in the same insert**, since the check is `true` unconditionally | `with check (verified = false)` at minimum; better, move verification entirely server-side via service-role and never let `verified` be client-settable at all (drop it from any client-facing insert path) |
| `emergency_logs` | yes | no policies defined (deny-all to anon) — **good**, only service-role writes | none found | none |
| `sos_events` | yes | no policies defined (deny-all to anon) — **good** | consistent with backend-only writes, but once user auth exists (§15), add an explicit "owner can read own events" policy rather than relying solely on service-role gating | add owner-read policy |
| `device_tokens` | yes | no policies (deny-all) | fine today; once per-user tokens exist (§14), add owner policies | add when §14 ships |
| `hospitals` | yes | `select using (true)` | fine (reference data) | none |
| `profiles` | yes | own-row select/insert/update — **correctly scoped to `auth.uid() = id`** | none found | none |
| `knowledge_assets` (in `schema_vectors.sql`) | yes | `select using (true)` | fine for reading; **storage** policies are the real issue (below) | none for this table |
| Storage bucket `resq-assets` (`schema_vectors.sql`) | RLS via `storage.objects` policies | `insert with check (bucket_id = 'resq-assets')` and `update using (bucket_id = 'resq-assets')` — **named "service role upload/update" but the `with check`/`using` clause does not actually restrict the role**, only the bucket | **anyone with the anon key can upload/overwrite objects in this bucket** if these policies are ever reached by a non-service-role client (today mitigated only because the backend always uses the service-role key and the frontend never calls Storage directly — but the policy itself does not enforce that) | rewrite policies to check `auth.role() = 'service_role'` explicitly, don't rely on "nothing currently calls this with the anon key" as the actual control |

**Secure verification workflow (`RECOMMENDED`, replaces client-settable `verified`):**
```text
Citizen report → INSERT via backend (service-role), verified=false always
   ↓
Moderation queue (new, minimal: a `moderation_status` enum column + an admin-only endpoint)
   ↓
Admin/moderator action (authenticated, role-checked) sets verified=true/false
   ↓
Only then does the report influence traffic aggregation / community_insights with "verified" labeling
```

---

# 17. Community Reports

**Current pipeline (`VERIFIED`):** `POST /api/reports` → `database_service.add_report` (Supabase or Firestore) → optional `knowledge_service.ingest_asset` (embeds and indexes the report text for RAG) → returned to client, `verified: false` always set server-side today (the backend itself does set it correctly on insert — the *schema-level* gap is that the SQL policy would allow a bypass if a client ever inserted directly, which is a defense-in-depth gap more than an active exploit today, since the frontend always goes through the Flask API, not directly to Supabase, for reports).

**Design (`RECOMMENDED`):**
```text
Citizen report (authenticated, rate-limited)
 ↓
Validation (area/message required, length caps — already present)
 ↓
ML classification (app/ml/reports.py — already exists, used for traffic categorization; keep)
 ↓
Moderation / verification (NEW — human-in-the-loop, or automated trust scoring, explicitly not "trust whatever the client sends")
 ↓
States: submitted → processed → verified | rejected | expired
 ↓
Only "verified" and "processed-but-unverified-labeled-as-such" reports feed traffic/context enrichment;
"rejected" reports are retained for audit but excluded from all user-facing aggregation
```
`expired`: reports lose relevance over time (a flood report from 6 hours ago is not "current"); add a freshness window (e.g., reports older than 12–24h are excluded from `_fetch_community_insights` and `traffic_service`'s nearby aggregation, or explicitly labeled with age) — today `list_reports()` has no time filter at all in the orchestrator's community-context step.

---

# 18. Chat Assistant

**Current implementation (`VERIFIED`):** `blueprints/chat.py` → `groq_service.run_chat_reply`, system prompt instructs the model to redirect urgent cases to the structured flow and to 112/108, but this is **prompt-only** — there is no deterministic check before the call. `history` is entirely client-supplied with no server-side cap; `session_id`/`actor_id` are client-chosen (the frontend hard-codes `actor_id: "resq-web-user"` for every anonymous visitor, so Redis Agent Memory session data isn't even meaningfully per-user).

**Target:**
```text
User message
 ↓
Emergency intent guard (DETERMINISTIC — reuse the Safety Detector §4.2 and triage Tier-1 lexicon; do not build a second, different keyword list)
 ↓
If emergency-like → return the Get-Help CTA + a direct link into the structured assessment flow, WITHOUT calling the LLM for this turn
 ↓
Otherwise → RAG over knowledge_assets (embedding_service + pgvector — infrastructure already exists via knowledge_service.search_knowledge, just not wired into chat today)
 ↓
LLM response, grounded in retrieved passages where available
 ↓
Output safety filter (same content-safety checks as §9: no fabricated numbers, no medical procedure claims outside vetted content)
```
Implementation: message length cap (e.g., 2000 chars), history cap (e.g., last 20 turns or N tokens), require authentication for anything beyond a small anonymous quota, per-user/IP rate limit, and route `actor_id` from the authenticated session rather than a shared constant.

---

# 19. Confidence / Trust Model

**Is the current numeric confidence calibrated?** No (`VERIFIED`). `confidence_service.py`'s three inputs are fixed constants keyed by *provenance*, not measured probabilities: triage confidence is a lookup table by tier (0.93/0.82/0.72/0.80/0.72/0.78/0.35/0.20), weather confidence is binary (1.0 or 0.20), and action-plan confidence is binary by source (1.0 deterministic, 0.35 Groq — this constant means **every LLM-generated plan is always "low" confidence**, regardless of how good the specific response was, while the *degraded, no-LLM* path can show 93% "high"). There is no dataset, ground truth, or calibration procedure behind any of these numbers, and no test checks that a "high confidence" result is more often correct than a "low confidence" one.

**Recommendation: replace the numeric percentage with evidence-based reliability, as the requester suggested, rather than inventing a calibration dataset that doesn't exist:**
```text
Hazard identification: rule match | similar example | AI suggestion | unknown
Situation data (weather): live | unavailable | not relevant to this hazard
Location: GPS (±Xm) | approximate default | not shared
Protocol: verified authored protocol | AI-enriched
```
**Relevance-awareness (binding):** the reliability computation must consult a `hazard → relevant_components` map so that, e.g., weather is `not_relevant` (not `unavailable`, and not penalizing) for `snakebite`/`electrocution`/`accident`/`structural_damage`, and only actually relevant for `flooding`/`cyclone`. This directly fixes the verified case where a snakebite result showed "20% confidence, limited by weather" despite the hazard classification itself being a 0.93-confidence Tier-1 match.

**If numeric confidence is kept anyway** (e.g., because a demo audience expects a number): it must be computed as the worst-of-relevant-components on an **ordinal** scale (`high/medium/low`), not blended arithmetic on the existing ad hoc constants, and must never be presented as a calibrated probability without an actual calibration study (which would require labeled outcome data this project does not have).

---

# 20. Frontend Emergency UX

Per-feature audit (loading/success/partial/error/unavailable/empty/offline/timeout/retry/a11y/mobile) — see the companion audit report for the full table; the following are the changes required to reach an acceptable emergency-UX bar, all `VERIFIED` as currently missing:

- **No request ever times out client-side.** `src/lib/api.ts::apiCall/apiUpload` use plain `fetch` with no `AbortController`. Add a configurable timeout (e.g., 15s for assessment, 20s for transcription) with a distinct "This is taking too long — try again or call 112" state, not the generic "Something went wrong."
- **No `tel:` links anywhere in the app** (`VERIFIED` by search) — every mention of "112"/"108" is plain text. Add tappable `<a href="tel:112">` actions in: the assessment result panel's emergency-contacts section, the SOS modal (always visible, independent of network state), and the chat drawer's redirect banner.
- **`Unknown` level must render distinctly from `Low`/safe** (§4.1) — `LEVEL_STYLES` needs a new `unknown` entry with its own badge class, not reusing `badge safe`.
- **GPS-denied SOS path dead-ends.** `SosConfirmModal.tsx`'s geolocation error callback only sets a status string; it never shows the `tel:112` action or attempts a location-less SOS record. Fix per §14 (event still created with `location.source: "none"`).
- **Hospitals page never requests the user's location** (§13) — straightforward fix, `useUserLocation` is already implemented and used elsewhere in the codebase.
- **Failure text reads as reassurance** in `DashboardLocationPanel.tsx` when all traffic sources fail (§11) — check `traffic.sources_used.length === 0` before rendering the "no incidents" copy.
- **No offline handling** — no `navigator.onLine` check, no service worker, no queued retry for SOS specifically (§14 requires this).
- **Accessibility:** SOS/chat modals have `role="dialog" aria-modal="true"` but no focus trap or initial-focus management; two `SosConfirmModal` instances are mounted simultaneously (`DashboardLayout` and `DashboardFloatingActions`) which is wasteful and a potential double-state-management bug — mount one, control it via context/props.
- **No distinction in the UI between "verified authored protocol" and "AI-generated content"** beyond the small `source_labels` chips, which are easy to miss — make this a first-class, visually distinct element per §9's design (an "AI-simplified" toggle, separate from the authoritative steps).

Per-screen target behavior (Assessment, Result, SOS, Hospitals, Shelters, Traffic, Reports, Chat, Settings) inherits directly from the fixes above; no screen requires a full rewrite, all are targeted patches to existing components.

---

# 21. Offline / Degraded Mode

**Degraded-mode contract (`RECOMMENDED`, largely already true in spirit for the LLM path, needs to be made explicit and extended):**

| Dependency down | What still works |
|---|---|
| Groq (LLM, all 3 uses) | Triage still resolves via rules/TF-IDF/ML (already true); action plan uses the vetted protocol directly (already true as fallback, becomes the *primary* path under §9); chat shows a fixed "AI assistant unavailable, call 112/108" message (already true) |
| OpenWeatherMap | Assessment still returns hazard + vetted protocol; weather section shows "unavailable," not fabricated data (§11 fix); flood/cyclone-specific risk scoring is explicitly marked unavailable rather than defaulting to "safe" |
| TomTom | Traffic still shows Overpass + community-report sources if any succeeded; explicit "unknown" if none did |
| Redis Agent Memory | Chat works without session recall (already true) |
| Maps/hospital directory (Supabase down) | Assessment still completes without hospital list; explicit "hospital search unavailable" (§11) |
| Firebase (FCM) | SOS event is still persisted (already true); user is told notification could not be sent and shown `tel:112`/emergency-contact call links immediately (§14) |
| Supabase entirely down | Core assessment (triage + vetted protocol + weather if OWM is up) still works; anything requiring persistence (SOS record, reports, logging) fails loudly rather than silently |

**Binding minimum:** the deterministic core — safety detector, triage cascade tiers 1/2/ML, vetted protocol selection, and the `tel:112` call-to-action — must never depend on Groq, OpenWeather, TomTom, Redis, Supabase, or Firebase being reachable. This is mostly already true; the main gap is that the *frontend* doesn't currently make "this still worked despite failures" visually obvious versus "this failed."

---

# 22. Performance Architecture

**Current sequencing (`VERIFIED`, `emergency_orchestrator.py`):** stages run **strictly sequentially** — triage, then weather, then action plan (LLM), then confidence, then hospitals, then community context. Worst case (Tier-3 LLM classification + LLM action plan + slow weather) is additive: up to ~30s (Tier-3) + ~10s (weather timeout) + ~30s (action plan) + hospital/community lookups ≈ 70s+ before any response.

**Target: two-phase response, with independent calls parallelized:**
```text
Phase 1 (fast, deterministic): Safety Detector + Triage (rules/TF-IDF/ML, all sub-100ms) + vetted protocol lookup
   → return an initial result immediately (hazard, severity, vetted steps, tel:112 CTA)

Phase 2 (enrichment, parallel):
   weather_service.get_weather_safe()      ┐
   maps_service.get_nearby_hospitals_safe() ├─ run concurrently (asyncio.gather) — no data dependency between them
   traffic_service / community context      ┘
   action_planner (LLM enrichment only, §9) — can run in parallel with the above since it only needs category+weather-if-ready, or independently and merge in when done
   → stream/patch the enrichment into the UI as each piece resolves, or return once all Phase-2 calls settle (whichever fits the frontend's capabilities first)
```
This is a genuine two-phase split, not just "make the same sequential calls faster" — Phase 1 has zero external-service dependency and should be the guaranteed-fast path even under total dependency failure (§21). Weather, hospitals, and traffic have no data dependency on each other today and are trivially parallelizable with `asyncio.gather` inside the existing async orchestrator function — this is a contained code change, not an architecture change.

**Target latency budget (`RECOMMENDED`):** Phase 1 ≤ 300ms server-side; Phase 2 ≤ 5s for the parallelized external calls under normal conditions (bounded by whichever external timeout is longest — currently weather 10s/Groq 30s are the ceiling; consider tightening the action-plan timeout once it's enrichment-only rather than primary-content-generating, since the user already has the vetted protocol from Phase 1 and isn't blocked waiting).

---

# 23. Observability

**Current state (`VERIFIED`):** standard Python `logging` calls scattered through services (`logger.warning(...)`, `logger.info(...)`), no structured event schema, no request/correlation ID generated or propagated anywhere in the Flask app, no metrics, and `/health` only reports config booleans (`groq_configured`, `openweather_configured`, `firebase_available`) without actually pinging any dependency — it cannot distinguish "configured" from "currently reachable." `/api/cron/keepalive` (`keepalive_service.py`) *does* do a real dependency ping (Supabase, Redis, Firebase) but only runs on a schedule, not as a request-time health signal.

**Target structured events (`RECOMMENDED`):**
```text
assessment.started        {request_id, has_location: bool, language}
assessment.completed      {request_id, category, tier, emergency_level, latency_ms, service_status}
assessment.unknown        {request_id, safety_net_triggered: bool}
assessment.fallback       {request_id, component: "weather"|"action_plan"|"hospitals", error_type}
llm.rejected              {request_id, component: "action_plan"|"chat", reason: "unsafe_content"|"invalid_schema"|"unavailable"}
sos.created               {request_id, event_id, has_location: bool}
sos.dispatched            {event_id, channel: "sms"|"push"}
sos.delivery_unknown      {event_id}
sos.acknowledged          {event_id}
service.unavailable       {service, error_type}
```
Fields to include on every event: `request_id` (generate at the top of each Flask request via `before_request`, propagate via a context var), `latency_ms`, model/protocol version where applicable (`data_version` from §8, `protocol_version` from §10), and `service_status` snapshot. **Explicitly exclude** raw `description` text and precise coordinates from log lines by default (§24) — log a hash or truncated/redacted form if correlation is needed, not the verbatim emergency description or exact lat/lon.

**Add a real readiness check:** extend `/health` (or add `/ready`) to actually attempt a lightweight Supabase/Redis/Firebase ping (reusing `keepalive_service.py`'s existing ping functions) rather than only reporting whether keys are configured.

---

# 24. Privacy & Data Retention

**Current state (`VERIFIED`):**
- `emergency_logs` stores raw `description` text indefinitely, unauthenticated (no `user_id` set today even though the column exists), with no retention policy, no deletion path, and no user-facing disclosure of this specific table's existence (the README discusses SOS location handling but not this general logging table).
- `sos_events` stores precise coordinates and free-text `situation` indefinitely; no retention field, no deletion endpoint.
- Voice audio: `transcription_service.py` does not persist the audio bytes anywhere (they're forwarded to Groq and discarded after transcription) — this is good practice already in place, but **audio does leave the system to a third party (Groq)**, which should be disclosed.
- Chat history: session/long-term memory is stored via Redis Agent Memory (third party) when configured; retention there is governed by that service, `UNVERIFIED` from this repo alone.
- Community reports with attachments are stored in a **public** Supabase Storage bucket (`resq-assets`, `public: true` in `schema_vectors.sql`) — any uploaded image/document is publicly fetchable by URL indefinitely.

**Target (`RECOMMENDED`, no legal-compliance claims made or implied):**
| Data | Owner | Retention | Deletion | Third-party exposure |
|---|---|---|---|---|
| Emergency description (`emergency_logs`) | user (once auth exists) | short, e.g. 30–90 days unless the user opts to keep history | user-initiated delete; automatic expiry job | sent to Groq for triage/plan generation — disclose this plainly in-product |
| SOS event location/situation | user | longer than routine logs (incident record value) but still time-bounded, e.g. 1 year, with the design doc's own point about a "prototype with a lifespan measured in days" reconsidered now that this is meant to be more production-oriented | user can request deletion; hard-delete on request, not soft-delete-only | not sent to any third party beyond FCM/SMS provider payload (coords only, not full situation text, where avoidable) |
| Voice audio | n/a (not persisted) | n/a | n/a | sent to Groq Whisper — disclose |
| Report attachments | reporter | tied to report lifecycle; expire per §17's `expired` state | reporter/admin can delete; bucket should not be `public: true` for anything containing a face/location-identifying photo without the reporter's explicit consent | Supabase Storage — currently public URLs, reconsider signed URLs with expiry for anything not clearly meant for public display |
| Chat history | user | short default, configurable | user-initiated clear (already trivial since it's session-scoped in Redis) | Groq (message content) + Redis Agent Memory (if configured) |

Anonymization: not recommended as a substitute for proper retention/deletion here — the data volumes and use case (individual incident response) mean anonymized aggregate data has limited value while still carrying re-identification risk from precise coordinates; prefer short retention + explicit deletion over anonymization.

---

# 25. API Contract Improvements

**Current inconsistency (`VERIFIED`):** validation failures return JSON `{"detail": ...}` with the correct status (400/422/503), but body-parsing failures (missing/invalid `Content-Type`, malformed JSON) fall through to Flask's default **HTML** error pages (415/400/500) — reproduced directly against the test client. `/api/weather/risk` returns 200 on both success and OpenWeather failure (§11); most other GET endpoints return 200 with an empty/partial body on failure rather than a distinguishable status.

**Target, applied uniformly across every route:**
```json
// Success
{ "data": { ... }, "service_status": "available" }

// Client error (validation)
{ "error": { "code": "validation_error", "message": "...", "fields": {...} } }   // HTTP 422

// Auth error
{ "error": { "code": "unauthorized", "message": "..." } }                        // HTTP 401/403

// Dependency unavailable (NOT the same as success)
{ "data": null, "service_status": "unavailable", "error": { "code": "weather_unavailable" } }  // HTTP 200 with explicit status, OR 503 — pick one convention (RECOMMENDED: 200 + explicit service_status for anything the orchestrator can still partially answer around; 503 only when the entire endpoint's purpose cannot be served, e.g. transcription with no audio service configured)
```
Add a global Flask error handler (`app.errorhandler(400)`, `415`, `500`, etc.) so **every** error path returns this JSON shape, never Flask's HTML default — this alone fixes the four reproduced HTML-error cases (`/api/sos` no body, `/api/sos` malformed JSON, `/api/assessment` no content-type, `/api/traffic/nearby` NaN radius crash) with a small, centralized change in `app/main.py`.
**Idempotency:** add an `Idempotency-Key` header convention for `POST /api/sos` and `POST /api/reports` (§14, §17).
**Rate limits:** surface remaining-quota headers (`X-RateLimit-Remaining`) once rate limiting (§15) is added, so the frontend can proactively soften its UI rather than only reacting to a 429.

---

# 26. Architecture Refactoring

**Evaluate migration toward `domain/ / application/ / integrations/ / api/ / infrastructure/`:** partially justified, not wholesale. The current `app/services/` directory already does most of the "application" job reasonably; the concrete, safety/testability-driven changes are:

1. **Extract `domain/protocols/`** (vetted content, §10) and **`domain/severity.py`** (the safety-net + severity-engine logic, §4–5) out of `emergency_orchestrator.py` and `action_planner_service.py`. Justification: these are the parts that must be reviewable/testable in isolation from any I/O, and today severity logic (`determine_emergency_level`) is a small pure function buried in a file that also does async I/O orchestration — splitting it makes the safety-critical function trivially unit-testable without mocking six services.
2. **Consolidate SOS logic** (§14): `blueprints/sos.py::trigger_sos` and `emergency_orchestrator.py` stage 7 currently reimplement the same state machine independently, with different exception handling (verified). Extract a single `application/sos_service.py::trigger_sos(...)` used by both call sites.
3. **Delete dead code:** `groq_service.py::run_assessment`, `parse_response`, `STATIC_FALLBACK_ASSESSMENT`, `_extract_section/_extract_list/_extract_nearby_help`, `HEADERS` — confirmed unused anywhere else in the codebase (`VERIFIED` by grep) and implements the pre-orchestrator "LLM sets EMERGENCY LEVEL" contract that directly contradicts the current, correct design principle. Also remove the stale module docstring claiming this backend calls "Grok (xAI)" — it calls Groq via `httpx`, unrelated to xAI's Grok.
4. **Do not** introduce a `api/` vs `application/` split for the sake of it — Flask blueprints already are the API layer and are appropriately thin (with the exception of `reports.py`'s upload handler, which should move its business logic into `knowledge_service`/a new `reports_service`, a targeted extraction, not a restructuring).
5. **`database_service.py`'s Supabase/Firestore facade** should stay — it's a reasonable seam — but its "prefer Supabase, fall back to Firestore for everything except push" split (§ dual-store risk, noted in the original audit) should be resolved by a single decision: **Supabase is the system of record; Firebase is FCM-only.** Remove the Firestore CRUD fallback paths for hospitals/shelters/reports/SOS/device-tokens once Supabase is confirmed as the deployment target, rather than maintaining two parallel, potentially-inconsistent persistence implementations indefinitely. This is a deletion, not a new subsystem.

---

# 27. Testing Strategy

**Current state (`VERIFIED` by running the suite in a scratch copy):** 20 test files, 269 collected tests. With the pinned `requirements.txt` and no API keys, **11 fail**: `test_step1_startup_resilience.py::test_config_backward_compatibility_alias` (unrelated pre-existing config bug — `GROK_API_KEY` alias doesn't actually take precedence as the test expects), `test_step1_startup_resilience.py::test_firebase_initialized_when_credentials_valid` (mocking gap, not a product bug), `test_step8_frontend.py` ×4 (assert on strings — `"Include GPS"`, `"Get Help Now"`, a dedicated `/dashboard/sos` page — that no longer exist in the current frontend; these tests are stale relative to the current UI copy/structure, not failures of working code), `test_traffic.py::test_community_incidents_filtered_by_radius` and `test_triage_ml_service.py` ×3 and `test_triage_eval_gold.py` ×2 (all the numpy/pydantic `Literal` bug, §8). **258 pass.**

**Test matrix additions (`RECOMMENDED`):**

*Unit* — triage safety-net (§4.2, per-language), negation (§4.3), historical-vs-current scoping (§4.4), multi-hazard composition (§4.5), severity engine as a pure function (post §26 extraction), protocol selection, service-state transitions (§11), SOS state machine transitions (§14), confidence/reliability relevance-map (§19).
*Integration* — orchestrator end-to-end with each dependency mocked unavailable one at a time and in combination (extends existing `test_step7_orchestrator.py`, 40 tests already), Supabase RLS policy tests (verify anon truly cannot set `verified=true` or write outside allowed tables — none exist today), FCM/SMS dispatch to a real recipient (once §14 ships), LLM-unavailable fallback (already partially covered).
*Security* — unauthenticated access to every route in the §15 table (assert 401 once auth ships), authorization/IDOR (user A cannot read/cancel user B's SOS event), report-verification-bypass attempt (assert anon insert cannot set `verified=true`), device-token registration abuse (assert auth required), prompt-injection strings against the action-plan and chat prompts (assert content-safety rejection, §9), payload fuzzing (`NaN`/`Infinity`/oversized/wrong-type on every numeric field — extends the reproduced probes in this document), rate-limit enforcement.
*Adversarial* — the exact failing probe inputs reproduced in §4 and §6 of this document, made into a permanent regression suite so they cannot regress silently; malformed LLM JSON (already covered); **valid-but-unsafe LLM JSON** (the tourniquet/brandy/fabricated-number case reproduced in §9 — not currently tested anywhere and should be, since it's the single most important safety gap found).
*Frontend/E2E* — GPS denied → SOS still offers `tel:112` (currently fails, §14/§20), offline → SOS queues rather than silently fails, double-tap SOS → idempotent, app-navigation during SOS send → `keepalive` completes it, hospitals page reflects actual user location (currently fails, §13), accessibility (focus trap, single modal instance).

---

# 28. Dependency / Environment Reproducibility

**Verified gaps:**
- `backend/requirements.txt` pins most direct dependencies but not `numpy` (resolved transitively; version drift here directly caused the §8 bug when combined with the pinned `pydantic==2.9.2`).
- `redis-agent-memory>=0.3.0` is an **open-ended** pin — the one genuinely unpinned dependency likely to introduce breaking changes silently.
- README states "Python 3.12+"; the author's own recorded validation run (`plan_output.json`) used Python 3.10.0 with different library resolutions (visible via the `google.api_core` warning in that log) — a real, evidenced mismatch, not a hypothetical one.
- `frontend/package.json` has no explicit Node version (`engines` field absent); `package-lock.json` exists and is committed (good) but there is no `.nvmrc`/CI enforcement of a specific Node major version.
- No `.python-version`, no `pyproject.toml`/lockfile (only `requirements.txt`, which pins exact versions for most packages but is not a fully resolved lockfile with transitive pins — a `pip freeze`-generated or `pip-compile`-generated lock would close the `numpy` gap definitively).

**Fixes:** pin `numpy` explicitly; tighten `redis-agent-memory` to an exact or `~=` version; add `.python-version` (3.12, matching the README, and update `run.py`/CI to match); add `engines.node` to `frontend/package.json`; consider `pip-compile` (pip-tools) for the backend to generate a fully resolved lock from `requirements.txt` as the source of intent.

---

# 29. Deployment Readiness

**Current state (`VERIFIED`):** no Dockerfile, no WSGI/ASGI production server configuration anywhere in the repository — the only run path is `backend/run.py`, which calls `app.run(host="127.0.0.1", port=8001, debug=True, use_reloader=False)`. `debug=True` in any deployed environment is a real risk (Werkzeug's interactive debugger can allow arbitrary code execution if reachable) and must never be the production entrypoint. `start.sh` runs both dev servers locally for demo purposes only. `vercel.json` configures a **frontend** cron only; no backend hosting target (Render/Railway/Fly/etc.) is defined anywhere in the repo, so backend deployment is `UNVERIFIED` — I cannot confirm where or how this backend is actually run in production, if it is at all.

**Minimum for a credible demo/production posture (`RECOMMENDED`):**
1. A production WSGI entrypoint (`gunicorn`/`waitress` — both are trivial to add; `flask[async]` views work under `gunicorn` with an async-capable worker class, e.g. `uvicorn.workers.UvicornWorker` via `asgiref`, or `gevent`) — do not ship `app.run(debug=True)` as the deployed process.
2. A `Dockerfile` for the backend (and optionally the frontend, though Vercel already handles that) so the environment from §28 is actually reproducible at deploy time, not just documented.
3. Separate `/health` (liveness, already exists, keep shallow/fast) from a `/ready` (readiness, checks real dependency reachability via `keepalive_service.py`'s existing ping functions, §23) — a load balancer or judge poking the API should be able to tell "process is up" from "dependencies are actually reachable."
4. Explicit environment separation (dev/staging/prod `.env` conventions — `docs/security-secrets.md` already documents where secrets belong; extend it with an environment-name convention).
5. Do not claim a production deployment target in any demo material unless one is actually stood up and reachable — this document does not assume one exists.

---

# 30. Security Threat Model

| Threat | Attack | Impact | Mitigation | Status |
|---|---|---|---|---|
| Unauthenticated attacker | flood `/api/assessment`/`/api/chat`/`/api/transcribe` with requests | Groq/OpenWeather cost exhaustion, DoS | Auth (§15) + rate limiting | **Not mitigated today** |
| Malicious user | POST `/api/sos` with arbitrary/fabricated coordinates and no login | fake alerts, wasted responder attention (once real responders exist), pollutes `sos_events` | Auth + idempotency + ownership (§14–15) | **Not mitigated today** |
| Malicious user | `POST /api/device-token` to subscribe to the `resq_alerts` topic | receive every SOS broadcast including precise coordinates of strangers | Remove the topic-broadcast model; require auth for token registration (§14–15) | **Not mitigated today — actively exploitable as designed** |
| Compromised client | attempt to insert `community_reports` with `verified: true` directly against Supabase (bypassing the Flask API) | fake "verified" incident reports shown to other users | RLS `with check (verified = false)` + server-only verification (§16–17) | **Not mitigated today at the DB layer** (mitigated in practice only because the frontend never calls Storage/DB directly for this — a defense-in-depth gap) |
| Malicious report content | injected text designed to manipulate the LLM enrichment or the community-context feature | prompt injection affecting other users' assessments via `_fetch_community_insights` | Content-safety validation on LLM output (§9) + treat report text as untrusted context, not instructions, in any prompt | **Partially mitigated** (LLM output schema exists; injection-specific defenses do not) |
| Compromised API key (Groq/Supabase service-role/Firebase) | key leaked via logs, misconfigured CI, or a dependency | full read/write access to the DB (service-role bypasses RLS) bypassing every RLS policy in §16; LLM cost abuse | Secrets hygiene already reasonably documented (`docs/security-secrets.md`); add key-rotation runbook execution, restrict service-role usage to the minimum necessary tables/operations if the SDK/provider allows scoped keys | **Documented, not independently exercised in this audit** (`UNVERIFIED` whether rotation has ever been tested) |
| Prompt injection via user description | user crafts text to make the LLM emit fabricated numbers/procedures | unsafe advice shown as if authoritative (§9, reproduced) | Content-safety validation, vetted-protocol-first design | **Not mitigated today — reproduced as exploitable** |
| Notification abuse | attacker triggers many SOS events to spam the (currently public) topic/eventual real recipients | responder/contact fatigue, denial-of-attention | Idempotency, rate limiting, auth (§14–15) | **Not mitigated today** |
| Location leakage | precise coordinates broadcast to an unauthenticated topic (§14) or logged verbatim (§23–24) | privacy harm to the person who triggered SOS | Remove topic broadcast; redact coordinates from logs by default | **Not mitigated today** |
| Database exposure | Storage bucket policies not actually role-restricted (§16) | public write/overwrite of uploaded assets if ever called with a non-service-role key | Rewrite storage policies to check `auth.role() = 'service_role'` explicitly | **Latent risk, not currently reachable via the shipped frontend, but the policy itself is wrong** |

---

# 31. Implementation Roadmap

## P0 — Critical safety/security (mandatory before any further demo)

```text
RESQ-SAFE-001
Priority: P0
Task: Stop unclassified/unknown emergencies from rendering as "Low"/safe.
Current: emergency_orchestrator.py::determine_emergency_level (else branch → "Low" for unclassified);
         AssessmentResultPanel.tsx LEVEL_STYLES.low → badge "safe"
Change: Introduce an explicit "Unknown" level, distinct from Low. determine_emergency_level's final
        else branch returns "Unknown" when category == "unclassified", never "Low". Add a new
        LEVEL_STYLES.unknown badge (amber/red, never green). Unknown always shows the tel:112 CTA.
Affected component: domain/severity.py (new, extracted per §26), AssessmentResultPanel.tsx
Dependencies: none
DB changes: none
API changes: AssessmentResult.emergency_level may now be "Unknown" — frontend types.ts must add it
Frontend changes: LEVEL_STYLES.unknown, badge class, CTA rendering
Tests required: unit test on determine_emergency_level for category="unclassified"; frontend snapshot
Acceptance:
- Fire, cardiac-arrest, choking, drowning, gas-leak, assault, self-harm probe inputs never render green/safe
- "Unknown" has its own visual treatment, never badge-safe
- Multi-hazard input (until RESQ-SAFE-003 ships) does not silently become "Low"
Risk: low (isolated function + one CSS mapping)
Complexity: S
Mandatory for demo: YES

RESQ-SAFE-002
Priority: P0
Task: Deterministic life-threat safety net, independent of the hazard classifier.
Current: no such layer exists; _TIER1_RULES covers only 7 hazards; historical guard runs before
         everything and can suppress current symptoms (see RESQ-SAFE-004)
Change: Add a Safety Detector (extend triage_service._phrase()/_TIER1_RULES pattern, do not fork it)
        for fire/smoke, not-breathing/difficulty-breathing, unconscious/collapsed, severe-bleeding
        (reuse existing injury phrases), chest-pain/heart-attack, gas-leak, drowning, attack/weapon,
        self-harm (routed to a distinct fixed support message, not the operational protocol).
        Cover native-script + romanized Hindi/Telugu for each new pattern group, matching existing
        coverage depth for the 7 hazards. Detector output can only escalate severity, never lower it.
Affected component: triage_service.py (new SAFETY_NET_RULES dict + _safety_net_check()),
        emergency_orchestrator.py (combine safety-net output with triage severity via max()),
        domain/protocols/unknown_urgent.json (new, §10)
Dependencies: RESQ-SAFE-001 (Unknown level must exist first)
DB changes: none
API changes: AssessmentResult gains safety_net_triggered: bool, matched_pattern: str|null
Frontend changes: surface safety-net trigger explanation in source_labels / result panel
Tests required: one test per lexicon entry per language variant; self-harm routes to support message,
        not the operational plan; safety net does not fire on unrelated text
Acceptance:
- Every reproduced probe failure in §4.2 now escalates to Critical/High with an explicit reason shown
- Self-harm input never returns hospital/action-plan-style content
- No existing passing test regresses
Risk: medium (new lexicon needs native-language review before shipping — do not invent translations
        without a fluent reviewer; flag any unreviewed phrase explicitly in code comments)
Complexity: M
Mandatory for demo: YES

RESQ-SEC-001
Priority: P0
Task: Require authentication on POST /api/sos and POST /api/device-token; stop the global-topic
      SOS broadcast model.
Current: blueprints/sos.py, blueprints/device.py — no auth; firebase_service.send_topic_push
         broadcasts to topic "resq_alerts"; register_device subscribes any token to that topic
Change: Verify the Supabase JWT on these two routes (small Flask decorator using Supabase's JWKS/
        shared secret); reject unauthenticated requests with 401 (new global error handler, §25).
        Replace topic broadcast with dispatch to the requesting user's own
        profiles.emergency_contact_phone (SMS/WhatsApp — pick one provider; do not build both).
        If no emergency contact is on file, tell the user to add one before allowing SOS dispatch,
        and still create the persisted event + show tel:112.
Affected component: app/auth.py (new), blueprints/sos.py, blueprints/device.py,
        services/firebase_service.py or a new services/notify_service.py (SMS provider)
Dependencies: none (independent of RESQ-SAFE-*)
DB changes: sos_events.user_id populated from the verified token (column already exists, unused);
        device_tokens.user_id populated likewise
API changes: 401 responses on both routes without a valid session; SOS response no longer implies
        "sent to responders" — see RESQ-SOS-001 for full state-machine wording changes
Frontend changes: SosConfirmModal must handle a 401 by prompting login, not showing a generic error
Tests required: unauthenticated POST to both routes → 401 (new security test); authenticated flow
        dispatches to the correct contact, not a broadcast topic
Acceptance:
- No client can create an SOS event or register a device token without a valid session
- No SOS notification reaches a device the requesting user did not choose
Risk: medium (requires the Supabase JWT verification plumbing to exist — new infrastructure, but
        small and well-documented for Supabase)
Complexity: M
Mandatory for demo: YES

RESQ-SEC-002
Priority: P0
Task: Content-safety validation on LLM-generated action plans; fix the emergency-contact substring bug.
Current: action_planner_service.py::parse_action_plan_json / _sanitize_emergency_contacts —
         schema-shape validation only; contact filter matches substrings ("1080" passes because it
         contains "108"); reproduced unsafe tourniquet/brandy/fabricated-number plan passed validation
Change: (a) _sanitize_emergency_contacts: match whole numbers with \b...\b against the trusted set,
        not substring containment. (b) Add a content-safety pass: reject output containing any
        digit-run not in the trusted-number set (beyond contacts — scan all text fields); reject
        output containing banned-procedure terms (tourniquet, incision/cut wound, inject, specific
        drug names/doses) unless present verbatim in the matching authored protocol; on rejection,
        use the authored protocol verbatim and log llm.rejected (§23) with the reason.
Affected component: action_planner_service.py, domain/protocols/*.json (§10, needed as the
        comparison baseline for the divergence check)
Dependencies: RESQ-ARCH-001 (protocol extraction) for the cleanest implementation, but the contact
        substring fix and banned-term scan can ship independently and immediately
Tests required: the exact reproduced unsafe-plan probe from §9 must now be rejected and replaced
        with the authored fallback; "Police: 1080" must not pass the contact filter
Acceptance:
- No LLM-authored digit sequence outside the trusted list appears in any user-visible field
- No banned-procedure term appears in LLM output unless verbatim in the source protocol
- Rejection always falls back to the authored protocol, never to a stripped/edited LLM string
Risk: low–medium (banned-term list needs care to avoid false positives that hide legitimate content —
        start conservative, expand test coverage before tightening further)
Complexity: M
Mandatory for demo: YES

RESQ-SEC-003
Priority: P0
Task: Fix Supabase RLS/storage policies that don't actually restrict what they claim to.
Current: schema.sql community_reports insert policy "with check (true)"; schema_vectors.sql storage
         policies named "service role upload/update" but check only bucket_id, not role
Change: community_reports insert policy → "with check (verified = false)" at minimum, or remove
        client-insert capability entirely once all writes go through the authenticated backend (§15).
        storage.objects insert/update policies → add "and auth.role() = 'service_role'" to the check.
Affected component: supabase/schema.sql, supabase/schema_vectors.sql (new migration file, §32)
Dependencies: none
DB changes: policy migration (§32)
Tests required: RLS policy test — anon key cannot set verified=true; anon key cannot write to the
        storage bucket
Acceptance: both gaps closed and covered by an automated policy test, not manual inspection alone
Risk: low
Complexity: S
Mandatory for demo: YES

RESQ-ML-001
Priority: P0
Task: Fix the numpy/pydantic Literal validation break in the ML triage and report classifiers.
Current: app/ml/text_classifier.py::predict returns numpy.str_ labels; app/ml/triage.py and
         app/ml/reports.py construct Pydantic models directly from them; pydantic==2.9.2 rejects
         numpy.str_ for Literal fields — reproduced, ML tier silently disables on every call,
         11/269 tests fail
Change: str(best_label) (and str() on any other numpy scalar crossing into a Pydantic model) in
        Prediction construction (text_classifier.py) and/or at each call site in triage.py/reports.py.
        Pin numpy explicitly in requirements.txt.
Affected component: app/ml/text_classifier.py, app/ml/triage.py, app/ml/reports.py,
        services/traffic_service.py (same bug via TrafficIncident.type), requirements.txt
Dependencies: none
Tests required: existing test_triage_ml_service.py, test_triage_eval_gold.py (multilingual/overall),
        test_traffic.py::test_community_incidents_filtered_by_radius must all pass under the pinned
        requirements after this fix (verified reproducible today)
Acceptance: pip install -r requirements.txt && pytest → 0 failures attributable to this bug
Risk: very low
Complexity: XS
Mandatory for demo: YES (currently the ML tier is dead weight in any fresh install)
```

## P1 — Reliability / core architecture

```text
RESQ-SAFE-003 (Multi-hazard detection & composition, §4.5) — depends on RESQ-SAFE-001/002
RESQ-SAFE-004 (Negation scoping in Tier 1, §4.3) — independent
RESQ-SAFE-005 (Historical-vs-current clause scoping, §4.4) — depends on RESQ-SAFE-002 (safety net
        must not be suppressed by the historical guard)
RESQ-REL-001  (Stop fabricating benign fallback values — weather/hospitals/traffic, §11) — independent,
        touches emergency_orchestrator.py, blueprints/weather.py, blueprints/hospitals.py,
        DashboardLocationPanel.tsx; acceptance: no failed dependency ever renders as "safe"/"none"/"clear"
RESQ-REL-002  (Standard location object end-to-end + NaN/range validation on /api/sos and
        /api/traffic/nearby, §12) — independent
RESQ-REL-003  (Fix hospitals page never sending user location, §13) — trivial, independent, high value
RESQ-SOS-001  (Full SOS state machine: idempotency, ownership, non-RuntimeError persistence handling,
        acknowledge/cancel, §14) — depends on RESQ-SEC-001
RESQ-API-001  (Global JSON error handler; consistent success/error/unavailable envelope, §25) —
        independent, fixes 4 reproduced HTML-error cases immediately
RESQ-PERF-001 (Parallelize weather/hospitals/traffic calls with asyncio.gather; two-phase response, §22)
RESQ-ARCH-001 (Extract domain/protocols/*.json and domain/severity.py; consolidate SOS logic;
        delete dead run_assessment/parse_response/STATIC_FALLBACK_ASSESSMENT, §10/§26)
RESQ-DEPLOY-001 (Production WSGI entrypoint, replace debug=True app.run, §29)
RESQ-ENV-001  (Pin numpy + redis-agent-memory exactly, add .python-version, §28) — pairs with RESQ-ML-001
```

## P2 — Advanced intelligence / ML

```text
RESQ-ML-002 (Rebuild the gold-eval split so no training row overlaps it; report real, held-out
        multilingual accuracy — verified today at ~50% without contamination, §7)
RESQ-ML-003 (Add adversarial/OOD/ASR-noise eval suites, §7)
RESQ-ML-004 (Offline training pipeline + versioned artifacts; never train on first request, §8)
RESQ-TRIAGE-001 (Run Tier 1/2/ML in parallel and combine via agreement rather than strict cascade,
        §6 — a genuine improvement, not required for P0/P1 safety fixes to land)
RESQ-CONF-001 (Replace numeric confidence with evidence-based, relevance-aware reliability chips, §19)
```

## P3 — UX / product polish

```text
RESQ-UX-001 (tel: links throughout; AbortController timeouts; single SOS modal instance; focus
        trapping, §20)
RESQ-UX-002 (Offline queueing for SOS specifically; navigator.onLine handling, §14/§21)
RESQ-UX-003 (Distinct "AI-simplified" vs authoritative content presentation, §9/§20)
RESQ-HOSP-001 (Emergency-capability field, phone numbers where sourceable, staleness display, §13)
RESQ-OBS-001 (Structured logging events, request IDs, real /ready dependency checks, §23)
```

## P4 — Optional future work

```text
RESQ-FUTURE-001 (Real responder/dispatcher channel — only if an actual organizational partner exists;
        do not simulate this for a demo, §14/§38)
RESQ-FUTURE-002 (Calibrated numeric confidence backed by a genuine labeled-outcome dataset, §19)
RESQ-FUTURE-003 (Retention/anonymization tooling once real user volume justifies the engineering cost,
        §24)
```

---

# 32. Database Migration Plan

| # | Table | Change | Type/constraint | Index | RLS policy | Dependency | Rollback |
|---|---|---|---|---|---|---|---|
| M1 | `community_reports` | tighten insert policy | `with check (verified = false)` | — | replaces existing `with check (true)` | RESQ-SEC-003 | drop new policy, restore old (documented risk, not recommended) |
| M2 | `storage.objects` (bucket `resq-assets`) | tighten insert/update policy | add `auth.role() = 'service_role'` | — | replaces existing policies | RESQ-SEC-003 | revert policy definition |
| M3 | `sos_events` | populate `user_id` on write (column exists, unused) | FK already present (`schema_relationships.sql`) | already indexed (`idx_sos_events_user_id`) | add owner-read policy once auth exists | RESQ-SEC-001 | no schema rollback needed, app-only change |
| M4 | `sos_events` | add `idempotency_key text`, `location_source text`, `location_accuracy_m double precision` | `unique (idempotency_key)` where not null | new index on `idempotency_key` | n/a | RESQ-SOS-001 | drop columns |
| M5 | `sos_events` (new table) `sos_event_transitions` | audit trail of every state change | `id uuid pk, sos_event_id uuid fk, state text, created_at timestamptz` | index on `sos_event_id` | deny-all to anon, service-role only | RESQ-SOS-001 | drop table |
| M6 | `emergency_logs` | populate `user_id` on write; add `retention_expires_at timestamptz` | column exists (`user_id`); add `retention_expires_at` | index on `retention_expires_at` for a cleanup job | unchanged (deny-all to anon) | RESQ-REL / §24 | drop new column |
| M7 | `community_reports` | add `moderation_status text not null default 'submitted'` (submitted/processed/verified/rejected/expired) | check constraint on allowed values | index on `moderation_status` | admin-only update policy for this column | RESQ-SAFE (community reports, §17) | drop column, keep legacy `verified` |
| M8 | `device_tokens` | populate `user_id` on write; consider dropping the global-topic subscription call in `register_device` | column exists | already indexed | add owner policy | RESQ-SEC-001 | app-only change |
| M9 | ML artifacts | not a DB change — object storage or CI artifact versioning for `triage_classifier.joblib`/`report_classifier.joblib` | n/a | n/a | n/a | RESQ-ML-004 | keep previous artifact alongside new one |

No destructive migrations are proposed; every change is additive (new columns/tables) or a policy tightening that can be reverted by restoring the previous policy text.

---

# 33. API Migration Plan

| Endpoint | Change | Before | After |
|---|---|---|---|
| `POST /api/sos` | require auth; new fields | `{lat, lon, situation?}`, 200 always | `Authorization: Bearer <jwt>`; body adds `idempotency_key`; response adds `state` (§14 state-machine value) instead of only `notification_status`; 401 without a valid session |
| `POST /api/device-token` | require auth | `{token}`, no auth | `Authorization: Bearer <jwt>` required; `user_id` derived from token, not accepted from body |
| `POST /api/assessment` | additive fields only, no breaking change | `AssessmentResult` as today | adds `emergency_level: "Unknown"` as a valid value; adds `safety_net_triggered`, `matched_pattern`, `detected_hazards: []` (multi-hazard, RESQ-SAFE-003); `weather`/`hospitals` become `null` on failure instead of fabricated defaults (RESQ-REL-001) — frontend must handle `null` |
| `GET /api/hospitals` | requires lat/lon for meaningful results (soft requirement — still works without, but flags `location_not_provided` explicitly) | `[]` on any failure | `{data: [...], service_status: "available"|"unavailable"|"no_results"|"location_not_provided"}` |
| `GET /api/weather/risk` | stop returning 200 with a fabricated baseline | 200 always | 200 with `service_status: "unavailable"` and `data: null`, or 503 (pick one convention project-wide, §25) |
| All routes | global error envelope | inconsistent JSON/HTML | uniform `{error: {code, message}}` on every non-2xx (§25) |
| `GET /api/ml/status` | require admin auth | public | 401/403 without an admin-role session |

---

# 34. UI Migration Plan

| Screen | Current | Target | API changes needed | A11y / mobile |
|---|---|---|---|---|
| Assessment | presets, textarea, voice input, opt-in location checkbox | unchanged interaction model; add timeout/abort handling | none beyond §25 envelope | keep presets (good for stress); ensure preset buttons remain large-tap-target |
| Assessment Result | badge + confidence % + sections | `Unknown` badge state; safety-net explanation banner; reliability chips instead of/alongside %; `tel:` links on every contact; explicit "unavailable" states for weather/hospitals instead of fabricated data | `emergency_level="Unknown"`, `safety_net_triggered`, reliability fields | ensure the call-now CTA is the first focusable, highest-contrast element for Critical/Unknown |
| SOS | modal, GPS-only path, generic error text | GPS-denied still offers `tel:112` and a location-less event; idempotent confirm button; single modal instance app-wide; acknowledge/cancel action once created | auth header, idempotency key, new state field | focus trap on open, restore focus on close |
| Hospitals | never sends location | sends `useUserLocation()` coords; distinguishes "no results near you" from "search failed" | `service_status` field | — |
| Shelters | static list | adds source/last-verified display; distance once real coordinates + user location are combined | source/last_verified fields | — |
| Traffic/context (dashboard panel) | shows reassuring "no incidents" even on total source failure | checks `sources_used.length` before rendering the all-clear message | none (data already present, only the check needs to be added) | — |
| Community Reports | anyone can post; "Checked/Not checked" badge | unchanged submission UX; badge now reflects the real moderation workflow (§17) rather than a client-trusted flag (already true today, since submission never sets `verified: true` client-side, but the badge should also show `moderation_status` transitions like "under review") | `moderation_status` field | — |
| Chat | unguarded LLM call for every message | emergency-intent guard short-circuits to the Get-Help CTA without a network round-trip for the LLM; message/history caps | none additive required for the guard (client-side pre-check using the same lexicon, mirrored server-side as the source of truth) | — |
| Settings | push permission → FCM token | unchanged UX; backend now requires auth for the registration call | 401 handling in the UI (prompt login) | — |

---

# 35. Acceptance Criteria

- No unsupported or unclassified emergency renders with the green "safe" badge style.
- Unknown hazards trigger escalation (≥ High) and always show a direct-call action, independent of network state.
- Negated hazard phrases ("no flooding here") do not produce a high-confidence Tier-1 match for that hazard.
- A current life-threatening symptom in the same input as a historical reference is not suppressed by the historical guard.
- Multi-hazard input produces a composed response reflecting all detected hazards, not a silent `unclassified`.
- No failed external dependency (weather, hospitals, traffic) produces a response indistinguishable from a genuine safe/clear/no-results result.
- Hospital search reflects the requesting user's actual shared location, not a hard-coded city center.
- `/api/sos` and `/api/device-token` reject unauthenticated requests.
- Duplicate/rapid-repeat SOS submissions with the same idempotency key produce one event, not many.
- No client (including a request made directly against Supabase with the anon key) can set `community_reports.verified = true`.
- The LLM cannot set `emergency_level`, invent an emergency contact number, or introduce a banned-procedure instruction into user-visible output; violations are caught and replaced with the authored protocol, verified by a regression test using the exact unsafe payload reproduced in this document.
- ML models are loaded from a pre-trained artifact at startup; no user request triggers training.
- The reported ML evaluation numbers come from a split with zero verified overlap between training and evaluation data.
- Core emergency assessment (safety net + triage + vetted protocol + call-now CTA) functions correctly with Groq, OpenWeather, TomTom, Redis, Supabase, and Firebase all simulated as unavailable simultaneously.

---

# 36. Hackathon Demonstration Plan

Every demo below uses only capabilities that exist in the repository today, plus the P0 fixes in §31 — nothing fabricated.

**Demo A — Normal flooding assessment.** Input: "Water is entering my house and rising fast," with location shared. Shows: Tier-1 rule match, deterministic High/Critical level driven by classification + live weather risk, vetted flood protocol, real hospitals near the shared location (post RESQ-REL-003). *Demonstrates:* deterministic-first pipeline working end-to-end.

**Demo B — Unsupported / unknown hazard.** Input: "There is a gas leak in my kitchen." Shows: Safety Detector fires (post RESQ-SAFE-002), `Unknown`/escalated level with explicit "we couldn't classify this exactly, treating it as urgent" messaging and the `tel:112` CTA immediately visible — contrasted live against the *current* behavior (green "Low") to make the fix's value obvious to a judge.

**Demo C — Multi-hazard emergency.** Input: "Flood water is rising and there was also a car accident with injuries nearby." Shows: both hazards detected, primary hazard (higher severity) drives the main protocol, secondary hazard's warnings merged in (post RESQ-SAFE-003).

**Demo D — LLM unavailable.** Toggle the Groq key off (or simulate). Shows: triage still resolves via rules/embeddings/ML, action plan uses the vetted protocol directly, chat shows the fixed unavailable message — the entire safety-relevant path is untouched by this outage (already true today; worth demonstrating explicitly).

**Demo E — Weather unavailable.** Toggle the OpenWeather key off. Shows (post RESQ-REL-001): the weather card reads "unavailable," not a fabricated 25°C/"safe" reading; overall assessment still completes.

**Demo F — GPS denied.** Deny location in the browser during SOS. Shows (post RESQ-SOS-001/RESQ-UX-001): SOS event is still created (flagged `location_source: none`), and the `tel:112` action is immediately available rather than a dead-end error message.

**Demo G — SOS flow.** Confirm SOS with location granted (post RESQ-SEC-001): event persists, dispatch goes to the user's own registered emergency contact (not a public broadcast), honest "delivery unknown vs delivered" wording is shown rather than "sent to responders."

**Demo H — Prompt injection / unsafe LLM response rejection.** Feed the exact reproduced unsafe snakebite payload (tourniquet/cut/brandy/fabricated number) through a test harness that simulates the LLM response (post RESQ-SEC-002): show the content-safety layer rejecting it and falling back to the authored protocol, with the rejection logged. *This is the single most technically credible demo in the set* — it shows the team found and fixed a real safety bug, not just described a principle.

---

# 37. Judge-Facing Technical Differentiators

- **Deterministic-first safety, verifiably enforced, not just claimed** — severity and emergency numbers are computed by code, and (post §31) LLM output that violates that boundary is caught by an automated content-safety check with a reproducible test case, not merely a system-prompt instruction.
- **Graceful degradation that is actually honest** — dependency failures surface as "unavailable," never as a fabricated safe/clear default (post §11); demonstrable live by toggling API keys off.
- **Evidence-based trust instead of decorative confidence percentages** — the reliability model (post §19) is relevance-aware (weather doesn't penalize a snakebite result) and legible ("hazard: rule match; weather: not relevant; protocol: verified authored") rather than an unexplained number.
- **Multi-hazard and unknown-hazard handling** — most hackathon emergency-assessment demos only show the happy path; this one can show the *unhappy* path (unknown, multi-hazard, all-dependencies-down) working safely, which is the harder and more convincing engineering story.
- **Multilingual support with an honest accuracy story** — reporting the real, contamination-controlled multilingual number (§7) rather than an inflated one is itself a differentiator to a technically literate judge, who will likely ask about train/test overlap if the project claims high accuracy.
- **SOS that notifies a real, user-chosen recipient** rather than an unauthenticated public broadcast — a concrete, demonstrable security fix with clear before/after framing.
- **Privacy-aware location handling** — a real location object with source/accuracy, never silently substituting a city center for the user's actual position.

---

# 38. What NOT to Build

- **Autonomous responder agents or an "agent swarm."** Nothing in this system should be framed as making decisions or dispatching real responders on its own; the entire architectural principle here is the opposite. Adding agent-to-agent orchestration language would actively undercut the project's own stated principle and add unauditable complexity.
- **Predictive flood/disaster forecasting.** The current risk score is explicitly a rainfall-only heuristic (`weather_service.py` docstring already says so); building or claiming a predictive model without real validated training data would be a credibility risk, not an improvement, and is exactly the kind of overclaim §35 of the original audit warns against repeating.
- **Nationwide deployment or coverage claims.** The hospital/shelter data is Hyderabad-specific; claiming broader coverage without the underlying data would be false.
- **IoT sensor integration claims.** Nothing in the repository reads from or claims to read from physical sensors; do not add this framing without actual hardware.
- **Government/CAD dispatch integration claims.** No such integration exists or is proposed here (§14 explicitly rules this out); claiming otherwise in a demo would be dishonest.
- **A second LLM provider or multi-model ensemble for classification.** The current single-provider Groq integration, once the content-safety and vetted-protocol-first fixes land, is sufficient; adding a second model increases cost/latency/complexity without addressing any finding in this document.
- **Excessive Redis/agent-memory complexity.** Redis Agent Memory is used only for chat session recall today and is explicitly non-critical (§21); do not expand its role into anything safety-relevant.
- **Unnecessary microservices.** The Flask monolith with clear service boundaries (§26) is appropriate at this scale; splitting into separate deployable services would add operational overhead (service discovery, network failure modes) without a corresponding safety or scalability need at current usage levels.
- **A general-purpose plugin/extension system for third-party hazard protocols.** Attractive-sounding but unnecessary complexity for a system whose current, correct instinct is a small, reviewed, first-party protocol set (§10).

Each of the above would look impressive in a pitch but would either contradict the project's own safety principle, add unaudited surface area, or make claims the repository cannot back up — all worse outcomes for a "serious hackathon evaluation" than a smaller, verifiably correct system.

---

# 39. Final Target Architecture

```text
Frontend (Next.js, existing)
   ↓
Authentication (Supabase JWT verified server-side — NEW)
   ↓
API Gateway (Flask blueprints — existing, + global error envelope §25, rate limiting §15)
   ↓
Emergency Orchestrator (existing, extended)
   ↓
Safety Engine (NEW: Safety Detector §4.2 + Severity Engine §5, pure functions, extracted per §26)
   ↓
Triage (existing cascade, patched for negation/historical/multi-hazard §4.3–4.5, parallelized §6)
   ↓
Severity (deterministic, existing logic extended — §4.1)
   ↓
Vetted Protocol (NEW first-class repository, §10; content migrated from existing _FALLBACK_PLANS)
   ↓
Context Services (weather / hospitals / traffic / community — parallelized §22, honest states §11)
   ↓
Optional LLM Enrichment (rephrase/translate/clarify only, content-safety-gated §9)
   ↓
Response (explicit service_status, reliability chips §19, tel: actions, Unknown-safe UI §20)
```

```text
Supporting subsystems:
SOS            — authenticated, idempotent state machine, real recipient dispatch (§14)
Database       — Supabase as system of record; Firebase FCM-only (§26); RLS tightened (§16)
Notifications  — SMS/push to a verified user-chosen contact, not a public topic (§14)
Observability  — structured events, request IDs, real readiness checks (§23)
ML pipeline    — offline-trained, versioned artifacts, honest held-out evaluation (§7–8)
Knowledge/RAG  — pgvector + fastembed, gated behind auth/moderation for uploads (§17)
External APIs  — Groq, OpenWeather, Overpass/TomTom, Supabase, Firebase — each with an explicit
                 available/unavailable/not_relevant state surfaced to the user, never fabricated (§11)
```

---

# 40. Final Engineering Verdict

**Current state.** ResQ AI already gets the hardest architectural call right: an LLM that assists but does not decide severity, wrapped in a schema-validated, gracefully-degrading orchestrator, with SOS that persists before it notifies. That is a genuinely more mature starting point than most hackathon emergency-response prototypes reach. The engineering discipline visible in `emergency_orchestrator.py`'s comments and `action_planner_service.py`'s structure suggests the team already understands the right principles — the gaps found here are mostly places where an otherwise-sound design's edge cases (the fall-through default, the substring contact filter, the unauthenticated write paths, the contaminated eval set) weren't yet closed, not places where the design itself is wrong.

**Critical weaknesses that must be fixed before a serious demo.** In order of what a careful evaluator or a real incident would find first: (1) unknown and multi-hazard inputs rendering as safe/green, (2) no deterministic backstop for common life-threats outside the seven modeled hazards, (3) a completely unauthenticated backend, with SOS specifically broadcasting to an unauthenticated public topic rather than a real recipient, (4) an LLM-generated action plan that can and (reproduced) does pass validation while containing dangerous first-aid content, and (5) a reported "100% accuracy" ML evaluation number that is substantially the model recalling its own training data.

**Target state after remediation.** The same architecture, with an authoritative safety layer that runs independently of and before the hazard classifier, authentication and rate limiting on every write/SOS/device-registration path, a content-safety gate between the LLM and the user for anything safety-relevant, honest dependency-failure states everywhere, and ML numbers that mean what they claim to mean.

**Minimum viable serious-hackathon version.** The six P0 tasks in §31 (`RESQ-SAFE-001/002`, `RESQ-SEC-001/002/003`, `RESQ-ML-001`) — none of them require new infrastructure beyond a JWT-verification decorator and an SMS/WhatsApp provider integration for real SOS recipients, and all six are demonstrable live, with a clear before/after story, per §36.

**Advanced version, if time allows.** Parallelized context enrichment for latency (§22), the full SOS state machine with acknowledge/cancel (§14), a genuinely held-out and adversarial ML evaluation (§7), and evidence-based reliability chips replacing the numeric confidence display (§19).

**Do not build.** Anything in §38 — none of it is required to make this project safe, secure, or credible, and all of it risks making an honest, well-scoped prototype look like it's overclaiming.

