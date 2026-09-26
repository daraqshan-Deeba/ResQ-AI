"use client";

import { DashboardLocationPanel } from "@/components/DashboardLocationPanel";
import { useAppLanguage } from "@/components/AppLanguageProvider";

export default function DashboardOverviewPage() {
  const { t } = useAppLanguage();
  return (
    <div>
      <div className="mb-3">
        <h1 className="text-xl font-semibold sm:text-2xl">{t("home.title")}</h1>
        <p className="text-sm text-slate-400">{t("home.subtitle")}</p>
      </div>

      <DashboardLocationPanel />
    </div>
  );
}
