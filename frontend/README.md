# ResQ AI — Next.js Frontend

Next.js (App Router) frontend for ResQ AI. It talks to the **Flask** backend via REST.

## Setup

```bash
cp .env.local.example .env.local
npm install
```

Set `NEXT_PUBLIC_API_URL` to your Flask server (default `http://127.0.0.1:8000`).

## Run (dev)

```bash
npm run dev
```

Open http://localhost:3000

## Pages

| Route | Purpose |
|-------|---------|
| `/` | Landing page |
| `/dashboard` | Overview — weather, risk score, quick actions |
| `/dashboard/assessment` | Emergency assessment (`POST /api/assessment`) |
| `/dashboard/assistant` | AI chat (`POST /api/chat`) |
| `/dashboard/hospitals` | Nearby hospitals |
| `/dashboard/shelters` | Shelter capacity |
| `/dashboard/reports` | Community reports |
| `/dashboard/sos` | SOS location capture |
| `/dashboard/settings` | Push notification setup |

## Backend connection

All API calls go through `src/lib/api.ts`, which reads `NEXT_PUBLIC_API_URL`.
The Flask backend must allow your origin in `CORS_ORIGINS` (default includes `http://localhost:3000`).
