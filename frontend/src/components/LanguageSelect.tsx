"use client";

import { SUPPORTED_LANGUAGES } from "@/lib/languages";

export function LanguageSelect({
  id,
  value,
  onChange,
  className = "",
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <select
      id={id}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className={
        className ||
        "rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-slate-200"
      }
    >
      {SUPPORTED_LANGUAGES.map((item) => (
        <option key={item.code} value={item.name}>
          {item.native} ({item.name})
        </option>
      ))}
    </select>
  );
}
