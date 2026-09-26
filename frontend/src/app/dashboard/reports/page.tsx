"use client";

import { useEffect, useState } from "react";
import { apiCall, apiUpload } from "@/lib/api";
import type { Report } from "@/lib/types";
import { useAppLanguage } from "@/components/AppLanguageProvider";
import { PlaceMapThumb } from "@/components/LocationMap";

function isStale(iso: string) {
  const ageMs = Date.now() - new Date(iso).getTime();
  return ageMs > 24 * 60 * 60 * 1000;
}

function timeAgo(iso: string) {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "unknown time";
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return days === 1 ? "1 day ago" : `${days} days ago`;
  const weeks = Math.round(days / 7);
  if (weeks < 8) return weeks === 1 ? "1 week ago" : `${weeks} weeks ago`;
  return new Date(then).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function ReportsPage() {
  const { t } = useAppLanguage();
  const [reports, setReports] = useState<Report[]>([]);
  const [area, setArea] = useState("");
  const [message, setMessage] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState("Loading...");

  async function load() {
    const res = await apiCall<Report[]>("/api/reports");
    if (!res.ok) {
      setStatus("Could not load reports. Please try again.");
      return;
    }
    setReports(res.data);
    setStatus(
      res.data.length
        ? `${res.data.length} local report(s).`
        : "No reports yet. Be the first to share an update.",
    );
  }

  useEffect(() => {
    load();
  }, []);

  async function submit() {
    if (!area.trim() || !message.trim()) return;

    if (file) {
      const form = new FormData();
      form.append("area", area.trim());
      form.append("message", message.trim());
      form.append("file", file);
      const res = await apiUpload<Report>("/api/reports", form);
      if (!res.ok) {
        alert("Could not submit your report. Please try again.");
        return;
      }
    } else {
      const res = await apiCall<Report>("/api/reports", {
        method: "POST",
        body: JSON.stringify({ area, message }),
      });
      if (!res.ok) {
        alert("Could not submit your report. Please try again.");
        return;
      }
    }

    setArea("");
    setMessage("");
    setFile(null);
    await load();
  }

  return (
    <div>
      <h1 className="text-xl font-semibold sm:text-2xl">{t("reports.title")}</h1>
      <p className="mt-1 text-sm text-slate-400">{status}</p>
      <p className="mt-1 text-xs text-slate-500">{t("reports.unverified")}</p>

      <div className="glass-card mt-4 p-4">
        <div className="mono-tag mb-3">{t("reports.share")}</div>
        <div className="grid gap-3 md:grid-cols-2">
          <input
            value={area}
            onChange={(e) => setArea(e.target.value)}
            placeholder="Area (for example, Tarnaka)"
            className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
          />
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="What is happening here?"
            className="min-h-[44px] w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm md:min-h-[44px]"
          />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <label className="text-sm text-slate-400">
            Optional photo or document
            <input
              type="file"
              accept="image/*,.txt,.md,.pdf"
              className="mt-1 block w-full text-sm"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <button className="btn btn-primary px-4 py-2 text-sm" onClick={submit}>
            Submit report
          </button>
        </div>
      </div>

      <div className="glass-card mt-4 divide-y divide-white/10 p-3">
        {reports.map((r) => (
          <div key={r.id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
            <span className="hidden text-xl sm:block" aria-hidden>
              👥
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <b>{r.area}</b>
                <span className="text-xs text-amber-300">Unverified</span>
                {isStale(r.created_at) && (
                  <span className="text-xs text-slate-500">May be stale (over 24h)</span>
                )}
              </div>
              <p className="mt-1 text-sm text-slate-200">{r.message}</p>
              {r.attachment_url && r.attachment_mime?.startsWith("image/") && (
                <img
                  src={r.attachment_url}
                  alt={`Report from ${r.area}`}
                  className="mt-2 max-h-40 rounded-lg border border-[var(--border)] object-cover"
                />
              )}
              {r.attachment_url && !r.attachment_mime?.startsWith("image/") && (
                <a
                  href={r.attachment_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-block text-sm text-[var(--accent-soft)] underline"
                >
                  View attached file
                </a>
              )}
              <span className="mono-tag mt-2 inline-block normal-case">
                {timeAgo(r.created_at)}
              </span>
            </div>
            {r.lat != null && r.lon != null && (
              <PlaceMapThumb lat={r.lat} lon={r.lon} label={r.area} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
