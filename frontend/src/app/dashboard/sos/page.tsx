"use client";

import { useState } from "react";
import { apiCall } from "@/lib/api";
import type { SosResponse } from "@/lib/types";

export default function SosPage() {
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  function confirmSos() {
    if (!navigator.geolocation) {
      setStatus("Location isn't available in this browser.");
      return;
    }
    setLoading(true);
    setStatus("Getting your location…");
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        setStatus("Sending SOS…");
        const res = await apiCall<SosResponse>("/api/sos", {
          method: "POST",
          body: JSON.stringify({
            lat: position.coords.latitude,
            lon: position.coords.longitude,
          }),
        });
        setLoading(false);
        setStatus(res.ok ? res.data.message : `⚠️ ${res.error}`);
      },
      () => {
        setLoading(false);
        setStatus("Could not get your location — check browser permissions.");
      },
    );
  }

  return (
    <div className="mx-auto flex max-w-md flex-col items-center py-12 text-center">
      <div className="glass-card w-full p-8">
        <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-[var(--danger)] text-3xl shadow-[0_0_40px_rgba(239,68,68,0.3)]">
          🚨
        </div>
        <h1 className="text-2xl font-semibold">Send an SOS</h1>
        <p className="mt-3 text-sm text-slate-400">
          Pressing this records your emergency and sends a push alert with your
          live location. You must confirm explicitly — location is never automatic.
        </p>
        <button
          className="btn btn-danger mt-8 w-full"
          onClick={confirmSos}
          disabled={loading}
        >
          Confirm SOS
        </button>
        {status && <p className="mt-4 text-sm text-slate-300">{status}</p>}
      </div>
    </div>
  );
}
