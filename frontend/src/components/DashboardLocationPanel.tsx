"use client";

import { useEffect, useState } from "react";
import { useUserLocation } from "@/hooks/useUserLocation";
import { apiCall } from "@/lib/api";
import { LocationMap } from "@/components/LocationMap";
import type { RiskScore, TrafficOverview, WeatherSummary } from "@/lib/types";
import { useAppLanguage } from "@/components/AppLanguageProvider";

const TRAFFIC_STYLES: Record<string, string> = {
  light: "text-emerald-300 bg-emerald-500/15 border-emerald-500/30",
  moderate: "text-amber-300 bg-amber-500/15 border-amber-500/30",
  heavy: "text-red-300 bg-red-500/15 border-red-500/30",
  unknown: "text-slate-300 bg-white/5 border-[var(--border)]",
};

const INCIDENT_ICONS: Record<string, string> = {
  accident: "🚗",
  construction: "🚧",
  congestion: "🐌",
  road_closure: "⛔",
  community_report: "👥",
};

const CONGESTION_LABELS: Record<string, string> = {
  light: "Light traffic",
  moderate: "Moderate traffic",
  heavy: "Heavy traffic",
  unknown: "Traffic unknown",
};

export function DashboardLocationPanel() {
  const { t } = useAppLanguage();
  const { coords, status, error, refresh } = useUserLocation(true);
  const [weather, setWeather] = useState<WeatherSummary | null>(null);
  const [risk, setRisk] = useState<RiskScore | null>(null);
  const [traffic, setTraffic] = useState<TrafficOverview | null>(null);
  const [loadingData, setLoadingData] = useState(false);
  const [weatherError, setWeatherError] = useState<string | null>(null);
  const [trafficError, setTrafficError] = useState<string | null>(null);

  useEffect(() => {
    if (!coords) return;

    (async () => {
      setLoadingData(true);
      setWeatherError(null);
      setTrafficError(null);
      const q = `?lat=${coords.lat}&lon=${coords.lon}`;
      const [weatherRes, riskRes, trafficRes] = await Promise.all([
        apiCall<WeatherSummary>(`/api/weather${q}`),
        apiCall<RiskScore>(`/api/weather/risk${q}`),
        apiCall<TrafficOverview>(`/api/traffic/nearby${q}&radius_km=5`),
      ]);
      if (weatherRes.ok) setWeather(weatherRes.data);
      else {
        setWeather(null);
        setWeatherError(weatherRes.error);
      }
      if (riskRes.ok) setRisk(riskRes.data);
      else setRisk(null);
      if (trafficRes.ok) setTraffic(trafficRes.data);
      else {
        setTraffic(null);
        setTrafficError(trafficRes.error);
      }
      setLoadingData(false);
    })();
  }, [coords]);

  const congestion = traffic?.congestion_level ?? "unknown";

  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-5 md:items-stretch">
        <div className={`flex flex-col overflow-hidden rounded-[14px] border border-[var(--border)] bg-[var(--surface)] md:col-span-3 ${coords ? "min-h-[280px] md:min-h-[360px] lg:min-h-[480px]" : ""}`}>
          <div className="flex items-center justify-between gap-3 px-3 py-2">
            <div className="mono-tag">{t("location.yours")}</div>
            <button
              type="button"
              onClick={refresh}
              className="min-h-11 text-xs text-[var(--accent-soft)] underline"
            >
              {t("location.refresh")}
            </button>
          </div>

          {status === "loading" && (
            <p className="px-3 pb-3 text-sm text-slate-400">Finding your location...</p>
          )}
          {status === "unsupported" && (
            <p className="px-3 pb-3 text-sm text-amber-300">{error}</p>
          )}
          {(status === "denied" || status === "error") && (
            <p className="px-3 pb-3 text-sm text-amber-300">{error}</p>
          )}
          {coords && (
            <LocationMap lat={coords.lat} lon={coords.lon} className="min-h-0 flex-1" />
          )}
          {!coords && status === "idle" && (
            <div className="px-3 pb-3">
              <button type="button" className="btn btn-outline text-sm" onClick={refresh}>
                Share location
              </button>
            </div>
          )}
        </div>

        <div className="grid gap-3 sm:grid-cols-2 md:col-span-2 md:grid-cols-1">
          <div className="glass-card p-4">
            <div className="mono-tag">{t("weather.title")}</div>
            {!coords ? (
              <p className="mt-3 text-sm text-slate-400">Share your location to see weather.</p>
            ) : loadingData && !weather && !weatherError ? (
              <p className="mt-3 text-sm text-slate-400">Loading weather...</p>
            ) : weatherError ? (
              <p className="mt-3 text-sm text-amber-300">Weather unavailable. {weatherError}</p>
            ) : (
              <>
                <h2 className="mt-2 text-xl font-semibold capitalize">
                  {weather?.condition ?? "Unavailable"}
                </h2>
                <p className="mt-1 text-2xl font-bold">
                  {weather ? `${Math.round(weather.temp_c)}°C` : "-"}
                </p>
                {weather && (
                  <p className="mt-2 text-xs text-slate-400">
                    Rain last hour: {weather.rain_mm_last_hour} mm
                  </p>
                )}
                {risk && (
                  <p className="mt-2 text-sm text-slate-400">
                    Flood risk:{" "}
                    <span className="capitalize text-slate-200">{risk.level}</span> (
                    {risk.score}/100)
                  </p>
                )}
              </>
            )}
          </div>

          <div className="glass-card p-4">
            <div className="mono-tag">{t("traffic.title")}</div>
            {!coords ? (
              <p className="mt-3 text-sm text-slate-400">Share your location to see traffic.</p>
            ) : (
              <>
                <div
                  className={`mt-3 inline-flex rounded-full border px-3 py-1 text-sm font-medium ${TRAFFIC_STYLES[congestion]}`}
                >
                  {CONGESTION_LABELS[congestion] ?? congestion}
                </div>
                <p className="mt-2 text-sm text-slate-400">
                  {trafficError
                    ? `Traffic data unavailable. ${trafficError}`
                    : traffic
                      ? `${traffic.incident_count} report(s) within ${traffic.radius_km} km`
                      : loadingData
                        ? "Checking nearby roads..."
                        : "Traffic updates unavailable"}
                </p>
              </>
            )}
          </div>
        </div>
      </div>

      {coords && traffic && traffic.incidents.length > 0 && (
        <div className="glass-card p-4">
          <div className="mono-tag mb-3">
            Road problems nearby
            {traffic.radius_km != null && (
              <span className="ml-2 text-slate-400">within {traffic.radius_km} km</span>
            )}
          </div>
          <div className="divide-y divide-[var(--border)]">
            {traffic.incidents.map((incident) => (
              <div key={incident.id} className="py-3 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span aria-hidden>{INCIDENT_ICONS[incident.type] ?? "📍"}</span>
                  <span className="font-medium text-white">{incident.title}</span>
                  <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs capitalize text-slate-300">
                    {incident.type.replaceAll("_", " ")}
                  </span>
                  {incident.verified ? (
                    <span className="text-xs text-emerald-300">Checked</span>
                  ) : (
                    <span className="text-xs text-amber-300">Not checked</span>
                  )}
                </div>
                <p className="mt-1 text-sm text-slate-300">{incident.description}</p>
                <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-500">
                  {typeof incident.distance_km === "number" && (
                    <span>{incident.distance_km.toFixed(1)} km away</span>
                  )}
                  {incident.lat != null && incident.lon != null && (
                    <a
                      className="text-[var(--accent-soft)] underline"
                      href={`https://www.google.com/maps/search/?api=1&query=${incident.lat},${incident.lon}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open map
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {coords && trafficError && (
        <p className="text-sm text-amber-200">
          Could not load nearby traffic. That is not the same as a clear road.
        </p>
      )}

      {coords && !trafficError && traffic && traffic.incidents.length === 0 && !loadingData && (
        <p className="text-sm text-slate-400">
          No incidents were returned from the sources we checked within 5 km. Drive carefully
          anyway — this is not a guarantee the roads are clear.
        </p>
      )}
    </div>
  );
}
