"use client";

import { useState } from "react";
import { InfoAssistantDrawer } from "@/components/InfoAssistantDrawer";
import { SosConfirmModal } from "@/components/SosConfirmModal";

export function DashboardFloatingActions() {
  const [chatOpen, setChatOpen] = useState(false);
  const [sosOpen, setSosOpen] = useState(false);

  return (
    <>
      <div className="fixed bottom-6 right-6 z-30 flex flex-col items-end gap-3">
        <button
          type="button"
          onClick={() => setChatOpen(true)}
          className="flex items-center gap-2 rounded-full border border-cyan-400/30 bg-slate-900/95 px-4 py-3 text-sm font-medium text-cyan-100 shadow-lg shadow-cyan-500/20 backdrop-blur transition hover:border-cyan-300/50 hover:bg-slate-800"
          aria-label="Open info assistant chat"
        >
          <span aria-hidden>🤖</span>
          Chat
        </button>
        <button
          type="button"
          onClick={() => setSosOpen(true)}
          className="btn btn-danger shadow-lg shadow-red-500/30"
          aria-label="Open SOS confirmation"
        >
          🚨 SOS
        </button>
      </div>

      <InfoAssistantDrawer open={chatOpen} onClose={() => setChatOpen(false)} />
      <SosConfirmModal open={sosOpen} onClose={() => setSosOpen(false)} />
    </>
  );
}
