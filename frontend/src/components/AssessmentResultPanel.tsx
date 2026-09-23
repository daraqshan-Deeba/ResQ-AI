import type { ReactNode } from "react";
import type { AssessmentResult } from "@/lib/types";

const SOURCE_LABELS: Record<string, string> = {
  deterministic_keyword: "Matched known phrases",
  embedding_similarity: "Matched similar examples",
  embedding_or_ml: "Matched from rules and examples",
  ai_classification: "Suggested category",
  live_weather_api: "Live weather",
  unavailable: "Not available",
  not_used: "Not used",
  ai_generated: "Written guidance",
  deterministic_fallback: "Standard guidance",
  supabase_directory: "Hospital directory",
  firebase_directory: "Hospital directory",
  location_not_provided: "Location not shared",
  community_reports: "Local reports",
  none: "None found",
  database: "Saved records",
};

const SERVICE_WARNINGS: Record<string, string> = {
  unavailable: "not available right now",
  service_disabled: "turned off",
  timeout: "took too long",
  network_error: "connection problem",
  auth_error: "could not connect",
  server_error: "temporary problem",
  fallback_used: "using standard guidance",
};

const LEVEL_STYLES: Record<string, { badge: string; ring: string; glow: string }> = {
  critical: {
    badge: "badge critical",
    ring: "border-red-500/40",
    glow: "from-red-600/20 via-red-500/5 to-transparent",
  },
  high: {
    badge: "badge warning",
    ring: "border-orange-500/40",
    glow: "from-orange-600/20 via-orange-500/5 to-transparent",
  },
  moderate: {
    badge: "badge watch",
    ring: "border-amber-500/40",
    glow: "from-amber-600/15 via-amber-500/5 to-transparent",
  },
  low: {
    badge: "badge safe",
    ring: "border-emerald-500/40",
    glow: "from-emerald-600/15 via-emerald-500/5 to-transparent",
  },
};

function formatSource(key: string, value: string) {
  const label = SOURCE_LABELS[value] ?? value.replaceAll("_", " ");
  return `${key.replaceAll("_", " ")}: ${label}`;
}

function levelKey(level: string) {
  return level.trim().toLowerCase();
}

function confidenceTone(level?: string) {
  if (level === "high") return "text-emerald-300";
  if (level === "medium") return "text-amber-300";
  return "text-red-300";
}

function SectionCard({
  title,
  icon,
  tone = "default",
  children,
}: {
  title: string;
  icon: string;
  tone?: "default" | "danger" | "info" | "success";
  children: ReactNode;
}) {
  const tones = {
    default: "border-[var(--border)] bg-white/[0.03]",
    danger: "border-red-500/25 bg-red-500/[0.06]",
    info: "border-cyan-500/25 bg-cyan-500/[0.05]",
    success: "border-emerald-500/25 bg-emerald-500/[0.05]",
  };

  return (
    <section className={`rounded-2xl border p-5 ${tones[tone]}`}>
      <div className="mb-3 flex items-center gap-2">
        <span className="text-lg" aria-hidden>{icon}</span>
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-200">
          {title}
        </h3>
      </div>
      {children}
    </section>
  );
}

