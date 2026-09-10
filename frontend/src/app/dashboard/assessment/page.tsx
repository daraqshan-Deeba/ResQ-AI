"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { AssessmentResultPanel } from "@/components/AssessmentResultPanel";
import { useVoiceInput } from "@/hooks/useVoiceInput";
import { apiCall } from "@/lib/api";
import type { AssessmentResult, SosResponse } from "@/lib/types";

const presets: Record<string, { label: string; text: string; icon: string }> = {
  flooding: {
    label: "Flooding",
    icon: "🌊",
    text: "My house is flooding and water is rising fast.",
  },
  electrocution: {
    label: "Electrocution",
    icon: "⚡",
    text: "There are live wires down near standing water.",
  },
  injury: {
    label: "Injury",
    icon: "🩹",
    text: "Someone has a deep cut and is bleeding badly, needs medical help.",
  },
  snakebite: {
    label: "Snakebite",
    icon: "🐍",
    text: "Someone has been bitten by a snake, urgent medical help needed.",
  },
  cyclone: {
    label: "Cyclone",
    icon: "🌀",
    text: "Extreme cyclone winds and storm surge warning in our area.",
  },
  structural_damage: {
    label: "Structural damage",
    icon: "🏚️",
    text: "Part of the building wall and roof has collapsed.",
  },
  accident: {
    label: "Accident",
    icon: "🚗",
    text: "A road vehicle collision just occurred with injured passengers.",
  },
};

export default function AssessmentPage() {
  const [text, setText] = useState("");
  const [language, setLanguage] = useState("English");
  const [includeLocation, setIncludeLocation] = useState(false);
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AssessmentResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sosStatus, setSosStatus] = useState("");

  const appendVoiceText = useCallback((transcript: string) => {
    setText((prev) => (prev ? `${prev} ${transcript}` : transcript));
  }, []);
  const voice = useVoiceInput(appendVoiceText, language);

  function toggleLocation() {
    if (!includeLocation) {
      if (!navigator.geolocation) return;
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude });
          setIncludeLocation(true);
        },
        () => setIncludeLocation(false),
      );
      return;
    }
    setIncludeLocation(false);
    setCoords(null);
  }

  async function submitAssessment() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const payload: Record<string, unknown> = {
      description: text.trim(),
      language,
    };
    if (includeLocation && coords) {
      payload.lat = coords.lat;
      payload.lon = coords.lon;
    }

    const res = await apiCall<AssessmentResult>("/api/assessment", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    setLoading(false);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    setResult(res.data);
  }

  async function sendSos() {
    setSosStatus("Acquiring location…");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const res = await apiCall<SosResponse>("/api/sos", {
          method: "POST",
          body: JSON.stringify({
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            situation: text || "Emergency reported via assessment",
          }),
        });
        setSosStatus(res.ok ? res.data.message : `⚠️ ${res.error}`);
      },
      () => setSosStatus("⚠️ Location permission required. Dial 112 directly."),
    );
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div className="rounded-3xl border border-red-500/20 bg-gradient-to-br from-red-500/10 via-transparent to-transparent p-6 sm:p-8">
        <p className="mono-tag text-red-200/80">Primary emergency path</p>
        <h1 className="mt-2 text-3xl font-semibold text-white">Emergency Assessment</h1>
        <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-300">
          Describe what is happening. ResQ AI will triage the situation, check live weather,
          build a prioritized action plan, and surface nearby hospitals when you share location.
          Location is never captured automatically.
        </p>
      </div>

      <div className="mt-8">
        <div className="mono-tag mb-3">Quick scenarios</div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(presets).map(([key, preset]) => (
            <button
              key={key}
              className="glass-card group px-4 py-4 text-left transition hover:border-blue-500/40 hover:bg-white/[0.04]"
              onClick={() => setText(preset.text)}
            >
              <div className="flex items-start gap-3">
                <span className="text-xl" aria-hidden>{preset.icon}</span>
                <div>
                  <div className="font-medium text-white">{preset.label}</div>
                  <p className="mt-1 text-xs leading-relaxed text-slate-400">{preset.text}</p>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="mt-8">
        <div className="mono-tag mb-3">Your situation</div>
        <div className="relative">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Describe what's happening — type or use voice…"
            className="min-h-[140px] w-full rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 pr-16 text-sm text-white outline-none ring-0 transition focus:border-cyan-500/40"
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
              disabled={voice.transcribing}
              title="Record voice (Groq Whisper transcription)"
            >
              {voice.transcribing ? "…" : voice.listening ? "●" : "🎤"}
            </button>
          )}
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-500">
          {voice.listening && <span className="text-red-300">Recording — tap again to stop</span>}
          {voice.transcribing && <span className="text-cyan-300">Transcribing audio…</span>}
          {voice.error && <span className="text-amber-300">{voice.error}</span>}
          {voice.supported && !voice.listening && !voice.transcribing && (
            <span>Voice uses server-side transcription for better accuracy.</span>
          )}
        </div>
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
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={includeLocation} onChange={toggleLocation} />
          Include GPS for nearby hospital search
        </label>
      </div>

      <button
        className="btn btn-primary mt-6 w-full sm:w-auto"
        onClick={submitAssessment}
        disabled={loading || !text.trim()}
      >
        {loading ? "Assessing…" : "🚨 Get Help Now"}
      </button>

      <p className="mt-3 text-xs text-slate-500">
        For general questions only, use the{" "}
        <Link href="/dashboard/assistant" className="text-[var(--accent-soft)] underline">
          informational assistant
        </Link>
        . Urgent situations should stay on this page.
      </p>

      {(error || result) && (
        <div className="mt-10 space-y-6">
          {error && (
            <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-100">
              ⚠️ {error}. Call 112 if urgent.
            </div>
          )}
          {result && (
            <>
              <AssessmentResultPanel result={result} />
              <div className="rounded-2xl border border-red-500/25 bg-red-500/5 p-5">
                <p className="text-sm text-slate-300">
                  If you need immediate dispatch, send an explicit SOS alert. This shares your
                  location only when you confirm below.
                </p>
                <button className="btn btn-danger mt-4 w-full" onClick={sendSos}>
                  🚨 Send One-Tap SOS Alert
                </button>
                {sosStatus && <p className="mt-3 text-sm text-slate-300">{sosStatus}</p>}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
