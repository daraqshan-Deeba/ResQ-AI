"use client";

import { useEffect, useState } from "react";
import { apiCall } from "@/lib/api";
import { useUserLocation } from "@/hooks/useUserLocation";
import type { Hospital } from "@/lib/types";

export default function HospitalsPage() {
  const { coords, status: locStatus, error: locError, refresh } = useUserLocation(true);
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [status, setStatus] = useState("Finding your location...");

  useEffect(() => {
    if (locStatus === "loading" || locStatus === "idle") {
      setStatus("Finding your location...");
      return;
    }
    if (locStatus === "denied" || locStatus === "unsupported" || locStatus === "error") {
      setHospitals([]);
      setStatus(locError || "Location is required to find nearby hospitals.");
      return;
    }
    if (!coords) return;

    (async () => {
      setStatus("Searching nearby hospitals...");
      const res = await apiCall<Hospital[]>(
        `/api/hospitals?lat=${coords.lat}&lon=${coords.lon}`,
      );
      if (!res.ok) {
        setHospitals([]);
        setStatus(res.error || "Hospital search failed. Call 112 if this is an emergency.");
        return;
      }
      setHospitals(res.data);
      setStatus(
        res.data.length
          ? `${res.data.length} hospitals and clinics found.`
          : "No hospitals found within 5 km of your location.",
      );
    })();
  }, [coords, locStatus, locError]);

  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Hospitals</h1>
          <p className="mt-2 text-sm text-slate-400">{status}</p>
        </div>
        <button
          type="button"
          onClick={refresh}
          className="text-xs text-[var(--accent-soft)] underline"
        >
          Refresh location
        </button>
      </div>
      <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {hospitals.map((h) => (
          <div key={`${h.name}-${h.lat}`} className="glass-card p-5">
            <div className="text-lg font-medium">➕ {h.name}</div>
            {h.facility_type && (
              <span className="mt-2 inline-block rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-300">
                {h.facility_type}
              </span>
            )}
            {h.address && <p className="mt-2 text-sm text-slate-400">📍 {h.address}</p>}
            {typeof h.distance_km === "number" && (
              <p className="mt-1 text-xs text-cyan-300">{h.distance_km.toFixed(1)} km away</p>
            )}
            <a
              href={`https://maps.google.com/?q=${h.lat},${h.lon}`}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-block text-sm text-[var(--accent-soft)]"
            >
              Open in Maps
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
