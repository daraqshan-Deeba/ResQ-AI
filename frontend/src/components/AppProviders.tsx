"use client";

import { AppLanguageProvider } from "@/components/AppLanguageProvider";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return <AppLanguageProvider>{children}</AppLanguageProvider>;
}
