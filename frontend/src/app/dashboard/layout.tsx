"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { DashboardSidebar } from "@/components/DashboardSidebar";
import { DashboardFloatingActions } from "@/components/DashboardFloatingActions";
import { DashboardBottomNav } from "@/components/DashboardBottomNav";
import { InfoAssistantDrawer } from "@/components/InfoAssistantDrawer";
import { SosConfirmModal } from "@/components/SosConfirmModal";
import { useAppLanguage } from "@/components/AppLanguageProvider";
import { LanguageSelect } from "@/components/LanguageSelect";

export default function DashboardLayout({ children }: LayoutProps<"/dashboard">) {
  const pathname = usePathname();
  const onGetHelp = pathname?.startsWith("/dashboard/assessment");
  const { t, language, setLanguage } = useAppLanguage();
  const [sosOpen, setSosOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <div className="flex min-h-screen">
      <DashboardSidebar />
      <div className="flex min-h-screen flex-1 flex-col">
        <div className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2 md:hidden">
          <Link href="/" className="font-semibold">
            📡 ResQ AI
          </Link>
          <div className="flex min-w-0 items-center gap-2">
            <LanguageSelect
              value={language}
              onChange={setLanguage}
              className="max-w-[7.5rem] rounded-lg border border-[var(--border)] bg-[var(--surface)] px-1 py-1 text-[11px] text-slate-200"
            />
            {!onGetHelp && (
              <button
                type="button"
                onClick={() => setChatOpen(true)}
                className="min-h-11 rounded-full border border-cyan-400/30 px-3 text-xs text-cyan-100"
                aria-label={t("chat")}
              >
                {t("chat")}
              </button>
            )}
            <button
              type="button"
              onClick={() => setSosOpen(true)}
              className="btn btn-danger min-h-11 px-3 py-2 text-xs"
            >
              {t("sos")}
            </button>
          </div>
        </div>
        <main className="flex-1 p-3 pb-24 md:p-6 md:pb-8">{children}</main>
        <DashboardBottomNav />
        <DashboardFloatingActions />
        <InfoAssistantDrawer open={chatOpen} onClose={() => setChatOpen(false)} />
        <SosConfirmModal open={sosOpen} onClose={() => setSosOpen(false)} />
      </div>
    </div>
  );
}
