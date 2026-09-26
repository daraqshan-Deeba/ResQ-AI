"use client";

import { useEffect, useState } from "react";
import { apiCall } from "@/lib/api";
import { useUserLocation } from "@/hooks/useUserLocation";
import type { Hospital } from "@/lib/types";
import { useAppLanguage } from "@/components/AppLanguageProvider";
import { PlaceMapThumb } from "@/components/LocationMap";

export default function HospitalsPage() {
  const { t } = useAppLanguage();
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
          <h1 className="text-xl font-semibold sm:text-2xl">{t("hospitals.title")}</h1>
          <p className="mt-1 text-sm text-slate-400">{status}</p>
          <p className="mt-1 text-xs text-slate-500">
            {t("hospitals.directory")}
          </p>
        </div>
        <button
          type="button"
          onClick={refresh}
          className="text-xs text-[var(--accent-soft)] underline"
        >
          Refresh location
        </button>
      </div>
      <div className="glass-card mt-4 divide-y divide-white/10 p-3">
        {hospitals.map((h) => (
          <div
            key={`${h.name}-${h.lat}`}
            className="flex items-center gap-3 py-3 first:pt-0 last:pb-0"
          >
            <div className="min-w-0 flex-1">
              <div className="font-medium text-white">➕ {h.name}</div>
              {h.facility_type && (
                <span className="mt-1 inline-block rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-300">
                  {h.facility_type}
                </span>
              )}
              {h.address && <p className="mt-0.5 truncate text-xs text-slate-400">📍 {h.address}</p>}
              <div className="mt-1 flex flex-wrap items-center gap-3 text-xs">
                {h.phone && (
                  <a className="text-cyan-200 underline" href={`tel:${h.phone}`}>
                    {h.phone}
                  </a>
                )}
                <a
                  href={`https://maps.google.com/?q=${h.lat},${h.lon}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[var(--accent-soft)] underline"
                >
                  Open in Maps
                </a>
              </div>
            </div>
            {h.lat != null && h.lon != null && (
              <PlaceMapThumb
                lat={h.lat}
                lon={h.lon}
                label={h.name}
                distanceKm={h.distance_km}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
