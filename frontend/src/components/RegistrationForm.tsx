"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PhoneInput } from "@/components/PhoneInput";
import { createClient } from "@/lib/supabase/client";
import {
  buildE164,
  DEFAULT_PHONE_DIAL,
  parseStoredPhone,
  validatePhone,
} from "@/lib/phone";
import type { UserProfile } from "@/lib/types";

export function RegistrationForm() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
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

    setPhoneError(phoneValidation);
    setEmergencyPhoneError(emergencyValidation);

    if (!fullName.trim() || !city.trim() || phoneValidation || emergencyValidation) {
      setError("Please fix the highlighted fields before continuing.");
      return;
    }

    const phoneE164 = buildE164(phoneDial, phoneNational);
    const emergencyE164 = emergencyNational.trim()
      ? buildE164(emergencyDial, emergencyNational)
      : null;

    if (!phoneE164) {
      setPhoneError("Enter a valid phone number.");
      return;
    }

    setSaving(true);
    setError(null);
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
        registration_complete: true,
        updated_at: new Date().toISOString(),
      })
      .eq("id", profile.id);

    setSaving(false);
    if (updateError) {
      setError(updateError.message);
      return;
    }

    router.replace("/dashboard");
    router.refresh();
  }

  if (loading) {
    return <p className="text-sm text-slate-400">Loading your profile...</p>;
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="text-sm text-slate-400">
        Please review your details and complete the form to continue.
      </p>

      {profile?.avatar_url && (
        <img
          src={profile.avatar_url}
          alt="Profile"
          className="h-16 w-16 rounded-full border border-[var(--border)]"
        />
      )}

      <label className="block text-sm">
        <span className="text-slate-400">Email</span>
        <input
          value={profile?.email ?? ""}
          readOnly
          className="mt-1 w-full rounded-xl border border-[var(--border)] bg-white/5 px-3 py-2 text-slate-400"
        />
      </label>

      <label className="block text-sm">
        <span className="text-slate-300">Full name *</span>
        <input
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          required
          className="mt-1 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
        />
      </label>

      <label className="block text-sm">
        <span className="text-slate-300">Display name</span>
        <input
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          className="mt-1 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
        />
      </label>

      <PhoneInput
        label="Phone number"
        dial={phoneDial}
        national={phoneNational}
        onDialChange={setPhoneDial}
        onNationalChange={setPhoneNational}
        required
        error={phoneError}
      />

      <label className="block text-sm">
        <span className="text-slate-300">City / area *</span>
        <input
          value={city}
          onChange={(e) => setCity(e.target.value)}
          required
          className="mt-1 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
        />
      </label>

      <div className="rounded-xl border border-[var(--border)] bg-white/5 p-4">
        <div className="mono-tag mb-3">Emergency contact (optional)</div>
        <label className="block text-sm">
          <span className="text-slate-300">Contact name</span>
          <input
            value={emergencyName}
            onChange={(e) => setEmergencyName(e.target.value)}
            className="mt-1 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
          />
        </label>
        <div className="mt-3">
          <PhoneInput
            label="Contact phone"
            dial={emergencyDial}
            national={emergencyNational}
            onDialChange={setEmergencyDial}
            onNationalChange={setEmergencyNational}
            error={emergencyPhoneError}
          />
        </div>
      </div>

      {error && <p className="text-sm text-[var(--danger-soft)]">{error}</p>}

      <button type="submit" className="btn btn-primary w-full" disabled={saving}>
        {saving ? "Saving..." : "Save and continue"}
      </button>
    </form>
  );
}
