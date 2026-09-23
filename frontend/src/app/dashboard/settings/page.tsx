"use client";

import { useState } from "react";
import { apiCall } from "@/lib/api";
import { isFirebaseWebConfigured, requestFcmToken } from "@/lib/firebase";

export default function SettingsPage() {
  const [status, setStatus] = useState("");

  async function enableAlerts() {
    if (!("Notification" in window)) {
      setStatus("This browser does not support alerts.");
      return;
    }

    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      setStatus(
        "Notifications were not allowed. You can turn them on later in your browser settings.",
      );
      return;
    }

    if (!isFirebaseWebConfigured()) {
      setStatus(
        "Permission was granted, but alerts are not fully set up on this device yet. Please try again later.",
      );
      return;
    }

    try {
      const token = await requestFcmToken();
      if (!token) {
        setStatus("Could not finish setting up alerts. Please try again.");
        return;
      }

      const res = await apiCall<{ status: string }>("/api/device-token", {
        method: "POST",
        body: JSON.stringify({ token }),
      });

      setStatus(
        res.ok
          ? "Alerts are on. This device can receive SOS and emergency updates."
          : "Could not save your alert settings. Please try again in a moment.",
      );
    } catch {
      setStatus("Something went wrong while enabling alerts. Please try again.");
    }
  }

  return (
    <div className="mx-auto max-w-md text-center">
      <div className="glass-card p-8">
        <div className="text-4xl">⚙️</div>
        <h1 className="mt-4 text-2xl font-semibold">Settings</h1>
        <p className="mt-3 text-sm text-slate-400">
          Turn on alerts to get SOS and emergency updates on this device, even
          when the app is in the background.
        </p>
        <button className="btn btn-primary mt-6" onClick={enableAlerts}>
          🔔 Turn on alerts
        </button>
        {status && <p className="mt-4 text-sm text-slate-300">{status}</p>}
        <p className="mt-6 text-xs text-slate-500">
          You can change notification permission anytime in your browser or
          device settings.
        </p>
      </div>
    </div>
  );
}
