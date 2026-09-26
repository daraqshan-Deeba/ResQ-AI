"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAppLanguage } from "@/components/AppLanguageProvider";
import type { UiCopyKey } from "@/lib/ui-copy";

const items: { href: string; key: UiCopyKey; icon: string; exact: boolean }[] = [
  { href: "/dashboard", key: "nav.home", icon: "🏠", exact: true },
  { href: "/dashboard/assessment", key: "nav.help", icon: "📋", exact: false },
  { href: "/dashboard/hospitals", key: "nav.hospitals", icon: "➕", exact: false },
  { href: "/dashboard/reports", key: "nav.reports", icon: "👥", exact: false },
];

export function DashboardBottomNav() {
  const pathname = usePathname();
  const { t } = useAppLanguage();

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 border-t border-[var(--border)] bg-[var(--surface)]/95 backdrop-blur md:hidden"
      style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}
      aria-label="Main"
    >
      <ul className="grid grid-cols-4">
        {items.map((item) => {
          const active = item.exact
            ? pathname === item.href
            : pathname.startsWith(item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={`flex min-h-12 flex-col items-center justify-center gap-0.5 px-1 py-2 text-center text-[11px] leading-tight ${
                  active ? "text-white" : "text-slate-400"
                }`}
              >
                <span className="text-base" aria-hidden>
                  {item.icon}
                </span>
                {t(item.key)}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
