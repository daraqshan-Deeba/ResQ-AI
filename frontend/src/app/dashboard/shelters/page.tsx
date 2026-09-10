"use client";

import { useEffect, useState } from "react";
import { apiCall } from "@/lib/api";
import type { Shelter } from "@/lib/types";

export default function SheltersPage() {
  const [shelters, setShelters] = useState<Shelter[]>([]);
  const [status, setStatus] = useState("Loading…");

  useEffect(() => {
    (async () => {
      const res = await apiCall<Shelter[]>("/api/shelters");
      if (!res.ok) {
        setStatus(res.error);
        return;
      }
      setShelters(res.data);
      setStatus("From Firestore — manually maintained occupancy.");
    })();
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold">Nearby Shelters</h1>
      <p className="mt-2 text-sm text-slate-400">{status}</p>
      <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {shelters.map((s) => {
          const pct = s.capacity ? Math.round((s.occupied / s.capacity) * 100) : 0;
          return (
            <div key={s.id} className="glass-card p-5">
              <div className="text-lg font-medium">🏘️ {s.name}</div>
              <p className="mt-2 text-sm">{s.occupied} / {s.capacity} occupied</p>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-[var(--accent)] to-[var(--primary)]"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
