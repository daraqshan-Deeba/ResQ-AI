# Security & secrets hygiene

Last audited: 2026-09-11

## Summary

| Check | Status |
|-------|--------|
| API keys hardcoded in source | **Pass** — all keys load from env |
| `.env` / `.env.local` in git | **Pass** — gitignored, never committed |
| Firebase private key in repo | **Pass** — env var only |
| Supabase service role exposed to frontend | **Pass** — backend-only |
| ML status endpoint leaks keys | **Pass** — returns model metadata only |

Run a local scan anytime:

```powershell
cd backend
python scripts/scan_secrets.py
```

## Where secrets belong

| File | Purpose |
|------|---------|
| `backend/.env` | **Server secrets** — Groq, OpenWeather, Supabase service role, Firebase admin key, Postgres |
| `frontend/.env.local` | **Public client config** — `NEXT_PUBLIC_*` only (Supabase anon key, API URL, Firebase web config) |

Do **not** put `SUPABASE_SERVICE_ROLE_KEY`, `FIREBASE_PRIVATE_KEY`, `GROQ_API_KEY`, or `POSTGRES_PASSWORD` in the frontend env.

If you still have a root-level `.env` from an older setup, migrate values into `backend/.env` and delete the root copy.

## Never commit

- `backend/.env`, `frontend/.env.local`
- `firebase-service-account.json`, `client_secret*.json`
- `backend/data/models/*.joblib` (regenerate with `python scripts/train_models.py`)
- Large KML/zips under `backend/data/sources/` and `backend/data/downloads/`

## If a key was exposed

1. **Rotate immediately** in the provider console (Groq, Supabase, Firebase, OpenWeather).
2. Revoke old Supabase service role / JWT secret if `SUPABASE_JWT_SECRET` leaked.
3. Run `python scripts/scan_secrets.py` and `git log --all -- .env` to confirm nothing was pushed.

## API surface

- Backend uses **Supabase service role** only server-side (`supabase_service.py`).
- Frontend uses **Supabase anon key** with RLS — safe to expose as `NEXT_PUBLIC_*`.
- Firebase web `apiKey` is a public client identifier; restrict by domain in Firebase Console.
