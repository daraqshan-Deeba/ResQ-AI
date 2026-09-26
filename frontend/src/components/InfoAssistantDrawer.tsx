"use client";

import { useEffect, useId } from "react";
import { ChatWidget } from "@/components/ChatWidget";
import { useAppLanguage } from "@/components/AppLanguageProvider";

type InfoAssistantDrawerProps = {
  open: boolean;
  onClose: () => void;
};

export function InfoAssistantDrawer({ open, onClose }: InfoAssistantDrawerProps) {
  const { t } = useAppLanguage();
  const titleId = useId();

  useEffect(() => {
    if (!open) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    document.addEventListener("keydown", onKeyDown);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/50"
        onClick={onClose}
        aria-hidden
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-[var(--border)] bg-[var(--surface)] shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
          <div>
            <h2 id={titleId} className="text-sm font-semibold text-white">
              {t("chat")}
            </h2>
            <p className="text-xs text-slate-400">
              {t("chat.subtitle")}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-slate-300 hover:bg-white/5 hover:text-white"
            aria-label={t("chat.close")}
          >
            ✕
          </button>
        </div>

        <div className="border-b border-amber-500/20 bg-amber-500/10 px-4 py-2 text-xs text-amber-100">
          {t("chat.danger")}
        </div>

        <div className="min-h-0 flex-1 p-4">
          <ChatWidget compact />
        </div>
      </aside>
    </>
  );
}
