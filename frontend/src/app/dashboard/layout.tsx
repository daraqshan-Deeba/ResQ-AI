import Link from "next/link";
import { DashboardSidebar } from "@/components/DashboardSidebar";

export default function DashboardLayout({ children }: LayoutProps<"/dashboard">) {
  return (
    <div className="flex min-h-screen">
      <DashboardSidebar />
      <div className="flex min-h-screen flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3 md:hidden">
          <Link href="/" className="font-semibold">
            📡 ResQ AI
          </Link>
          <Link href="/dashboard/sos" className="btn btn-danger px-3 py-2 text-xs">
            SOS
          </Link>
        </div>
        <main className="flex-1 p-4 md:p-8">{children}</main>
        <Link
          href="/dashboard/sos"
          className="fixed bottom-6 right-6 btn btn-danger shadow-lg md:hidden"
        >
          🚨 SOS
        </Link>
      </div>
    </div>
  );
}
