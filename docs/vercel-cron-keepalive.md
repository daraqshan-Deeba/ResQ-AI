# Vercel Cron — keep-alive pings

ResQ AI uses a Vercel Cron job to ping Supabase and the Flask backend so free-tier services do not go idle.

## Vercel plan limits (important)

| Plan | Minimum cron interval | Timing precision |
|------|----------------------|------------------|
| **Hobby (free)** | **Once per day only** | Any time within the scheduled hour (±59 min) |
| Pro / Enterprise | Once per minute | Within the scheduled minute |

This project ships with **`0 4 * * *`** (once daily at ~04:00 UTC). Expressions like `*/6 * * * *` or `0 */4 * * *` **fail deployment on Hobby**.

If you need pings more than once per day on Hobby, use an external scheduler (GitHub Actions, [cron-job.org](https://cron-job.org)) to `GET` your deployed URL:

```http
GET https://your-app.vercel.app/api/cron/keepalive
Authorization: Bearer <CRON_SECRET>
```

## What gets pinged

| Target | From | Action |
|--------|------|--------|
| **Supabase Postgres** | Vercel function | `SELECT` count on `shelters` |
| **Flask backend** | Vercel function → your API host | `/api/cron/keepalive` |
| **Redis agent memory** | Flask backend cron route | lightweight memory search |
| **Firebase admin** | Flask backend cron route | availability check |

## Setup on Vercel

1. Deploy the **frontend** project (root directory: `frontend`).

2. Add **Environment Variables** (Production):

   | Variable | Where | Notes |
   |----------|-------|-------|
   | `CRON_SECRET` | Vercel only | Random 32+ char string; Vercel sends this automatically |
   | `NEXT_PUBLIC_API_URL` | Vercel | Public URL of your Flask backend |
   | `NEXT_PUBLIC_SUPABASE_URL` | Vercel | Same as local |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Vercel | Same as local |
   | `SUPABASE_SERVICE_ROLE_KEY` | Vercel only | Optional but recommended for DB wake ping |
   | `KEEPALIVE_SECRET` | Vercel + backend | Same value as `CRON_SECRET` is fine |

3. On your **Flask backend** host, set:

   ```
   CRON_SECRET=<same as Vercel>
   KEEPALIVE_SECRET=<same as Vercel>   # optional alias
   ```

4. Redeploy. Cron appears under **Project → Settings → Cron Jobs**.

## Local test

```powershell
# Terminal 1 — backend
cd backend
python run.py

# Terminal 2 — frontend
cd frontend
$env:CRON_SECRET="test-secret-local"
$env:KEEPALIVE_SECRET="test-secret-local"
npm run dev

# Terminal 3 — simulate Vercel cron
curl -H "Authorization: Bearer test-secret-local" http://127.0.0.1:3000/api/cron/keepalive
```

## Response shape

```json
{
  "status": "ok",
  "triggered_at": "2026-09-23T04:12:00.000Z",
  "schedule": "0 4 * * *",
  "checks": {
    "supabase": { "ok": true, "configured": true, "latency_ms": 120 },
    "backend": { "ok": true, "configured": true, "latency_ms": 85 }
  }
}
```

`207` = degraded (some configured services failed). `500` = nothing configured.

## Security

- Endpoints require `Authorization: Bearer <CRON_SECRET>`.
- Never expose `CRON_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, or `KEEPALIVE_SECRET` as `NEXT_PUBLIC_*`.
- Vercel does not follow redirects for cron invocations — ensure the route returns `200` directly.
