"use client";

import { useState } from "react";
import { RegistrationForm } from "@/components/RegistrationForm";
import { apiCall } from "@/lib/api";
import { isFirebaseWebConfigured, requestFcmToken } from "@/lib/firebase";
import { LanguageSelect } from "@/components/LanguageSelect";
import { useAppLanguage } from "@/components/AppLanguageProvider";

export default function SettingsPage() {
  const { language, setLanguage, t } = useAppLanguage();
  const [status, setStatus] = useState("");

  async function enableAlerts() {
    if (!isFirebaseWebConfigured()) {
      setStatus(t("settings.alertsPartial"));
      return;
    }

    if (!("Notification" in window)) {
      setStatus(t("settings.alertsUnsupported"));
      return;
    }

    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      setStatus(t("settings.alertsDenied"));
      return;
    }

    if (!isFirebaseWebConfigured()) {
      setStatus(t("settings.alertsPartial"));
      return;
    }

    try {
      const token = await requestFcmToken();
      if (!token) {
        setStatus(t("settings.alertsRetry"));
        return;
      }

      const res = await apiCall<{ status: string }>("/api/device-token", {
        method: "POST",
        body: JSON.stringify({ token }),
      });

      setStatus(res.ok ? t("settings.alertsOk") : t("settings.alertsFail"));
    } catch {
      setStatus(t("settings.alertsError"));
    }
  }

  return (
    <div className="max-w-md space-y-4 md:pb-4">
      <div>
        <h1 className="text-2xl font-semibold">{t("settings.title")}</h1>
        <p className="mt-1 text-sm text-slate-400">{t("settings.intro")}</p>
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <p className="mb-2 text-sm font-medium text-slate-200">{t("language.label")}</p>
        <p className="mb-2 text-xs text-slate-400">{t("language.help")}</p>
        <LanguageSelect
          value={language}
          onChange={setLanguage}
          className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-slate-200"
        />
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <p className="mb-3 text-sm font-medium text-slate-200">{t("settings.review")}</p>
        <RegistrationForm redirectTo={null} submitLabel={t("settings.save")} />
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <p className="text-sm font-medium text-slate-200">{t("settings.alertsTitle")}</p>
        <p className="mt-1 text-xs leading-relaxed text-slate-400">{t("settings.alertsBody")}</p>
        <button type="button" className="btn btn-primary mt-3 w-full" onClick={enableAlerts}>
          {t("settings.alertsButton")}
        </button>
        {status && <p className="mt-3 text-sm text-slate-300">{status}</p>}
      </div>
    </div>
  );
}
