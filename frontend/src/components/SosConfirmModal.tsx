"use client";

import { useEffect, useId, useState } from "react";
import { apiCall } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import type { SosResponse } from "@/lib/types";
import { useAppLanguage } from "@/components/AppLanguageProvider";
import { CallNumberButton } from "@/components/CallNumberButton";

type SosConfirmModalProps = {
  open: boolean;
  onClose: () => void;
  situation?: string;
};

export function SosConfirmModal({ open, onClose, situation }: SosConfirmModalProps) {
  const { t } = useAppLanguage();
  const titleId = useId();
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [contactPhone, setContactPhone] = useState<string | null>(null);
  const [contactName, setContactName] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setStatus("");
      setLoading(false);
      setContactPhone(null);
      setContactName(null);
      return;
    }

    let cancelled = false;
    async function loadContact() {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user || cancelled) return;
      const { data } = await supabase
        .from("profiles")
        .select("emergency_contact_phone,emergency_contact_name,emergency_contact_relation")
        .eq("id", user.id)
        .maybeSingle();
      if (cancelled || !data) return;
      setContactPhone(data.emergency_contact_phone ?? null);
      setContactName(data.emergency_contact_name ?? null);
    }
    void loadContact();

    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      cancelled = true;
      document.body.style.overflow = previous;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !loading) onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose, loading]);

  async function sendSos(lat?: number, lon?: number) {
    setLoading(true);
    const body: Record<string, unknown> = {
      situation: situation || undefined,
      idempotency_key: `web-${Date.now()}`,
    };
    if (lat != null && lon != null) {
      body.lat = lat;
      body.lon = lon;
    }
    const res = await apiCall<SosResponse>("/api/sos", {
      method: "POST",
      body: JSON.stringify(body),
    });
    setLoading(false);
    if (res.ok) {
      setContactPhone(res.data.emergency_contact_phone ?? contactPhone);
      setStatus(res.data.message);
      return;
    }
    setStatus(`Could not send SOS. ${res.error} Call 112 if you are in danger.`);
  }

  function confirmSos() {
    if (!navigator.geolocation) {
      setStatus("Location is not available in this browser. Recording SOS without a map pin.");
      void sendSos();
      return;
    }
    setLoading(true);
    setStatus("Getting your location...");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setStatus("Sending SOS...");
        void sendSos(position.coords.latitude, position.coords.longitude);
      },
      () => {
        setStatus("Location was denied. Recording SOS without a map pin. Call 112.");
        void sendSos();
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    );
  }

  if (!open) return null;

  const contactLabel = contactName
    ? `Call ${contactName}`
    : "Call emergency contact";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/60"
        onClick={() => {
          if (!loading) onClose();
        }}
        aria-hidden
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative z-10 w-full max-w-md rounded-2xl border border-red-500/30 bg-[var(--surface)] p-6 shadow-2xl shadow-red-900/30"
      >
        <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-[var(--danger)] text-2xl shadow-[0_0_40px_rgba(239,68,68,0.35)]">
          🚨
        </div>
        <h2 id={titleId} className="text-center text-xl font-semibold text-white">
          {t("sos.confirmTitle")}
        </h2>
        <p className="mt-3 text-center text-sm text-slate-400">
          {t("sos.confirmBody")}
        </p>
        <div className="mt-4 flex flex-col gap-2">
          <CallNumberButton
            phone="112"
            label={t("sos.call112")}
            className="btn btn-danger w-full min-h-11"
          />
          {contactPhone && (
            <CallNumberButton
              phone={contactPhone}
              label={`${contactLabel} ${contactPhone}`}
              className="btn w-full min-h-11 border border-amber-400/40 bg-amber-500/10 text-amber-100 hover:bg-amber-500/20"
            />
          )}
        </div>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row-reverse">
          <button
            type="button"
            className="btn btn-danger flex-1"
            onClick={confirmSos}
            disabled={loading}
          >
            {loading ? t("sos.sending") : t("sos.confirm")}
          </button>
          <button
            type="button"
            className="btn flex-1 border border-[var(--border)] bg-white/5 text-slate-200 hover:bg-white/10"
            onClick={onClose}
            disabled={loading}
          >
            {t("sos.cancel")}
          </button>
        </div>

        {status && (
          <p className="mt-4 text-center text-sm text-slate-300" role="status">
            {status}
          </p>
        )}
      </div>
    </div>
  );
}
