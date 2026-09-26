"use client";

import { useEffect, useState } from "react";
import { apiCall } from "@/lib/api";
import { useUserLocation } from "@/hooks/useUserLocation";
import type { Shelter } from "@/lib/types";
import { useAppLanguage } from "@/components/AppLanguageProvider";
import { PlaceMapThumb } from "@/components/LocationMap";

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number) {
  const r = 6371;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dp = ((lat2 - lat1) * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return r * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export default function SheltersPage() {
  const { t } = useAppLanguage();
  const { coords } = useUserLocation(true);
  const [shelters, setShelters] = useState<Shelter[]>([]);
  const [status, setStatus] = useState("Loading...");

  useEffect(() => {
    (async () => {
      const res = await apiCall<Shelter[]>("/api/shelters");
      if (!res.ok) {
        setStatus("Could not load shelters. Please try again.");
        return;
      }
      setShelters(res.data);
      setStatus(
        res.data.length
          ? `${res.data.length} shelters listed (manually maintained, not live occupancy).`
          : "No shelters found nearby.",
      );
    })();
  }, []);

  return (
    <div>
      <h1 className="text-xl font-semibold sm:text-2xl">{t("shelters.title")}</h1>
      <p className="mt-1 text-sm text-slate-400">{status}</p>
      <div className="glass-card mt-4 divide-y divide-white/10 p-3">
        {shelters.map((s) => {
          const pct = s.capacity ? Math.round((s.occupied / s.capacity) * 100) : 0;
          const distance =
            coords && s.lat != null && s.lon != null
              ? haversineKm(coords.lat, coords.lon, s.lat, s.lon)
              : null;
          return (
            <div key={s.id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
              <div className="min-w-0 flex-1">
                <div className="font-medium text-white">🏘️ {s.name}</div>
                {s.address && <p className="mt-0.5 truncate text-xs text-slate-400">{s.address}</p>}
                <p className="mt-1 text-sm text-slate-300">
                  Last listed: {s.occupied} of {s.capacity} spaces
                  <span className="ml-2 text-xs text-slate-500">Occupancy is not a live feed.</span>
                </p>
                <div className="mt-2 h-1.5 max-w-xs overflow-hidden rounded-full bg-white/10">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-[var(--accent)] to-[var(--primary)]"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
              {s.lat != null && s.lon != null && (
                <PlaceMapThumb
                  lat={s.lat}
                  lon={s.lon}
                  label={s.name}
                  distanceKm={distance}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
