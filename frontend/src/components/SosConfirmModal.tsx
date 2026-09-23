"use client";

import { useEffect, useId, useState } from "react";
import { apiCall } from "@/lib/api";
import type { SosResponse } from "@/lib/types";

type SosConfirmModalProps = {
  open: boolean;
  onClose: () => void;
};

export function SosConfirmModal({ open, onClose }: SosConfirmModalProps) {
  const titleId = useId();
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) {
      setStatus("");
      setLoading(false);
      return;
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !loading) onClose();
    }

    document.addEventListener("keydown", onKeyDown);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previous;
    };
  }, [open, onClose, loading]);

  function confirmSos() {
    if (!navigator.geolocation) {
      setStatus("Location is not available in this browser.");
      return;
    }
    setLoading(true);
    setStatus("Getting your location...");
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        setStatus("Sending SOS...");
        const res = await apiCall<SosResponse>("/api/sos", {
          method: "POST",
          body: JSON.stringify({
            lat: position.coords.latitude,
            lon: position.coords.longitude,
          }),
        });
        setLoading(false);
        setStatus(res.ok ? res.data.message : `Could not send SOS. ${res.error}`);
      },
      () => {
        setLoading(false);
        setStatus("Could not get your location. Check browser permissions.");
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 },
    );
  }

  if (!open) return null;

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
          Confirm SOS
        </h2>
        <p className="mt-3 text-center text-sm text-slate-400">
          This sends an emergency alert with your current location. Your
          location is shared only after you confirm.
        </p>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row-reverse">
          <button
            type="button"
            className="btn btn-danger flex-1"
            onClick={confirmSos}
            disabled={loading}
          >
            {loading ? "Sending..." : "Confirm SOS"}
          </button>
          <button
            type="button"
            className="btn flex-1 border border-[var(--border)] bg-white/5 text-slate-200 hover:bg-white/10"
            onClick={onClose}
            disabled={loading}
          >
            Cancel
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
