"use client";

import Link from "next/link";
import { useState } from "react";
import { DashboardSidebar } from "@/components/DashboardSidebar";
import { DashboardFloatingActions } from "@/components/DashboardFloatingActions";
import { SosConfirmModal } from "@/components/SosConfirmModal";

export default function DashboardLayout({ children }: LayoutProps<"/dashboard">) {
  const [sosOpen, setSosOpen] = useState(false);

  return (
    <div className="flex min-h-screen">
      <DashboardSidebar />
      <div className="flex min-h-screen flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3 md:hidden">
          <Link href="/" className="font-semibold">
            📡 ResQ AI
          </Link>
          <button
            type="button"
            onClick={() => setSosOpen(true)}
            className="btn btn-danger px-3 py-2 text-xs"
          >
            SOS
          </button>
        </div>
        <main className="flex-1 p-4 pb-28 md:p-8 md:pb-28">{children}</main>
        <DashboardFloatingActions />
        <SosConfirmModal open={sosOpen} onClose={() => setSosOpen(false)} />
      </div>
    </div>
  );
}
