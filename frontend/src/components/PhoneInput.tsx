"use client";

import {
  COUNTRY_PHONE_CODES,
  DEFAULT_PHONE_DIAL,
  digitsOnly,
} from "@/lib/phone";

type PhoneInputProps = {
  label: string;
  dial: string;
  national: string;
  onDialChange: (dial: string) => void;
  onNationalChange: (national: string) => void;
  required?: boolean;
  error?: string | null;
};

export function PhoneInput({
  label,
  dial,
  national,
  onDialChange,
  onNationalChange,
  required = false,
  error,
}: PhoneInputProps) {
  const selected =
    COUNTRY_PHONE_CODES.find((c) => c.dial === dial) ??
    COUNTRY_PHONE_CODES.find((c) => c.dial === DEFAULT_PHONE_DIAL)!;

  return (
    <label className="block text-sm">
      <span className="text-slate-300">
        {label}
        {required ? " *" : ""}
      </span>
      <div className="mt-1 flex gap-2">
        <select
          value={dial}
          onChange={(e) => onDialChange(e.target.value)}
          className="w-[9.5rem] shrink-0 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-2 py-2 text-sm"
          aria-label={`${label} country code`}
        >
          {COUNTRY_PHONE_CODES.map((country) => (
            <option key={country.code} value={country.dial}>
              {country.dial} {country.code}
            </option>
          ))}
        </select>
        <input
          value={national}
          onChange={(e) => onNationalChange(digitsOnly(e.target.value))}
          type="tel"
          inputMode="numeric"
          autoComplete="tel-national"
          placeholder={`${selected.nationalLength} digits`}
          required={required}
          maxLength={15}
          className="min-w-0 flex-1 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
        />
      </div>
      <span className="mt-1 block text-xs text-slate-500">{selected.label}</span>
      {error && <span className="mt-1 block text-xs text-[var(--danger-soft)]">{error}</span>}
    </label>
  );
}
