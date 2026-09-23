"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { DashboardUserMenu } from "@/components/DashboardUserMenu";

const navItems = [
  { href: "/dashboard", label: "Home", icon: "🏠" },
  { href: "/dashboard/assessment", label: "Get help", icon: "📋" },
  { href: "/dashboard/hospitals", label: "Hospitals", icon: "➕" },
  { href: "/dashboard/shelters", label: "Shelters", icon: "🏘️" },
  { href: "/dashboard/reports", label: "Local reports", icon: "👥" },
  { href: "/dashboard/settings", label: "Settings", icon: "⚙️" },
];

export function DashboardSidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)] p-6 md:flex">
      <Link href="/" className="mb-8 text-xl font-semibold">
        📡 ResQ<span className="text-[var(--accent)]">AI</span>
      </Link>
      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto">
        {navItems.map((item) => {
          const active =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`rounded-xl px-3 py-2.5 text-sm transition ${
                active
                  ? "bg-blue-600/20 text-white"
                  : "text-slate-300 hover:bg-white/5"
              }`}
            >
              {item.icon} {item.label}
            </Link>
          );
        })}
      </nav>
      <DashboardUserMenu />
    </aside>
  );
}
