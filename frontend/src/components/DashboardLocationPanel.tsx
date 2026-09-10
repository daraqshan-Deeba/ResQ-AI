"use client";

import { useEffect, useState } from "react";
import { useUserLocation } from "@/hooks/useUserLocation";
import { apiCall } from "@/lib/api";
import type { RiskScore, TrafficOverview, WeatherSummary } from "@/lib/types";

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

export function DashboardLocationPanel() {
  const { coords, status, error, refresh } = useUserLocation(true);
  const [weather, setWeather] = useState<WeatherSummary | null>(null);
  const [risk, setRisk] = useState<RiskScore | null>(null);
  const [traffic, setTraffic] = useState<TrafficOverview | null>(null);
  const [loadingData, setLoadingData] = useState(false);

  useEffect(() => {
    if (!coords) return;

    (async () => {
      setLoadingData(true);
      const q = `?lat=${coords.lat}&lon=${coords.lon}`;
      const [weatherRes, riskRes, trafficRes] = await Promise.all([
        apiCall<WeatherSummary>(`/api/weather${q}`),
        apiCall<RiskScore>(`/api/weather/risk${q}`),
        apiCall<TrafficOverview>(`/api/traffic/nearby${q}&radius_km=5`),
      ]);
      if (weatherRes.ok) setWeather(weatherRes.data);
      if (riskRes.ok) setRisk(riskRes.data);
      if (trafficRes.ok) setTraffic(trafficRes.data);
      setLoadingData(false);
    })();
  }, [coords]);

  const congestion = traffic?.congestion_level ?? "unknown";

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="glass-card p-6">
          <div className="flex items-start justify-between gap-3">
            <div className="mono-tag">Your location</div>
            <button
              type="button"
              onClick={refresh}
              className="text-xs text-[var(--accent-soft)] underline"
            >
              Refresh
            </button>
          </div>

          {status === "loading" && (
            <p className="mt-4 text-sm text-slate-400">Acquiring GPS coordinates…</p>
          )}
          {status === "unsupported" && (
            <p className="mt-4 text-sm text-amber-300">{error}</p>
          )}
          {(status === "denied" || status === "error") && (
            <p className="mt-4 text-sm text-amber-300">{error}</p>
          )}
          {coords && (
            <div className="mt-4 space-y-2 font-mono text-sm text-slate-200">
              <div>Latitude: {coords.lat.toFixed(6)}°</div>
              <div>Longitude: {coords.lon.toFixed(6)}°</div>
              {coords.accuracy != null && (
                <div className="text-slate-400">Accuracy ±{Math.round(coords.accuracy)} m</div>
              )}
            </div>
          )}
          {!coords && status === "idle" && (
            <button type="button" className="btn btn-outline mt-4 text-sm" onClick={refresh}>
              Enable location
            </button>
          )}
        </div>

        <div className="glass-card p-6">
          <div className="mono-tag">Weather at your location</div>
          {!coords ? (
            <p className="mt-4 text-sm text-slate-400">Share location to load local weather.</p>
          ) : loadingData && !weather ? (
            <p className="mt-4 text-sm text-slate-400">Loading weather…</p>
          ) : (
            <>
              <h2 className="mt-3 text-2xl font-semibold capitalize">
                {weather?.condition ?? "Unavailable"}
              </h2>
              <p className="mt-2 text-3xl font-bold">
                {weather ? `${Math.round(weather.temp_c)}°C` : "—"}
              </p>
              {weather && (
                <p className="mt-2 text-sm text-slate-400">
                  Rain last hour: {weather.rain_mm_last_hour} mm
                </p>
              )}
              {risk && (
                <p className="mt-3 text-sm text-slate-400">
                  Flood risk: <span className="capitalize text-slate-200">{risk.level}</span> (
                  {risk.score}/100)
                </p>
              )}
            </>
          )}
        </div>

        <div className="glass-card p-6">
          <div className="mono-tag">Traffic near you</div>
          {!coords ? (
            <p className="mt-4 text-sm text-slate-400">Share location to check nearby traffic.</p>
          ) : (
            <>
              <div
                className={`mt-4 inline-flex rounded-full border px-3 py-1 text-sm font-medium capitalize ${TRAFFIC_STYLES[congestion]}`}
              >
                {congestion} congestion
              </div>
              <p className="mt-3 text-sm text-slate-400">
                {traffic
                  ? `${traffic.incident_count} incident(s) within ${traffic.radius_km} km`
                  : loadingData
                    ? "Scanning roads…"
                    : "No traffic data"}
              </p>
              {traffic?.sources_used?.length ? (
                <p className="mt-2 text-xs text-slate-500">
                  Sources: {traffic.sources_used.join(", ")}
                </p>
              ) : null}
            </>
          )}
        </div>
      </div>

      {coords && traffic && traffic.incidents.length > 0 && (
        <div className="glass-card p-6">
          <div className="mono-tag mb-4">Road incidents &amp; disruptions</div>
          <div className="space-y-3">
            {traffic.incidents.map((incident) => (
              <div
                key={incident.id}
                className="rounded-xl border border-[var(--border)] bg-white/[0.03] p-4"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span aria-hidden>{INCIDENT_ICONS[incident.type] ?? "📍"}</span>
                  <span className="font-medium text-white">{incident.title}</span>
                  <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs capitalize text-slate-300">
                    {incident.type.replaceAll("_", " ")}
                  </span>
                  {incident.verified ? (
                    <span className="text-xs text-emerald-300">Verified</span>
                  ) : (
                    <span className="text-xs text-amber-300">Unverified</span>
                  )}
                </div>
                <p className="mt-2 text-sm text-slate-300">{incident.description}</p>
                <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                  <span>Source: {incident.source.replaceAll("_", " ")}</span>
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
                      View on map
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {coords && traffic && traffic.incidents.length === 0 && !loadingData && (
        <div className="glass-card p-6 text-sm text-slate-400">
          No accidents, construction, or congestion reports found within 5 km. Roads look relatively
          clear — still drive carefully in wet conditions.
        </div>
      )}
    </div>
  );
}
