# ResQ AI — Backend

FastAPI backend for the three agents:

- **Responder** (`/api/assessment`, `/api/chat`) — Grok (xAI) API.
- **Sentinel** (`/api/weather`, `/api/weather/risk`) — OpenWeatherMap, turned
  into the dashboard's risk score.
- **Wayfinder** (`/api/hospitals`, `/api/shelters`) — Google Places for real
  hospitals; Firestore for shelters, since no public API publishes live
  shelter/bed occupancy.

Also included: `/api/reports` (community reports), `/api/device-token`
(register a browser for push alerts), and `/api/sos` (sends a free push
notification via Firebase Cloud Messaging to every registered device).

**Database + notifications are both Firebase** — Firestore is the database,
Cloud Messaging (FCM) sends the SOS/alert pushes. One project, one setup,
no separate Postgres server to run, and no per-SMS cost.

## Step 1 — Firebase project (database + push, ~5 minutes)

1. Go to https://console.firebase.google.com → **Add project** → give it any
   name (e.g. `resq-ai`) → you can skip Google Analytics.
2. In the left sidebar: **Build → Firestore Database → Create database** →
   pick a region close to you → start in **test mode** (fine for a hackathon;
   tighten the rules before any real deployment).
3. In the left sidebar: **Build → Cloud Messaging** → it's enabled by default,
   nothing else to do here yet.
4. Click the ⚙️ gear (top left) → **Project settings → Service accounts** tab
   → **Generate new private key**. This downloads a JSON file.
5. Rename that file to `firebase-service-account.json` and put it in this
   `resq-backend` folder (same level as `requirements.txt`). **Never commit
   this file** — it's already listed in `.gitignore`.
6. Still in Project settings, go to the **General** tab → scroll to
   "Your apps" → click the **Web** icon (`</>`) → register an app (any
   nickname) → you'll get a `firebaseConfig` object. Copy it — the frontend
   needs it (see the frontend README).
7. One tab over: **Project settings → Cloud Messaging** → scroll to
   **Web configuration → Web Push certificates → Generate key pair**. Copy
   the key shown — the frontend needs this too (it's the "VAPID key").

## Step 2 — Grok (xAI) API key

Go to https://console.x.ai, create a key. It should look like `xai-...` —
if the key you're using starts with something else (e.g. `AQ...`), it's from
the wrong service and won't authenticate.

## Step 3 — the rest of the keys

- `OPENWEATHER_API_KEY` → https://openweathermap.org/api (free tier)
- `GOOGLE_MAPS_API_KEY` → https://console.cloud.google.com — enable
  **Places API (New)** and **Directions API** on the project, then create a
  key under APIs & Services → Credentials.

## Step 4 — install and configure

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` and fill in `GROK_API_KEY`, `OPENWEATHER_API_KEY`,
`GOOGLE_MAPS_API_KEY`. Leave `FIREBASE_CREDENTIALS_PATH` as-is if you named
the file exactly `firebase-service-account.json`.

## Step 5 — seed sample data and run

```bash
python seed_shelters.py     # optional: puts 3 example shelters in Firestore
uvicorn app.main:app --reload --port 8000
```

Check http://localhost:8000/docs for interactive API docs — every endpoint
can be tested from there before you touch the frontend at all.

## What's wired on the frontend side

`script.js` calls these for real:

- Chat widget → `POST /api/chat`
- "Get Help Now" → `POST /api/assessment`
- Dashboard risk gauge / weather → `GET /api/weather/risk`, `GET /api/weather`
- Hospitals page → `GET /api/hospitals`
- Shelters page → `GET /api/shelters`
- Community Reports page → `GET`/`POST /api/reports`
- Settings page "Enable Push Alerts" button → registers this browser for
  push via `POST /api/device-token`
- SOS page → `POST /api/sos`, which pushes a notification to every
  registered device (see the frontend README for the Firebase JS setup this
  needs)

Every call goes through the `apiCall()` helper in `script.js`, which never
throws — if the backend is down or misconfigured, the UI shows a `⚠️`
message inline instead of breaking.

## Running frontend + backend together

1. Start this backend: `uvicorn app.main:app --reload --port 8000`
2. Serve the frontend folder with a real local server rather than opening
   `index.html` directly (push notifications specifically need this — a
   service worker won't register from a `file://` URL):
   - VS Code: right-click `index.html` → "Open with Live Server"
   - or: `python -m http.server 5500` from inside the frontend folder
3. Open the dashboard → Settings → "Enable Push Alerts" → allow notifications
   when the browser prompts. This registers your device.
4. Go to the SOS page and confirm — you should see a real push notification
   appear (even if the tab isn't focused), sent through Firebase.
5. Submit an emergency assessment — if `GROK_API_KEY` is valid, you'll get a
   real Grok-generated response instead of the "Couldn't reach Responder"
   fallback message.

If you see `⚠️ Could not reach the backend`, it's almost always: uvicorn
isn't running, the port doesn't match `API_BASE` in `script.js`, or your
frontend's origin isn't in `CORS_ORIGINS`.

## Notes on data honesty

- **Hospital bed counts and shelter occupancy are not available from any
  public API.** The hospital list is real (via Google Places); the shelter
  list and occupancy numbers live in Firestore and are whatever you (or an
  admin) put there — keep it manually maintained, or clearly mark it as demo
  data until you have a real feed.
- **The risk score is a heuristic**, not an official flood model — it
  combines real rainfall data with a fixed placeholder for drainage capacity.
  Good enough to demo the concept; say so if anyone asks how it's calculated.
- **Grok responses aren't grounded in live web search by default** in this
  setup (see the comment in `grok_service.py`) — the NEARBY HELP section
  comes from the model's training data, so treat those specific names/links
  as a starting point to verify, not a live lookup.
