# ResQ AI — Frontend (simple HTML/CSS/JS)

No build tools, no framework — open `index.html` to see the landing page,
`dashboard.html` for the app (Assessment, Assistant, Hospitals, Shelters,
Reports, SOS, Settings).

## Connecting to the backend

`script.js` calls the FastAPI backend at whatever `API_BASE` is set to (top
of the file, defaults to `http://localhost:8000`). See `../resq-backend/README.md`
to get that running first.

## Push notifications (Firebase Cloud Messaging)

The SOS button and the Settings page's "Enable Push Alerts" button both need
a bit of one-time setup, because unlike the backend calls, push notifications
require a small amount of *public* Firebase config to live in the frontend
too:

1. Finish the backend's Firebase setup first (README there) — same project.
2. Open `firebase-config.js` in this folder and fill in the `firebaseConfig`
   object and `FCM_VAPID_KEY` using the values from:
   **Firebase Console → Project settings → General → "Your apps" → Web app**
   (the config object), and
   **Firebase Console → Project settings → Cloud Messaging → Web Push
   certificates** (the VAPID key).
   These values are meant to be public — this is not the same as the
   backend's private service-account JSON, don't worry about exposing them.
3. Serve this folder with a real local server — **not** by double-clicking
   `index.html`. Push notifications need a service worker, and browsers only
   register service workers over `http(s)://` or `localhost`, not `file://`.
   Easiest options:
   - VS Code: right-click `index.html` → "Open with Live Server"
   - or: `python -m http.server 5500` from inside this folder, then visit
     `http://localhost:5500`
4. On the dashboard, go to **Settings → Enable Push Alerts**, and allow
   notifications when your browser prompts. This registers your browser with
   the backend (`POST /api/device-token`) and subscribes it to the alert
   topic.
5. Go to the **SOS** page and confirm. You should see a real notification
   pop up (Firebase handles delivery even to a backgrounded tab, via
   `firebase-messaging-sw.js`).

If nothing shows up: check the browser console for errors first — the two
most common issues are `firebase-config.js` still having placeholder values,
or the page being opened as `file://` instead of served locally.
