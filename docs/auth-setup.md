# Google login & registration setup

ResQ AI uses **Supabase Auth** with Google OAuth. Your Google client JSON redirect URI already points at Supabase.

## 1. Supabase dashboard

1. **Authentication → URL configuration**
   - Site URL: `http://localhost:3000`
   - Redirect URLs: `http://localhost:3000/auth/callback`

2. **Authentication → Providers → Google**
   - Enable Google
   - Client ID: from your Google OAuth JSON (`client_id`)
   - Client Secret: from your Google OAuth JSON (`client_secret`)
   - Do **not** put the client secret in the Next.js app — only in Supabase.

3. **Database**
   - Run `backend/supabase/schema_auth.sql` (or `python backend/scripts/apply_supabase_schema.py`)

## 2. Google Cloud Console

In [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → your OAuth client:

- **Authorized redirect URIs** (already set):
  - `https://tsmjwldlsbywslixcezl.supabase.co/auth/v1/callback`
- **Authorized JavaScript origins** (add for local dev):
  - `http://localhost:3000`

## 3. Frontend environment

`frontend/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```

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
