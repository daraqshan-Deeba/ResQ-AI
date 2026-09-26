"use client";

import { FormEvent, useCallback, useRef, useState } from "react";
import { AssessmentResultPanel } from "@/components/AssessmentResultPanel";
import { LanguageSelect } from "@/components/LanguageSelect";
import { SosConfirmModal } from "@/components/SosConfirmModal";
import { useUserLocation } from "@/hooks/useUserLocation";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { apiCall } from "@/lib/api";
import { useAppLanguage } from "@/components/AppLanguageProvider";
import type { AssessmentResult } from "@/lib/types";

export default function AssessmentPage() {
  const { language, setLanguage, t } = useAppLanguage();
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sosOpen, setSosOpen] = useState(false);
  const { coords, status: locationStatus } = useUserLocation(true);
  const loadingRef = useRef(false);

  const runAssessment = useCallback(
    async (description: string) => {
      const trimmed = description.trim();
      if (!trimmed || loadingRef.current) return;
      loadingRef.current = true;
      setLoading(true);
      setError(null);
      setResult(null);

      const payload: Record<string, unknown> = {
        description: trimmed,
        language,
      };
      if (coords) {
        payload.lat = coords.lat;
        payload.lon = coords.lon;
      }

      const res = await apiCall<AssessmentResult>("/api/assessment", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      loadingRef.current = false;
      setLoading(false);
      if (!res.ok) {
        setError(res.error);
        return;
      }
      setResult(res.data);
    },
    [coords, language],
  );

  const onTranscript = useCallback((transcript: string) => {
    setText((prev) => (prev.trim() ? `${prev.trim()} ${transcript}` : transcript));
  }, []);

  const voice = useVoiceInput(onTranscript, language);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void runAssessment(text);
  }

  const locationHint =
    locationStatus === "granted" && coords
      ? "Using your location for nearby hospitals and weather when they apply."
      : locationStatus === "loading"
        ? "Getting your location..."
        : locationStatus === "denied"
          ? "Location is off. You still get protocol steps. Call 112 if this is urgent."
          : "Location will be used for hospitals and weather when the situation needs it.";

  return (
    <div className="max-w-none">
      <div className="rounded-2xl border border-red-500/20 bg-gradient-to-br from-red-500/10 via-transparent to-transparent p-3 sm:p-4">
        <p className="mono-tag text-red-200/80">{t("help.tag")}</p>
        <h1 className="mt-1 text-xl font-semibold text-white sm:text-2xl">{t("help.title")}</h1>
        {!result && (
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-300">
            {t("help.intro")}
          </p>
        )}
      </div>

      <form className="mt-3" onSubmit={onSubmit}>
        <div className="relative">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void runAssessment(text);
              }
            }}
            placeholder={t("help.placeholder")}
            className={`w-full rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-3 pr-16 text-sm text-white outline-none ring-0 transition focus:border-cyan-500/40 ${
              result ? "min-h-[72px]" : "min-h-[120px]"
            }`}
            disabled={loading}
          />
          {voice.supported && (
            <button
              type="button"
              className={`absolute right-3 top-3 flex h-11 w-11 items-center justify-center rounded-full border text-lg transition ${
                voice.listening
                  ? "animate-pulse border-red-400/60 bg-red-500/20 text-red-100"
                  : voice.transcribing
                    ? "border-cyan-400/50 bg-cyan-500/15 text-cyan-100"
                    : "border-[var(--border)] bg-white/5 text-slate-300 hover:border-cyan-500/40"
              }`}
              onClick={voice.toggle}
              disabled={voice.transcribing || loading}
              title="Record your voice"
            >
              {voice.transcribing ? "..." : voice.listening ? "●" : "🎤"}
            </button>
          )}
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-500">
          {voice.listening && <span className="text-red-300">Recording. Tap again to stop, then review the text and press Get help.</span>}
          {voice.transcribing && <span className="text-cyan-300">Converting speech to text...</span>}
          {voice.error && <span className="text-amber-300">{voice.error}</span>}
          {loading && <span className="text-cyan-200">Working on your situation...</span>}
          {!result && !voice.listening && !voice.transcribing && !loading && (
            <span>{t("help.mic")}</span>
          )}
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            type="submit"
            className="btn btn-primary w-full sm:w-auto"
            disabled={loading || !text.trim()}
          >
            {loading ? t("help.working") : t("help.submit")}
          </button>
          <label className="text-xs text-slate-500">
            {t("language.label")}
            <span className="ml-2 inline-block">
              <LanguageSelect value={language} onChange={setLanguage} />
            </span>
          </label>
          {!result && (
            <p className="max-w-md text-xs text-slate-500">
              {t("help.protocolNote")}
              {locationHint ? ` ${locationHint}` : ""}
            </p>
          )}
        </div>
      </form>

      {(error || result) && (
        <div className="mt-4">
          {error && (
            <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-100">
              {error}. Call 112 if this is urgent.
            </div>
          )}
          {result && (
            <AssessmentResultPanel
              result={result}
              onRequestSos={() => setSosOpen(true)}
              onAskQuestion={(question) => {
                setText((prev) => `${prev.trim()}\n${question}`);
              }}
            />
          )}
        </div>
      )}

      <SosConfirmModal
        open={sosOpen}
        onClose={() => setSosOpen(false)}
        situation={text || result?.whats_happening || undefined}
      />
    </div>
  );
}
