"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { DashboardUserMenu } from "@/components/DashboardUserMenu";
import { LanguageSelect } from "@/components/LanguageSelect";
import { useAppLanguage } from "@/components/AppLanguageProvider";
import type { UiCopyKey } from "@/lib/ui-copy";

const navItems: { href: string; key: UiCopyKey; icon: string }[] = [
  { href: "/dashboard", key: "nav.home", icon: "🏠" },
  { href: "/dashboard/assessment", key: "nav.help", icon: "📋" },
  { href: "/dashboard/hospitals", key: "nav.hospitals", icon: "➕" },
  { href: "/dashboard/shelters", key: "nav.shelters", icon: "🏘️" },
  { href: "/dashboard/reports", key: "nav.reports", icon: "👥" },
  { href: "/dashboard/settings", key: "nav.settings", icon: "⚙️" },
];

export function DashboardSidebar() {
  const pathname = usePathname();
  const { language, setLanguage, t } = useAppLanguage();

  return (
    <aside className="hidden w-56 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--surface)] p-4 md:flex">
      <Link href="/" className="mb-5 text-lg font-semibold">
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
              className={`rounded-lg px-3 py-2 text-sm transition ${
                active
                  ? "bg-blue-600/20 text-white"
                  : "text-slate-300 hover:bg-white/5"
              }`}
            >
              {item.icon} {t(item.key)}
            </Link>
          );
        })}
      </nav>
      <label className="mb-2 block text-[11px] text-slate-500" htmlFor="sidebar-language">
        {t("language.label")}
      </label>
      <LanguageSelect
        id="sidebar-language"
        value={language}
        onChange={setLanguage}
        className="mb-3 w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-xs text-slate-200"
      />
      <DashboardUserMenu />
    </aside>
  );
}
