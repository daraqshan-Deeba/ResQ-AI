"use client";

import type { ReactNode } from "react";
import type { AssessmentResult } from "@/lib/types";
import { PlaceMapThumb } from "@/components/LocationMap";
import { useAppLanguage } from "@/components/AppLanguageProvider";
import { CallNumberButton } from "@/components/CallNumberButton";
import { extractDialNumber } from "@/lib/phone";

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
  llm_restatement: "Restated in plain language",
  retrieved_examples: "Similar past examples",
  groq_grounded: "Groq wording, protocol steps",
  database: "Saved records",
};

const SERVICE_WARNINGS: Record<string, string> = {
  unavailable: "not available right now",
  service_disabled: "turned off",
  timeout: "took too long",
  network_error: "connection problem",
  auth_error: "could not connect",
  server_error: "temporary problem",
  fallback_used: "standard protocol (AI wording unavailable)",
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
    badge: "badge watch",
    ring: "border-amber-500/40",
    glow: "from-amber-600/15 via-amber-500/5 to-transparent",
  },
  unknown: {
    badge: "badge warning",
    ring: "border-orange-500/40",
    glow: "from-orange-600/20 via-orange-500/5 to-transparent",
  },
};

function formatSource(key: string, value: string) {
  const label = SOURCE_LABELS[value] ?? value.replaceAll("_", " ");
  return `${key.replaceAll("_", " ")}: ${label}`;
}

