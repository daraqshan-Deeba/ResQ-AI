export type CountryPhoneCode = {
  code: string;
  dial: string;
  label: string;
  nationalLength: number;
};

/** Dial codes sorted longest-first for parsing numbers that include + prefix. */
export const COUNTRY_PHONE_CODES: CountryPhoneCode[] = [
  { code: "IN", dial: "+91", label: "India", nationalLength: 10 },
  { code: "US", dial: "+1", label: "United States", nationalLength: 10 },
  { code: "GB", dial: "+44", label: "United Kingdom", nationalLength: 10 },
  { code: "AE", dial: "+971", label: "United Arab Emirates", nationalLength: 9 },
  { code: "AU", dial: "+61", label: "Australia", nationalLength: 9 },
  { code: "CA", dial: "+1", label: "Canada", nationalLength: 10 },
  { code: "SG", dial: "+65", label: "Singapore", nationalLength: 8 },
  { code: "DE", dial: "+49", label: "Germany", nationalLength: 10 },
  { code: "FR", dial: "+33", label: "France", nationalLength: 9 },
  { code: "BD", dial: "+880", label: "Bangladesh", nationalLength: 10 },
  { code: "LK", dial: "+94", label: "Sri Lanka", nationalLength: 9 },
  { code: "NP", dial: "+977", label: "Nepal", nationalLength: 10 },
  { code: "PK", dial: "+92", label: "Pakistan", nationalLength: 10 },
];

const DIAL_SORTED = [...COUNTRY_PHONE_CODES].sort(
  (a, b) => b.dial.length - a.dial.length,
);

export const DEFAULT_PHONE_DIAL = "+91";

export type ParsedPhone = {
  dial: string;
  national: string;
  e164: string;
};

export function digitsOnly(value: string): string {
  return value.replace(/\D/g, "");
}

export function findCountryByDial(dial: string): CountryPhoneCode | undefined {
  return COUNTRY_PHONE_CODES.find((c) => c.dial === dial);
}

export function parseStoredPhone(
  e164: string | null | undefined,
  dial?: string | null,
  national?: string | null,
): ParsedPhone {
  if (dial && national) {
    const cleanNational = digitsOnly(national);
    const built = buildE164(dial, cleanNational);
    if (built) {
      return { dial, national: cleanNational, e164: built };
    }
  }

  if (!e164?.trim()) {
    return { dial: DEFAULT_PHONE_DIAL, national: "", e164: "" };
  }

  const raw = e164.trim();
  if (raw.startsWith("+")) {
    for (const country of DIAL_SORTED) {
      if (raw.startsWith(country.dial)) {
        const rest = digitsOnly(raw.slice(country.dial.length));
        const built = buildE164(country.dial, rest);
        if (built) {
          return { dial: country.dial, national: rest, e164: built };
        }
      }
    }
  }

  let digits = digitsOnly(raw);
  if (digits.length === 12 && digits.startsWith("91")) {
    digits = digits.slice(2);
    const built = buildE164("+91", digits);
    if (built) return { dial: "+91", national: digits, e164: built };
  }
  if (digits.length === 11 && digits.startsWith("0")) {
    digits = digits.slice(1);
  }

  const built = buildE164(DEFAULT_PHONE_DIAL, digits);
  return {
    dial: DEFAULT_PHONE_DIAL,
    national: digits,
    e164: built ?? "",
  };
}

export function buildE164(dial: string, nationalDigits: string): string | null {
  const national = digitsOnly(nationalDigits);
  if (!national) return null;
  if (!/^\+\d{1,3}$/.test(dial)) return null;
  const e164 = `${dial}${national}`;
  if (!/^\+[1-9]\d{6,14}$/.test(e164)) return null;
  return e164;
}

export function validatePhone(dial: string, nationalDigits: string): string | null {
  const national = digitsOnly(nationalDigits);
  if (!national) return "Phone number is required.";
  if (!/^\+\d{1,3}$/.test(dial)) return "Select a valid country code.";

  const country = findCountryByDial(dial);
  if (country && national.length !== country.nationalLength) {
    return `${country.label} numbers must be ${country.nationalLength} digits.`;
  }

  if (national.length < 7 || national.length > 15) {
    return "Enter a valid phone number (7 to 15 digits).";
  }

  if (!buildE164(dial, national)) {
    return "Enter a valid international phone number.";
  }

  return null;
}

export function formatPhoneDisplay(
  e164: string | null | undefined,
  dial?: string | null,
  national?: string | null,
): string {
  const parsed = parseStoredPhone(e164, dial, national);
  if (!parsed.national) return "";
  return `${parsed.dial} ${parsed.national}`;
}

/** RFC 3966 dialer URI. Short codes like 112 stay local; other numbers keep digits and a leading +. */
export function toTelHref(phone: string): string {
  const raw = phone.trim();
  if (/^(112|108|100|101|102)$/.test(raw)) {
    return `tel:${raw}`;
  }
  const cleaned = raw.replace(/[^\d+]/g, "");
  if (!cleaned) return "";
  return `tel:${cleaned}`;
}

export function extractDialNumber(text: string): string | null {
  const trimmed = text.trim();
  const short = trimmed.match(/\b(112|108|100|101|102)\b/);
  if (short) return short[1];
  const e164 = trimmed.match(/\+[1-9]\d{6,14}/);
  if (e164) return e164[0];
  const digits = trimmed.match(/(\d{3,})/);
  return digits ? digits[1] : null;
}

export function openPhoneDialer(phone: string) {
  const href = toTelHref(phone);
  if (!href) return;
  window.location.href = href;
}
