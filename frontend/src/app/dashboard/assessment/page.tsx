"use client";

import { FormEvent, useCallback, useRef, useState } from "react";
import { AssessmentResultPanel } from "@/components/AssessmentResultPanel";
import { SosConfirmModal } from "@/components/SosConfirmModal";
import { useUserLocation } from "@/hooks/useUserLocation";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { apiCall } from "@/lib/api";
import type { AssessmentResult } from "@/lib/types";

export default function AssessmentPage() {
  const [text, setText] = useState("");
  const [language, setLanguage] = useState("English");
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

  const onTranscript = useCallback(
    (transcript: string) => {
      setText((prev) => {
        const next = prev.trim() ? `${prev.trim()} ${transcript}` : transcript;
        void runAssessment(next);
        return next;
      });
    },
    [runAssessment],
  );

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
    <div className="mx-auto max-w-3xl">
      <div className="rounded-3xl border border-red-500/20 bg-gradient-to-br from-red-500/10 via-transparent to-transparent p-6 sm:p-8">
        <p className="mono-tag text-red-200/80">Need help now</p>
        <h1 className="mt-2 text-3xl font-semibold text-white">Get help</h1>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-300">
          Say or type what is happening. The backend classifies the situation,
          fetches only the evidence that matters, and returns standard steps.
          For a life-threatening emergency, call 112 first.
        </p>
      </div>

      <form className="mt-8" onSubmit={onSubmit}>
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
            placeholder="What is happening? Speak or type, then go."
            className="min-h-[160px] w-full rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 pr-16 text-sm text-white outline-none ring-0 transition focus:border-cyan-500/40"
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
          {voice.listening && <span className="text-red-300">Recording. Tap again to stop — we will assess automatically.</span>}
          {voice.transcribing && <span className="text-cyan-300">Converting speech to text...</span>}
          {voice.error && <span className="text-amber-300">{voice.error}</span>}
          {loading && <span className="text-cyan-200">Working on your situation...</span>}
          {!voice.listening && !voice.transcribing && !loading && (
            <span>Tap the microphone to speak, or press Enter to send.</span>
          )}
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-4">
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
          >
            <option>English</option>
            <option>Telugu</option>
            <option>Hindi</option>
          </select>
          <p className="max-w-md text-xs text-slate-500">{locationHint}</p>
        </div>

        <button
          type="submit"
          className="btn btn-primary mt-6 w-full sm:w-auto"
          disabled={loading || !text.trim()}
        >
          {loading ? "Working..." : "Get help"}
        </button>
      </form>

      {(error || result) && (
        <div className="mt-10 space-y-6">
          {error && (
            <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-100">
              {error}. Call 112 if this is urgent.
            </div>
          )}
          {result && (
            <AssessmentResultPanel
              result={result}
              onRequestSos={() => setSosOpen(true)}
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
