"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import type { UserProfile } from "@/lib/types";
import { useAppLanguage } from "@/components/AppLanguageProvider";

export function DashboardUserMenu() {
  const router = useRouter();
  const { t } = useAppLanguage();
  const [profile, setProfile] = useState<UserProfile | null>(null);

  useEffect(() => {
    async function load() {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user) return;
      const { data } = await supabase
        .from("profiles")
        .select("display_name, full_name, email, avatar_url")
        .eq("id", user.id)
        .maybeSingle();
      setProfile(data as UserProfile | null);
    }
    load();
  }, []);

  async function signOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.replace("/login");
    router.refresh();
  }

  if (!profile) return null;

  return (
    <div className="mt-auto border-t border-[var(--border)] pt-4">
      <div className="flex items-center gap-3 px-2">
        {profile.avatar_url ? (
          <img src={profile.avatar_url} alt="" className="h-9 w-9 rounded-full" />
        ) : (
          <span className="text-lg">👤</span>
        )}
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">
            {profile.display_name || profile.full_name}
          </div>
          <div className="truncate text-xs text-slate-500">{profile.email}</div>
        </div>
      </div>
      <button
        type="button"
        onClick={signOut}
        className="mt-3 w-full rounded-xl px-3 py-2 text-left text-sm text-slate-400 hover:bg-white/5"
      >
        {t("signOut")}
      </button>
    </div>
  );
}
