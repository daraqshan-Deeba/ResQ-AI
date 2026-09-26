# Google login & registration setup

ResQ AI uses **Supabase Auth** with Google OAuth. Your Google client JSON redirect URI already points at Supabase.

## 1. Supabase dashboard

1. **Authentication → URL configuration**
   - Site URL: `http://localhost:3000`
   - Redirect URLs: `http://localhost:3000/auth/callback`

2. **Authentication → Providers → Google**
   - Enable Google
   - Client ID: `653926784871-i9hrtiarj35tnkrva7aik9d4mh9n5ijj.apps.googleusercontent.com`
   - Client Secret: from `client_secret_*.json` (`web.client_secret`) — **Supabase dashboard only**
   - Do **not** put the client secret in the Next.js app.

   Optional: `python backend/scripts/apply_google_oauth.py` with `SUPABASE_ACCESS_TOKEN` set (Dashboard → Account → Access Tokens).

3. **Database**
   - Run `backend/supabase/schema_auth.sql` (or `python backend/scripts/apply_supabase_schema.py`)

## 2. Google Cloud Console

In [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → OAuth client in project **mufasaai**:

- **Authorized redirect URIs** (already set on this client):
  - `https://tsmjwldlsbywslixcezl.supabase.co/auth/v1/callback`
- **Authorized JavaScript origins** (the OAuth client screenshot had none — add these):
  - `http://localhost:3000`
  - `http://127.0.0.1:3000`
  - `https://res-q-ai-one.vercel.app`
  - `https://tsmjwldlsbywslixcezl.supabase.co`

## 3. Frontend environment

`frontend/.env.local` (local) and **Vercel → Settings → Environment Variables** (production). `NEXT_PUBLIC_*` is baked in at **build** time — add the vars, then **Redeploy**.

```env
NEXT_PUBLIC_SUPABASE_URL=https://tsmjwldlsbywslixcezl.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<same anon key as local>
```

Without those two on Vercel, the login page shows: “Sign in is not available right now.”

Also add **Authentication → URL configuration → Redirect URLs**:

- `http://localhost:3000/auth/callback`
- `https://res-q-ai-one.vercel.app/auth/callback`

Site URL can be `https://res-q-ai-one.vercel.app` (keep localhost in Redirect URLs for local).

## 4. User flow

1. `/login` → Continue with Google
2. Google → Supabase → `/auth/callback`
3. New user → `/register` (pre-filled from Google, editable)
4. Complete registration → `/dashboard`
5. Returning user → `/dashboard` directly

## 5. Profile fields collected

| Field | Source | Editable before register |
|-------|--------|--------------------------|
| Email | Google | Read-only |
| Full name | Google | Yes |
| Display name | Google | Yes |
| Avatar | Google | Shown (from Google URL) |
| Phone | User | Yes — country code selector + national digits, stored as E.164 (`+919876543210`) |
| City / area | User | Yes (required) |
| Emergency contact | User | Yes (optional) |
