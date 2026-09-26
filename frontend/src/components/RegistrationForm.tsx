"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PhoneInput } from "@/components/PhoneInput";
import { createClient } from "@/lib/supabase/client";
import { useAppLanguage } from "@/components/AppLanguageProvider";
import {
  buildE164,
  DEFAULT_PHONE_DIAL,
  parseStoredPhone,
  validatePhone,
} from "@/lib/phone";
import type { UserProfile } from "@/lib/types";
import type { UiCopyKey } from "@/lib/ui-copy";

const RELATION_PRESETS = [
  "son",
  "daughter",
  "spouse",
  "father",
  "mother",
  "brother",
  "sister",
  "friend",
  "caregiver",
] as const;

function splitRelation(value: string | null | undefined): {
  preset: string;
  custom: string;
} {
  const raw = (value ?? "").trim();
  if (!raw) return { preset: "", custom: "" };
  if ((RELATION_PRESETS as readonly string[]).includes(raw)) {
    return { preset: raw, custom: "" };
  }
  return { preset: "other", custom: raw };
}

export function RegistrationForm({
  redirectTo = "/dashboard",
  submitLabel,
}: {
  redirectTo?: string | null;
  submitLabel?: string;
}) {
  const router = useRouter();
  const { t } = useAppLanguage();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [profile, setProfile] = useState<UserProfile | null>(null);

  const [fullName, setFullName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [phoneDial, setPhoneDial] = useState(DEFAULT_PHONE_DIAL);
  const [phoneNational, setPhoneNational] = useState("");
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [city, setCity] = useState("Hyderabad");
  const [emergencyName, setEmergencyName] = useState("");
  const [emergencyDial, setEmergencyDial] = useState(DEFAULT_PHONE_DIAL);
  const [emergencyNational, setEmergencyNational] = useState("");
  const [emergencyPhoneError, setEmergencyPhoneError] = useState<string | null>(null);
  const [relationPreset, setRelationPreset] = useState("");
  const [relationCustom, setRelationCustom] = useState("");
  const [relationError, setRelationError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (!user) {
        router.replace("/login");
        return;
      }

      let row = (
        await supabase.from("profiles").select("*").eq("id", user.id).maybeSingle()
      ).data as UserProfile | null;

      if (!row) {
        const meta = user.user_metadata ?? {};
        const seed = {
          id: user.id,
          email: user.email ?? "",
          full_name: meta.full_name ?? meta.name ?? "",
          display_name: meta.name ?? meta.full_name ?? "",
          avatar_url: meta.avatar_url ?? meta.picture ?? null,
          registration_complete: false,
        };
        await supabase.from("profiles").upsert(seed);
        row = {
          ...seed,
          phone: null,
          phone_country_dial: DEFAULT_PHONE_DIAL,
          phone_national: null,
          city: "Hyderabad",
          emergency_contact_name: null,
          emergency_contact_phone: null,
          emergency_contact_country_dial: DEFAULT_PHONE_DIAL,
          emergency_contact_national: null,
          emergency_contact_relation: null,
          created_at: "",
          updated_at: "",
        };
      }

      const phone = parseStoredPhone(
        row.phone,
        row.phone_country_dial,
        row.phone_national,
      );
      const emergency = parseStoredPhone(
        row.emergency_contact_phone,
        row.emergency_contact_country_dial,
        row.emergency_contact_national,
      );

      setProfile(row);
      setFullName(row.full_name ?? "");
      setDisplayName(row.display_name ?? row.full_name ?? "");
      setPhoneDial(phone.dial);
      setPhoneNational(phone.national);
      setCity(row.city ?? "Hyderabad");
      setEmergencyName(row.emergency_contact_name ?? "");
      setEmergencyDial(emergency.dial);
      setEmergencyNational(emergency.national);
      const relation = splitRelation(row.emergency_contact_relation);
      setRelationPreset(relation.preset);
      setRelationCustom(relation.custom);
      setLoading(false);
    }

    load();
  }, [router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!profile) return;

    const phoneValidation = validatePhone(phoneDial, phoneNational);
    const emergencyValidation =
      emergencyNational.trim() === ""
        ? null
        : validatePhone(emergencyDial, emergencyNational);

    const phoneE164 = buildE164(phoneDial, phoneNational);
    const emergencyE164 = emergencyNational.trim()
      ? buildE164(emergencyDial, emergencyNational)
      : null;
    const relationValue =
      relationPreset === "other"
        ? relationCustom.trim()
        : relationPreset.trim();

    setPhoneError(phoneValidation);
    setEmergencyPhoneError(emergencyValidation);
    setRelationError(
      emergencyE164 && !relationValue ? t("settings.relationError") : null,
    );

    if (
      !fullName.trim() ||
      !city.trim() ||
      phoneValidation ||
      emergencyValidation ||
      (emergencyE164 && !relationValue)
    ) {
      setError(t("settings.fixFields"));
      return;
    }

    if (!phoneE164) {
      setPhoneError(t("settings.phoneInvalid"));
      return;
    }

    setSaving(true);
    setError(null);
    setSaved(false);
    const supabase = createClient();

    const { error: updateError } = await supabase
      .from("profiles")
      .update({
        full_name: fullName.trim(),
        display_name: displayName.trim() || fullName.trim(),
        phone: phoneE164,
        phone_country_dial: phoneDial,
        phone_national: phoneNational,
        city: city.trim(),
        emergency_contact_name: emergencyName.trim() || null,
        emergency_contact_phone: emergencyE164,
        emergency_contact_country_dial: emergencyNational.trim() ? emergencyDial : null,
        emergency_contact_national: emergencyNational.trim() || null,
        emergency_contact_relation: emergencyE164 ? relationValue : null,
        registration_complete: true,
        updated_at: new Date().toISOString(),
      })
      .eq("id", profile.id);

    setSaving(false);
    if (updateError) {
      setError(updateError.message);
      return;
    }

    if (redirectTo) {
      router.replace(redirectTo);
      router.refresh();
    } else {
      setSaved(true);
    }
  }

  if (loading) {
    return <p className="text-sm text-slate-400">{t("settings.loading")}</p>;
  }

  const fieldClass =
    "mt-1 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2";

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="rounded-xl border border-amber-400/35 bg-amber-500/[0.07] p-3">
        <p className="text-sm font-medium text-amber-100">{t("settings.emergencyTag")}</p>
        <p className="mt-1 text-xs leading-relaxed text-slate-400">
          {t("settings.emergencyHelp")}
        </p>
        <label className="mt-3 block text-sm">
          <span className="text-slate-300">{t("settings.contactName")}</span>
          <input
            value={emergencyName}
            onChange={(e) => setEmergencyName(e.target.value)}
            className={fieldClass}
          />
        </label>
        <div className="mt-3">
          <PhoneInput
            label={t("settings.contactPhone")}
            dial={emergencyDial}
            national={emergencyNational}
            onDialChange={setEmergencyDial}
            onNationalChange={setEmergencyNational}
            error={emergencyPhoneError}
          />
        </div>
        <label className="mt-3 block text-sm">
          <span className="text-slate-300">{t("settings.relation")}</span>
          <select
            value={relationPreset}
            onChange={(e) => setRelationPreset(e.target.value)}
            className={fieldClass}
          >
            <option value="">{t("settings.relationSelect")}</option>
            {RELATION_PRESETS.map((value) => (
              <option key={value} value={value}>
                {t(`settings.rel.${value}` as UiCopyKey)}
              </option>
            ))}
            <option value="other">{t("settings.relationOther")}</option>
          </select>
        </label>
        {relationPreset === "other" && (
          <label className="mt-3 block text-sm">
            <span className="text-slate-300">{t("settings.relationCustom")}</span>
            <input
              value={relationCustom}
              onChange={(e) => setRelationCustom(e.target.value)}
              placeholder={t("settings.relationHint")}
              className={fieldClass}
            />
          </label>
        )}
        {relationError && (
          <p className="mt-2 text-sm text-[var(--danger-soft)]">{relationError}</p>
        )}
      </div>

      <div className="flex items-center gap-3">
        {profile?.avatar_url && (
          <img
            src={profile.avatar_url}
            alt=""
            className="h-12 w-12 shrink-0 rounded-full border border-[var(--border)]"
          />
        )}
        <label className="min-w-0 flex-1 text-sm">
          <span className="text-slate-400">{t("settings.email")}</span>
          <input
            value={profile?.email ?? ""}
            readOnly
            className="mt-1 w-full rounded-xl border border-[var(--border)] bg-white/5 px-3 py-2 text-slate-400"
          />
        </label>
      </div>

      <label className="block text-sm">
        <span className="text-slate-300">{t("settings.fullName")} *</span>
        <input
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          required
          className={fieldClass}
        />
      </label>

      <label className="block text-sm">
        <span className="text-slate-300">{t("settings.displayName")}</span>
        <input
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          className={fieldClass}
        />
      </label>

      <PhoneInput
        label={t("settings.phone")}
        dial={phoneDial}
        national={phoneNational}
        onDialChange={setPhoneDial}
        onNationalChange={setPhoneNational}
        required
        error={phoneError}
      />

      <label className="block text-sm">
        <span className="text-slate-300">{t("settings.city")} *</span>
        <input
          value={city}
          onChange={(e) => setCity(e.target.value)}
          required
          className={fieldClass}
        />
      </label>

      {error && <p className="text-sm text-[var(--danger-soft)]">{error}</p>}
      {saved && !error && (
        <p className="text-sm text-emerald-300">{t("settings.saved")}</p>
      )}

      <button type="submit" className="btn btn-primary w-full" disabled={saving}>
        {saving ? t("settings.saving") : submitLabel ?? t("settings.saveContinue")}
      </button>
    </form>
  );
}
