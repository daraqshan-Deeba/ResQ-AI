"use client";

import { useState } from "react";
import { apiCall } from "@/lib/api";
import { isFirebaseWebConfigured, requestFcmToken } from "@/lib/firebase";

export default function SettingsPage() {
  const [status, setStatus] = useState("");

  async function enableAlerts() {
    if (!("Notification" in window)) {
      setStatus("Push notifications aren't supported in this browser.");
      return;
    }

    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      setStatus("Notifications were not allowed.");
      return;
    }

    if (!isFirebaseWebConfigured()) {
      setStatus(
        "Browser permission granted. Add Firebase web config (API key, sender ID, app ID, VAPID) to frontend/.env.local to register with the backend.",
      );
      return;
    }

    try {
      const token = await requestFcmToken();
      if (!token) {
        setStatus("Could not obtain an FCM device token. Check VAPID key and Firebase web app config.");
        return;
      }

      const res = await apiCall<{ status: string }>("/api/device-token", {
        method: "POST",
        body: JSON.stringify({ token }),
      });

      setStatus(
        res.ok
          ? "Push alerts enabled. This device is subscribed to SOS notifications."
          : `Registered locally but backend error: ${res.error}`,
      );
    } catch {
      setStatus("Failed to register for push notifications.");
    }
  }

  return (
    <div className="mx-auto max-w-md text-center">
      <div className="glass-card p-8">
        <div className="text-4xl">⚙️</div>
        <h1 className="mt-4 text-2xl font-semibold">Settings</h1>
        <p className="mt-3 text-sm text-slate-400">
          Enable push alerts to receive SOS and emergency notifications via Firebase
          Cloud Messaging.
        </p>
        <button className="btn btn-primary mt-6" onClick={enableAlerts}>
          🔔 Enable Push Alerts
        </button>
        {status && <p className="mt-4 text-sm text-slate-300">{status}</p>}
        <p className="mt-6 text-xs text-slate-500">
          API backend: {process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}
        </p>
      </div>
    </div>
  );
}
