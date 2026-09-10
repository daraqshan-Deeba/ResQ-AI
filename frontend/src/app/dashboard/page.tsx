"use client";

import Link from "next/link";
import { ChatWidget } from "@/components/ChatWidget";
import { DashboardLocationPanel } from "@/components/DashboardLocationPanel";

export default function DashboardOverviewPage() {
  return (
    <div>
      <div className="mb-8 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Emergency Overview</h1>
          <p className="text-sm text-slate-400">
            Live location, weather, and traffic near you
          </p>
        </div>
      </div>

      <DashboardLocationPanel />

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="glass-card p-6 lg:col-span-2">
          <div className="mono-tag mb-4">Quick Actions</div>
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              ["/dashboard/assessment", "📋", "New Assessment"],
              ["/dashboard/hospitals", "➕", "Find Hospital"],
              ["/dashboard/shelters", "🏘️", "Find Shelter"],
              ["/dashboard/reports", "👥", "Report Issue"],
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
        </div>
        <div className="glass-card p-6">
          <ChatWidget compact />
        </div>
      </div>
    </div>
  );
}
