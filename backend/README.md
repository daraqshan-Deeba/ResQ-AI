# ResQ AI — Backend (Flask)

Flask API powered by the Emergency Orchestrator pipeline. All business logic lives in `app/services/`; HTTP routes are Flask blueprints under `app/blueprints/`.

## Endpoints

- **Emergency Assessment** — `POST /api/assessment`
- **Weather / Risk** — `GET /api/weather`, `GET /api/weather/risk`
- **Hospitals / Shelters** — `GET /api/hospitals`, `GET /api/shelters`
- **SOS** — `POST /api/sos`
- **Community** — `GET|POST /api/reports`, `POST /api/device-token`, `POST /api/chat`
- **Health** — `GET /health`

## Setup

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # creates backend/.env — never commit this file
```

Fill in API keys in `backend/.env`. See `.env.example` for Firebase, Groq, OpenWeather, and Supabase.  
Frontend public vars go in `frontend/.env.local` — see `docs/security-secrets.md`.

```bash
python scripts/apply_supabase_schema.py   # create Supabase tables (once)
python scripts/seed_database.py         # shelters, reports, knowledge assets
python scripts/fetch_hospitals_overpass.py  # hospitals → Firebase
python run.py                           # http://127.0.0.1:8001
```

Data sources and download links: `data/DATA_SOURCES.md`  
Raw KML/metadata: `data/sources/` (gitignored when large)

## CORS (Next.js frontend)

Set `CORS_ORIGINS` in `.env` to include your Next.js dev server:

```
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

## Running with the frontend

1. Start backend: `python run.py`
2. Start frontend: `cd ../frontend && npm run dev`
3. Open http://localhost:3000

Or from the repo root: `./start.sh` (bash).

## Tests

```bash
pytest
```