function levelKey(level: string) {
  return level.trim().toLowerCase();
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
    <section className={`rounded-xl border p-3 ${tones[tone]}`}>
      <div className="mb-2 flex items-center gap-2">
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

export function AssessmentResultPanel({
  result,
  onRequestSos,
  onAskQuestion,
}: {
  result: AssessmentResult;
  onRequestSos?: () => void;
  onAskQuestion?: (question: string) => void;
}) {
  const { t } = useAppLanguage();
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
  const questions = plan?.questions_to_ask_user ?? [];
  const thingsToCarry = result.things_to_carry ?? [];
  const carryCategories = new Set([
    "flooding",
    "flood",
    "cyclone",
    "fire",
    "structural_damage",
  ]);
  const showCarryKit = carryCategories.has((result.triage?.category ?? "").toLowerCase());

  const degraded = Object.entries(result.service_status ?? {}).filter(
    ([key, status]) =>
      key !== "community" &&
      !(key === "groq" && status === "fallback_used") &&
      status !== "available" &&
      status !== "not_requested" &&
      status !== "not_relevant" &&
      status !== "not_needed" &&
      status !== "none",
  );

  const showCallNow = ["unknown", "critical", "high"].includes(level);
  const weatherNotRelevant =
    result.weather?.status === "not_relevant" || result.service_status?.weather === "not_relevant";
  const weatherMissing =
    !weatherNotRelevant &&
    (!result.weather ||
      result.weather.status === "unavailable" ||
      result.weather.status === "not_requested" ||
      result.weather.score == null);
  const hospitalSearchFailed = (result.service_status?.maps ?? "").includes("fail") ||
    result.service_status?.maps === "server_error";

  return (
    <div className="space-y-3">
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

      <div className="grid gap-3 lg:grid-cols-3 lg:items-start">
        <div
          className={`relative overflow-hidden rounded-xl border ${levelStyle.ring} bg-[var(--surface)] p-4 lg:col-span-2`}
        >
          <div
            className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${levelStyle.glow}`}
          />
          <div className="relative">
            <div className="flex flex-wrap items-center gap-2">
              <p className="mono-tag mb-0">{t("result.yours")}</p>
              <span className={levelStyle.badge}>{result.emergency_level}</span>
              {result.triage?.category && (
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300">
                  {result.triage.category.replaceAll("_", " ")}
                </span>
              )}
            </div>
            {showCallNow && (
              <div className="mt-3 flex flex-wrap gap-2">
                <CallNumberButton phone="112" label="Call 112" className="btn btn-danger text-sm" />
                <CallNumberButton phone="108" label="Call 108" className="btn border border-white/20 bg-white/10 text-sm" />
                {onRequestSos && (
                  <button type="button" className="btn btn-danger text-sm" onClick={onRequestSos}>
                    Send SOS
                  </button>
                )}
              </div>
            )}
            <h2 className="mt-3 text-xl font-semibold leading-snug text-white">
              {plan?.explanation || result.whats_happening}
            </h2>
            {result.understood_as && (
              <p className="mt-1 text-sm text-slate-400">
                Understood as: {result.understood_as}
              </p>
            )}
            {result.triage?.explanation && (
              <p className="mt-1 text-sm text-slate-400">{result.triage.explanation}</p>
            )}
            {result.source_labels && Object.keys(result.source_labels).length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {Object.entries(result.source_labels).map(([key, value]) => (
                  <span
                    key={key}
                    className="rounded-full border border-[var(--border)] bg-white/5 px-2 py-0.5 text-[11px] text-slate-400"
                    title={formatSource(key, value)}
                  >
                    {formatSource(key, value)}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="rounded-xl border border-white/10 bg-black/20 p-3">
          <div className="mono-tag mb-2">{t("result.reliability")}</div>
          <div className="flex flex-wrap gap-1.5 text-xs text-slate-300">
            <span className="rounded-full border border-white/15 bg-white/5 px-2.5 py-1">
              Type: {(result.confidence?.triage_state ?? "unknown").replaceAll("_", " ")}
            </span>
            <span className="rounded-full border border-white/15 bg-white/5 px-2.5 py-1">
              Situation: {(result.confidence?.weather_state ?? "unknown").replaceAll("_", " ")}
            </span>
            <span className="rounded-full border border-white/15 bg-white/5 px-2.5 py-1">
              Guidance: {(result.confidence?.guidance_state ?? "standard_protocol").replaceAll("_", " ")}
            </span>
          </div>
          {result.confidence?.limiting_factor && (
            <p className="mt-2 text-xs text-slate-500">
              Limited by {result.confidence.limiting_factor.replaceAll("_", " ")}
            </p>
          )}
        </div>
      </div>

      {weatherNotRelevant ? null : weatherMissing ? (
        <div className="rounded-2xl border border-amber-500/25 bg-amber-500/10 p-4 text-sm text-amber-100">
          Live weather is not available for this result
          {result.weather?.status ? ` (${result.weather.status.replaceAll("_", " ")})` : ""}.
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-2xl border border-[var(--border)] bg-white/[0.03] p-4">
            <div className="mono-tag">Weather risk</div>
            <div className="mt-2 text-xl font-semibold capitalize">
              {result.weather?.level ?? "unknown"}
            </div>
            {typeof result.weather?.score === "number" && (
              <p className="mt-1 text-sm text-slate-400">Score {result.weather.score}</p>
            )}
          </div>
          <div className="rounded-2xl border border-[var(--border)] bg-white/[0.03] p-4">
            <div className="mono-tag">Conditions</div>
            <div className="mt-2 text-xl font-semibold capitalize">
              {result.weather?.condition ?? "-"}
            </div>
          </div>
          <div className="rounded-2xl border border-[var(--border)] bg-white/[0.03] p-4">
            <div className="mono-tag">Temperature</div>
            <div className="mt-2 text-xl font-semibold">
              {typeof result.weather?.temp_c === "number" ? `${result.weather.temp_c}°C` : "-"}
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2 [&>:last-child:nth-child(odd)]:md:col-span-2">
        {immediateActions.length > 0 && (
          <SectionCard title={t("result.doNow")} icon="✓" tone="success">
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
          <SectionCard title={t("result.doNot")} icon="✕" tone="danger">
            <ActionList items={safetyWarnings} marker="!" />
          </SectionCard>
        )}

        {whenToSeekHelp.length > 0 && (
          <SectionCard title={t("result.seekHelp")} icon="⚠" tone="info">
            <ActionList items={whenToSeekHelp} marker="→" />
          </SectionCard>
        )}

        {questions.length > 0 && (
          <SectionCard title={t("result.questions")} icon="?" tone="info">
            <p className="mb-3 text-xs text-slate-500">
              {t("result.questionsHint")}
            </p>
            <div className="flex flex-wrap gap-2">
              {questions.map((question) => (
                <button
                  key={question}
                  type="button"
                  className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1.5 text-left text-sm text-cyan-100"
                  onClick={() => onAskQuestion?.(question)}
                >
                  {question}
                </button>
              ))}
            </div>
          </SectionCard>
        )}

        {emergencyContacts.length > 0 && (
          <SectionCard title={t("result.callServices")} icon="☎" tone="default">
            <ul className="space-y-2.5 text-sm leading-relaxed text-slate-300">
              {emergencyContacts.map((item) => {
                const number = extractDialNumber(item);
                return (
                  <li key={item} className="flex gap-3">
                    <span className="mt-0.5 shrink-0 text-slate-500">•</span>
                    {number ? (
                      <CallNumberButton
                        phone={number}
                        label={item}
                        className="underline"
                      />
                    ) : (
                      <span>{item}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </SectionCard>
        )}

        {showCarryKit && thingsToCarry.length > 0 && (
          <SectionCard title={t("result.carry")} icon="🎒" tone="default">
            <ActionList items={thingsToCarry} marker="•" />
          </SectionCard>
        )}
      </div>

      {hospitalSearchFailed && (
        <div className="rounded-2xl border border-amber-500/25 bg-amber-500/10 p-4 text-sm text-amber-100">
          Hospital search failed. Call 112 / 108 for dispatch.
        </div>
      )}

      {result.hospitals && result.hospitals.length > 0 && (
        <SectionCard title={t("result.hospitals")} icon="🏥" tone="info">
          <div className="divide-y divide-white/10">
            {result.hospitals.map((hospital) => (
              <div
                key={`${hospital.name}-${hospital.lat}`}
                className="flex items-center gap-3 py-2 first:pt-0 last:pb-0"
              >
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-white">{hospital.name}</div>
                  {hospital.address && (
                    <p className="mt-0.5 truncate text-xs text-slate-400">{hospital.address}</p>
                  )}
                  <div className="mt-1 flex flex-wrap items-center gap-3 text-xs">
                    {hospital.phone && (
                      <a className="text-cyan-200 underline" href={`tel:${hospital.phone}`}>
                        {hospital.phone}
                      </a>
                    )}
                    <a
                      className="text-[var(--accent-soft)] underline"
                      href={`https://www.google.com/maps/search/?api=1&query=${hospital.lat},${hospital.lon}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {t("result.openMaps")}
                    </a>
                  </div>
                </div>
                {hospital.lat != null && hospital.lon != null && (
                  <PlaceMapThumb
                    lat={hospital.lat}
                    lon={hospital.lon}
                    label={hospital.name}
                    distanceKm={hospital.distance_km}
                  />
                )}
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
