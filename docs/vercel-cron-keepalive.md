# Vercel Cron + anti cold-start keep-alive

ResQ AI keeps **Supabase**, the **Flask backend**, and the **Vercel frontend** warm so visitors hit fewer cold starts.

## Why GitHub Actions (not only Vercel Cron)

| Plan | Minimum cron interval | Enough to avoid cold starts? |
|------|----------------------|------------------------------|
| **Hobby (free)** | **Once per day** | No — functions go cold in minutes |
| Pro / Enterprise | Once per minute | Yes, if you schedule often |

This repo ships:

1. **Vercel Cron** — `0 4 * * *` (once daily; Hobby-safe fallback)
2. **GitHub Actions** — every **5 minutes** → primary anti cold-start pinger

## What gets pinged

| Target | How | Action |
|--------|-----|--------|
| **Vercel `/api/health`** | GitHub Actions | Lightweight warm (no auth) |
| **Vercel `/`** | GitHub Actions + cron job | Warm the home page function |
| **Vercel `/api/cron/keepalive`** | GitHub Actions + Vercel Cron | Full chain |
| **Supabase Postgres** | Keepalive function | `SELECT` count on `shelters` |
| **Flask backend** | Keepalive → `NEXT_PUBLIC_API_URL` | `/api/cron/keepalive` (Redis, Firebase, cache warm) |

## Setup

### 1. Vercel env (frontend project, root = `frontend`)

| Variable | Notes |
|----------|-------|
| `CRON_SECRET` | Random 32+ char string (Vercel Cron sends `Authorization: Bearer …`) |
| `NEXT_PUBLIC_APP_URL` | Production URL, e.g. `https://your-app.vercel.app` |
| `NEXT_PUBLIC_API_URL` | Public URL of your Flask backend |
| `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Same as local |
| `SUPABASE_SERVICE_ROLE_KEY` | Optional; better DB wake ping |
| `KEEPALIVE_SECRET` | Same as `CRON_SECRET` is fine |

### 2. Flask backend env

```
CRON_SECRET=<same as Vercel>
KEEPALIVE_SECRET=<same as Vercel>
```

### 3. GitHub repository secrets (Settings → Secrets and variables → Actions)

| Secret | Example |
|--------|---------|
| `KEEPALIVE_APP_URL` | `https://your-app.vercel.app` |
| `CRON_SECRET` | Same value as Vercel `CRON_SECRET` |

Workflow file: [`.github/workflows/keepalive.yml`](../.github/workflows/keepalive.yml)

After pushing, open **Actions → Keepalive (anti cold-start)** and run **workflow_dispatch** once to verify.

### 4. Redeploy frontend

Cron appears under **Project → Settings → Cron Jobs**. Hobby stays at once/day; Actions handle the frequent pings.

## Local test

```powershell
# Backend
cd backend
python run.py

# Frontend
cd frontend
$env:CRON_SECRET="test-secret-local"
$env:KEEPALIVE_SECRET="test-secret-local"
$env:NEXT_PUBLIC_APP_URL="http://127.0.0.1:3000"
npm run dev

# Warm + full chain
curl http://127.0.0.1:3000/api/health
curl -H "Authorization: Bearer test-secret-local" http://127.0.0.1:3000/api/cron/keepalive
```

## Response shape (`/api/cron/keepalive`)

```json
{
  "status": "ok",
  "triggered_at": "2026-09-23T04:12:00.000Z",
  "schedule": "0 4 * * *",
  "checks": {
    "frontend": { "ok": true, "configured": true, "routes": { "/api/health": 40, "/": 120 } },
    "supabase": { "ok": true, "configured": true, "latency_ms": 120 },
    "backend": { "ok": true, "configured": true, "latency_ms": 85 }
  }
}
```

- `200` = all configured checks healthy  
- `207` = degraded (app still warmed)  
- `500` = nothing configured  

## Security

- `/api/health` is public and returns no secrets (warm only).
- `/api/cron/keepalive` requires `Authorization: Bearer <CRON_SECRET>`.
- Never expose `CRON_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, or `KEEPALIVE_SECRET` as `NEXT_PUBLIC_*`.
- Vercel Cron does not follow redirects — keep the cron path returning `200`/`207` directly.