function ActionList({ items, marker }: { items: string[]; marker: string }) {
  return (
    <ul className="space-y-2.5 text-sm leading-relaxed text-slate-300">
      {items.map((item) => (
        <li key={item} className="flex gap-3">
          <span className="mt-0.5 shrink-0 text-slate-500">{marker}</span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function AssessmentResultPanel({ result }: { result: AssessmentResult }) {
  const plan = result.action_plan;
  const level = levelKey(result.emergency_level);
  const levelStyle = LEVEL_STYLES[level] ?? LEVEL_STYLES.moderate;

  const immediateActions =
    plan?.immediate_actions?.length ? plan.immediate_actions : result.immediate_first_aid ?? [];
  const safetyWarnings =
    plan?.safety_warnings?.length ? plan.safety_warnings : result.what_not_to_do ?? [];
  const emergencyContacts =
    plan?.emergency_contacts?.length
      ? plan.emergency_contacts
      : result.call_these_services ?? [];
  const whenToSeekHelp = plan?.when_to_seek_help ?? [];
  const thingsToCarry = result.things_to_carry ?? [];

  const degraded = Object.entries(result.service_status ?? {}).filter(
    ([key, status]) =>
      key !== "community" &&
      status !== "available" &&
      status !== "not_requested" &&
      status !== "none",
  );

  const confidencePct = Math.round((result.confidence?.overall_confidence ?? 0) * 100);

  return (
    <div className="space-y-5">
      {degraded.length > 0 && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
          <div className="font-medium">Some information is incomplete</div>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-amber-100/90">
            {degraded.map(([service, status]) => (
              <li key={service}>
                {service}: {SERVICE_WARNINGS[status] ?? status.replaceAll("_", " ")}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div
        className={`relative overflow-hidden rounded-3xl border ${levelStyle.ring} bg-[var(--surface)] p-6`}
      >
        <div
          className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${levelStyle.glow}`}
        />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 flex-1">
            <p className="mono-tag mb-2">Your result</p>
            <div className="flex flex-wrap items-center gap-2">
              <span className={levelStyle.badge}>{result.emergency_level}</span>
              {result.triage?.category && (
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                  {result.triage.category.replaceAll("_", " ")}
                </span>
              )}
            </div>
            <h2 className="mt-4 text-2xl font-semibold leading-snug text-white">
              {plan?.explanation || result.whats_happening}
            </h2>
            {result.triage?.explanation && (
              <p className="mt-2 text-sm text-slate-400">{result.triage.explanation}</p>
            )}
          </div>

          <div className="w-full shrink-0 rounded-2xl border border-white/10 bg-black/20 p-4 sm:w-56">
            <div className="mono-tag mb-2">Confidence</div>
            <div className={`text-3xl font-semibold ${confidenceTone(result.confidence?.confidence_level)}`}>
              {confidencePct}%
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500 transition-all"
                style={{ width: `${confidencePct}%` }}
              />
            </div>
            {result.confidence?.confidence_level && (
              <p className="mt-2 text-xs text-slate-400">
                Level: {result.confidence.confidence_level}
              </p>
            )}
            {result.confidence?.limiting_factor && (
              <p className="mt-1 text-xs text-slate-500">
                Limited by {result.confidence.limiting_factor.replaceAll("_", " ")}
              </p>
            )}
          </div>
        </div>
      </div>

      {result.weather && (
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border border-[var(--border)] bg-white/[0.03] p-4">
            <div className="mono-tag">Weather risk</div>
            <div className="mt-2 text-xl font-semibold capitalize">
              {result.weather.level ?? "unknown"}
            </div>
            {typeof result.weather.score === "number" && (
              <p className="mt-1 text-sm text-slate-400">Score {result.weather.score}</p>
            )}
          </div>
          <div className="rounded-2xl border border-[var(--border)] bg-white/[0.03] p-4">
            <div className="mono-tag">Conditions</div>
            <div className="mt-2 text-xl font-semibold capitalize">
              {result.weather.condition ?? "-"}
            </div>
          </div>
          <div className="rounded-2xl border border-[var(--border)] bg-white/[0.03] p-4">
            <div className="mono-tag">Temperature</div>
            <div className="mt-2 text-xl font-semibold">
              {typeof result.weather.temp_c === "number" ? `${result.weather.temp_c}°C` : "-"}
            </div>
          </div>
        </div>
      )}

      {result.source_labels && Object.keys(result.source_labels).length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(result.source_labels).map(([key, value]) => (
            <span
              key={key}
              className="rounded-full border border-[var(--border)] bg-white/5 px-2.5 py-1 text-xs text-slate-400"
              title={formatSource(key, value)}
            >
              {formatSource(key, value)}
            </span>
          ))}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {immediateActions.length > 0 && (
          <SectionCard title="Do this now" icon="✓" tone="success">
            <ol className="space-y-2.5 text-sm leading-relaxed text-slate-300">
              {immediateActions.map((item, index) => (
                <li key={item} className="flex gap-3">
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-xs font-semibold text-emerald-300">
                    {index + 1}
                  </span>
                  <span>{item}</span>
                </li>
              ))}
            </ol>
          </SectionCard>
        )}

        {safetyWarnings.length > 0 && (
          <SectionCard title="Do not do this" icon="✕" tone="danger">
            <ActionList items={safetyWarnings} marker="!" />
          </SectionCard>
        )}

        {whenToSeekHelp.length > 0 && (
          <SectionCard title="Seek help immediately if" icon="⚠" tone="info">
            <ActionList items={whenToSeekHelp} marker="→" />
          </SectionCard>
        )}

        {emergencyContacts.length > 0 && (
          <SectionCard title="Call these services" icon="☎" tone="default">
            <ActionList items={emergencyContacts} marker="•" />
          </SectionCard>
        )}
      </div>

      {thingsToCarry.length > 0 && (
        <SectionCard title="Things to carry" icon="🎒" tone="default">
          <ActionList items={thingsToCarry} marker="•" />
        </SectionCard>
      )}

      {result.hospitals && result.hospitals.length > 0 && (
        <SectionCard title="Nearby hospitals" icon="🏥" tone="info">
          <div className="space-y-3">
            {result.hospitals.map((hospital) => (
              <div
                key={`${hospital.name}-${hospital.lat}`}
                className="rounded-xl border border-white/10 bg-black/20 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="font-medium text-white">{hospital.name}</div>
                    {hospital.address && (
                      <p className="mt-1 text-sm text-slate-400">{hospital.address}</p>
                    )}
                  </div>
                  {typeof hospital.distance_km === "number" && (
                    <span className="rounded-full bg-cyan-500/15 px-2.5 py-1 text-xs text-cyan-200">
                      {hospital.distance_km.toFixed(1)} km
                    </span>
                  )}
                </div>
                <a
                  className="mt-3 inline-flex text-sm text-[var(--accent-soft)] underline"
                  href={`https://www.google.com/maps/search/?api=1&query=${hospital.lat},${hospital.lon}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open in maps
                </a>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {result.community_insights && result.community_insights.length > 0 && (
        <SectionCard title="Local reports" icon="👥" tone="default">
          <p className="mb-3 text-xs text-slate-500">Check these updates yourself before you act on them.</p>
          <div className="space-y-3">
            {result.community_insights.map((insight) => (
              <div
                key={insight.id}
                className="rounded-xl border border-white/10 bg-black/20 p-3 text-sm"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <b>{insight.area}</b>
                  <span className="text-xs text-slate-400">
                    {insight.source === "knowledge_asset" ? "Safety note" : "Local report"}
                  </span>
                  {insight.verified ? (
                    <span className="text-xs text-[var(--accent-soft)]">Checked</span>
                  ) : (
                    <span className="text-xs text-amber-300">Not checked</span>
                  )}
                </div>
                <p className="mt-1 text-slate-300">{insight.message}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      )}
    </div>
  );
}
