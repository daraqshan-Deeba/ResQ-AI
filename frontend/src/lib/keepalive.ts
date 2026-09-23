import { createClient } from "@supabase/supabase-js";
import { getSupabaseEnv } from "@/lib/supabase/env";

export type KeepaliveCheck = {
  ok: boolean;
  configured: boolean;
  detail?: string | null;
  latency_ms?: number;
  shelters_count?: number | null;
};

export type KeepaliveReport = {
  status: "ok" | "degraded" | "error";
  triggered_at: string;
  schedule: string | null;
  checks: {
    supabase: KeepaliveCheck;
    backend: KeepaliveCheck;
  };
};

function supabaseAdminConfig() {
  const url =
    process.env.SUPABASE_URL?.trim() ||
    process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() ||
    "";
  const key =
    process.env.SUPABASE_SERVICE_ROLE_KEY?.trim() ||
    process.env.SUPABASE_SECRET_KEY?.trim() ||
    "";

  if (!url || !key) {
    return null;
  }

  return { url, key };
}

async function timed<T>(fn: () => Promise<T>): Promise<{ result: T; latency_ms: number }> {
  const started = Date.now();
  const result = await fn();
  return { result, latency_ms: Date.now() - started };
}

export async function pingSupabase(): Promise<KeepaliveCheck> {
  const admin = supabaseAdminConfig();
  const publicEnv = getSupabaseEnv();

  if (!admin && !publicEnv) {
    return { ok: false, configured: false, detail: "supabase env not set" };
  }

  const { url, key } = admin ?? { url: publicEnv!.url, key: publicEnv!.anonKey };

  try {
    const { result, latency_ms } = await timed(async () => {
      const client = createClient(url, key, { auth: { persistSession: false } });
      const { count, error } = await client
        .from("shelters")
        .select("id", { count: "exact", head: true });

      if (error) {
        throw new Error(error.message);
      }

      return count;
    });

    return {
      ok: true,
      configured: true,
      latency_ms,
      shelters_count: result,
    };
  } catch (error) {
    return {
      ok: false,
      configured: true,
      detail: error instanceof Error ? error.message : "supabase ping failed",
    };
  }
}

export async function pingBackend(): Promise<KeepaliveCheck> {
  const apiBase = process.env.NEXT_PUBLIC_API_URL?.trim();
  const secret = process.env.KEEPALIVE_SECRET?.trim() || process.env.CRON_SECRET?.trim();

  if (!apiBase) {
    return { ok: false, configured: false, detail: "NEXT_PUBLIC_API_URL not set" };
  }

  if (!secret) {
    return { ok: false, configured: false, detail: "KEEPALIVE_SECRET / CRON_SECRET not set" };
  }

  try {
    const { latency_ms } = await timed(async () => {
      const response = await fetch(`${apiBase}/api/cron/keepalive`, {
        method: "GET",
        headers: { Authorization: `Bearer ${secret}` },
        cache: "no-store",
        signal: AbortSignal.timeout(25_000),
      });

      if (!response.ok) {
        const body = await response.text().catch(() => "");
        throw new Error(`${response.status} ${response.statusText}${body ? ` — ${body}` : ""}`);
      }

      await response.json();
    });

    return { ok: true, configured: true, latency_ms };
  } catch (error) {
    return {
      ok: false,
      configured: true,
      detail: error instanceof Error ? error.message : "backend ping failed",
    };
  }
}

export async function runKeepalive(schedule: string | null): Promise<KeepaliveReport> {
  const [supabase, backend] = await Promise.all([pingSupabase(), pingBackend()]);

  const configured = [supabase, backend].filter((check) => check.configured);
  const healthy = configured.filter((check) => check.ok);
  const status =
    configured.length === 0
      ? "error"
      : healthy.length === configured.length
        ? "ok"
        : "degraded";

  return {
    status,
    triggered_at: new Date().toISOString(),
    schedule,
    checks: { supabase, backend },
  };
}
