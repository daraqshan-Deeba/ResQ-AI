"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { InfoAssistantDrawer } from "@/components/InfoAssistantDrawer";
import { SosConfirmModal } from "@/components/SosConfirmModal";
import { useAppLanguage } from "@/components/AppLanguageProvider";

export function DashboardFloatingActions() {
  const pathname = usePathname();
  const onGetHelp = pathname?.startsWith("/dashboard/assessment");
  const { t } = useAppLanguage();
  const [chatOpen, setChatOpen] = useState(false);
  const [sosOpen, setSosOpen] = useState(false);

  return (
    <>
      <div className="fixed bottom-6 right-6 z-30 hidden flex-col items-end gap-3 md:flex">
        {!onGetHelp && (
          <button
            type="button"
            onClick={() => setChatOpen(true)}
            className="flex min-h-11 items-center gap-2 rounded-full border border-cyan-400/30 bg-slate-900/95 px-4 py-2.5 text-sm font-medium text-cyan-100 shadow-lg shadow-cyan-500/20 backdrop-blur"
            aria-label={t("chat")}
          >
            <span aria-hidden>🤖</span>
            {t("chat")}
          </button>
        )}
        <button
          type="button"
          onClick={() => setSosOpen(true)}
          className="btn btn-danger min-h-11 px-5 py-2.5 shadow-lg shadow-red-500/30"
          aria-label={t("sos.confirmTitle")}
        >
          {t("sos")}
        </button>
      </div>

      <InfoAssistantDrawer open={chatOpen} onClose={() => setChatOpen(false)} />
      <SosConfirmModal open={sosOpen} onClose={() => setSosOpen(false)} />
    </>
  );
}
