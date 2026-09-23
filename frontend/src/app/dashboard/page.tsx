"use client";

import Link from "next/link";
import { DashboardLocationPanel } from "@/components/DashboardLocationPanel";

export default function DashboardOverviewPage() {
  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-semibold">Home</h1>
        <p className="text-sm text-slate-400">
          Your location, weather, and road updates nearby
        </p>
      </div>

      <DashboardLocationPanel />

      <div className="mt-6 glass-card p-6">
        <div className="mono-tag mb-4">Quick actions</div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["/dashboard/assessment", "📋", "Get help"],
            ["/dashboard/hospitals", "➕", "Find a hospital"],
            ["/dashboard/shelters", "🏘️", "Find a shelter"],
            ["/dashboard/reports", "👥", "Share a report"],
          ].map(([href, icon, label]) => (
            <Link
              key={href}
              href={href}
              className="rounded-xl border border-[var(--border)] bg-white/5 px-4 py-3 text-sm hover:border-blue-500/40"
            >
              {icon} {label}
            </Link>
          ))}
        </div>
        <p className="mt-4 text-xs text-slate-500">
          For non urgent questions, tap Chat above the SOS button.
        </p>
      </div>
    </div>
  );
}
