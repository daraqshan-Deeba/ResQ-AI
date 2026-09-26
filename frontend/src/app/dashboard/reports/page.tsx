"use client";

import { useEffect, useState } from "react";
import { apiCall, apiUpload } from "@/lib/api";
import type { Report } from "@/lib/types";

function timeAgo(iso: string) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  return `${Math.round(mins / 60)} hr ago`;
}

export default function ReportsPage() {
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
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-semibold">Local reports</h1>
      <p className="mt-2 text-sm text-slate-400">{status}</p>

      <div className="glass-card mt-6 p-5">
        <div className="mono-tag mb-3">Share an update</div>
        <input
          value={area}
          onChange={(e) => setArea(e.target.value)}
          placeholder="Area (for example, Tarnaka)"
          className="mb-3 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
        />
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="What is happening here?"
          className="min-h-[80px] w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
        />
        <label className="mt-3 block text-sm text-slate-400">
          Optional photo or document
          <input
            type="file"
            accept="image/*,.txt,.md,.pdf"
            className="mt-2 block w-full text-sm"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <button className="btn btn-primary mt-3 px-4 py-2 text-sm" onClick={submit}>
          Submit report
        </button>
      </div>

      <div className="mt-8 space-y-4">
        {reports.map((r) => (
          <div key={r.id} className="glass-card flex gap-4 p-5">
            <span className="text-xl">👥</span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <b>{r.area}</b>
                {r.verified ? (
                  <span className="text-xs text-[var(--accent-soft)]">Checked</span>
                ) : (
                  <span className="text-xs text-amber-300">Unverified</span>
                )}
              </div>
              <p className="mt-1 text-sm">{r.message}</p>
              {r.attachment_url && r.attachment_mime?.startsWith("image/") && (
                <img
                  src={r.attachment_url}
                  alt={`Report from ${r.area}`}
                  className="mt-3 max-h-56 rounded-xl border border-[var(--border)] object-cover"
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
          </div>
        ))}
      </div>
    </div>
  );
}
