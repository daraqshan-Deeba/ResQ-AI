"use client";

import { useEffect, useState } from "react";
import { apiCall } from "@/lib/api";
import type { Hospital } from "@/lib/types";

export default function HospitalsPage() {
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [status, setStatus] = useState("Loading...");

  useEffect(() => {
    (async () => {
      const res = await apiCall<Hospital[]>("/api/hospitals");
      if (!res.ok) {
        setStatus("Could not load hospitals. Please try again.");
        return;
      }
      setHospitals(res.data);
      setStatus(
        res.data.length
          ? `${res.data.length} hospitals and clinics found.`
          : "No hospitals found nearby.",
      );
    })();
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold">Hospitals</h1>
      <p className="mt-2 text-sm text-slate-400">{status}</p>
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
