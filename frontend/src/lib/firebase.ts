import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import { getMessaging, getToken, isSupported, type Messaging } from "firebase/messaging";

function firebaseConfig() {
  return {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
    messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  };
}

export function isFirebaseWebConfigured(): boolean {
  const cfg = firebaseConfig();
  return Boolean(cfg.apiKey && cfg.projectId && cfg.messagingSenderId && cfg.appId);
}

export function getFirebaseApp(): FirebaseApp | null {
  if (!isFirebaseWebConfigured()) return null;
  if (getApps().length) return getApps()[0];
  return initializeApp(firebaseConfig());
}

export async function getFirebaseMessaging(): Promise<Messaging | null> {
  if (!(await isSupported())) return null;
  const app = getFirebaseApp();
  if (!app) return null;
  return getMessaging(app);
}

export async function requestFcmToken(): Promise<string | null> {
  const messaging = await getFirebaseMessaging();
  const vapidKey = process.env.NEXT_PUBLIC_FCM_VAPID_KEY;
  if (!messaging || !vapidKey) return null;

  let registration: ServiceWorkerRegistration | undefined;
  if ("serviceWorker" in navigator) {
    registration = await navigator.serviceWorker.register("/firebase-messaging-sw.js");
    const cfg = firebaseConfig();
    registration.active?.postMessage({ type: "FIREBASE_CONFIG", config: cfg });
  }

  return getToken(messaging, { vapidKey, serviceWorkerRegistration: registration });
}
