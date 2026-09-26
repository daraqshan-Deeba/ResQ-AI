"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  DEFAULT_LANGUAGE,
  languageByName,
  normalizeLanguage,
  readStoredLanguage,
  storeLanguage,
} from "@/lib/languages";
import { translate, type UiCopyKey } from "@/lib/ui-copy";

type LanguageContextValue = {
  language: string;
  setLanguage: (name: string) => void;
  t: (key: UiCopyKey) => string;
  dir: "ltr" | "rtl";
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function AppLanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState(DEFAULT_LANGUAGE);

  useEffect(() => {
    setLanguageState(readStoredLanguage());
  }, []);

  useEffect(() => {
    const meta = languageByName(language);
    document.documentElement.lang = meta.code === "hi-Latn" ? "hi" : meta.code;
    document.documentElement.dir = meta.dir;
  }, [language]);

  const value = useMemo<LanguageContextValue>(() => {
    const meta = languageByName(language);
    return {
      language,
      dir: meta.dir,
      setLanguage: (name: string) => {
        setLanguageState(storeLanguage(name));
      },
      t: (key: UiCopyKey) => translate(language, key),
    };
  }, [language]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useAppLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    return {
      language: DEFAULT_LANGUAGE,
      setLanguage: (_name: string) => {},
      t: (key: UiCopyKey) => translate(DEFAULT_LANGUAGE, key),
      dir: "ltr" as const,
    };
  }
  return ctx;
}
