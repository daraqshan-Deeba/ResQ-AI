export type AppLanguage = {
  name: string;
  code: string;
  native: string;
  dir: "ltr" | "rtl";
};

/** Keep in sync with backend/app/i18n/languages.py */
export const GROQ_SMALL_MULTILINGUAL_MODEL = "openai/gpt-oss-20b";

export const SUPPORTED_LANGUAGES: AppLanguage[] = [
  { name: "English", code: "en", native: "English", dir: "ltr" },
  { name: "Hindi", code: "hi", native: "हिन्दी", dir: "ltr" },
  { name: "Hinglish", code: "hi-Latn", native: "Hinglish", dir: "ltr" },
  { name: "Telugu", code: "te", native: "తెలుగు", dir: "ltr" },
  { name: "Urdu", code: "ur", native: "اردو", dir: "rtl" },
];

export const DEFAULT_LANGUAGE = "English";

const STORAGE_KEY = "resq-app-language";

export function languageByName(name: string): AppLanguage {
  return (
    SUPPORTED_LANGUAGES.find((item) => item.name.toLowerCase() === name.toLowerCase()) ??
    SUPPORTED_LANGUAGES[0]
  );
}

export function normalizeLanguage(value: string | null | undefined): string {
  if (!value?.trim()) return DEFAULT_LANGUAGE;
  const raw = value.trim().toLowerCase();
  const aliases: Record<string, string> = {
    en: "English",
    hi: "Hindi",
    hin: "Hindi",
    "hi-latn": "Hinglish",
    hinglish: "Hinglish",
    "hi-en": "Hinglish",
    te: "Telugu",
    ur: "Urdu",
  };
  if (aliases[raw]) return aliases[raw];
  const match = SUPPORTED_LANGUAGES.find((item) => item.name.toLowerCase() === raw);
  return match?.name ?? DEFAULT_LANGUAGE;
}

export function readStoredLanguage(): string {
  if (typeof window === "undefined") return DEFAULT_LANGUAGE;
  return normalizeLanguage(window.localStorage.getItem(STORAGE_KEY));
}

export function storeLanguage(name: string) {
  const normalized = normalizeLanguage(name);
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, normalized);
  }
  return normalized;
}

export function languageGroups() {
  return { india: SUPPORTED_LANGUAGES, international: [] as AppLanguage[] };
}
