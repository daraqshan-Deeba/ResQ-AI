"use client";

import { useEffect, useId } from "react";
import { ChatWidget } from "@/components/ChatWidget";

type InfoAssistantDrawerProps = {
  open: boolean;
  onClose: () => void;
};

export function InfoAssistantDrawer({ open, onClose }: InfoAssistantDrawerProps) {
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

  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-black/50 transition-opacity duration-200 ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        onClick={onClose}
        aria-hidden={!open}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-hidden={!open}
        className={`fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-[var(--border)] bg-[var(--surface)] shadow-2xl transition-transform duration-300 ease-out ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
          <div>
            <h2 id={titleId} className="text-sm font-semibold text-white">
              Chat
            </h2>
            <p className="text-xs text-slate-400">
              For general questions. Not for urgent emergencies.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-slate-300 hover:bg-white/5 hover:text-white"
            aria-label="Close chat"
          >
            ✕
          </button>
        </div>

        <div className="border-b border-amber-500/20 bg-amber-500/10 px-4 py-2 text-xs text-amber-100">
          If someone is in danger, use Get help or call 112 / 108.
        </div>

        <div className="min-h-0 flex-1 p-4">
          <ChatWidget compact />
        </div>
      </aside>
    </>
  );
}
