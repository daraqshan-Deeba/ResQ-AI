import { createClient } from "@supabase/supabase-js";
import { getSupabaseEnv } from "@/lib/supabase/env";

export type KeepaliveCheck = {
  ok: boolean;
  configured: boolean;
  detail?: string | null;
  latency_ms?: number;
  shelters_count?: number | null;
  routes?: Record<string, number>;
};

export type KeepaliveReport = {
  status: "ok" | "degraded" | "error";
  triggered_at: string;
  schedule: string | null;
  checks: {
    frontend: KeepaliveCheck;
    supabase: KeepaliveCheck;
    backend: KeepaliveCheck;
  };
};

function appBaseUrl(): string | null {
  const explicit =
    process.env.NEXT_PUBLIC_APP_URL?.trim() ||
    process.env.KEEPALIVE_APP_URL?.trim() ||
    "";
  if (explicit) {
    return explicit.replace(/\/$/, "");
  }

  const production = process.env.VERCEL_PROJECT_PRODUCTION_URL?.trim();
  if (production) {
    return `https://${production.replace(/^https?:\/\//, "")}`;
  }

  const deployment = process.env.VERCEL_URL?.trim();
  if (deployment) {
    return `https://${deployment.replace(/^https?:\/\//, "")}`;
  }

  return null;
}

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

/** Warm the Next.js app routes so visitors avoid cold starts. */
export async function pingFrontend(): Promise<KeepaliveCheck> {
  const base = appBaseUrl();
  if (!base) {
    return {
      ok: false,
      configured: false,
      detail: "NEXT_PUBLIC_APP_URL / VERCEL_URL not set",
    };
  }

  const paths = ["/api/health", "/"];
  const routes: Record<string, number> = {};

  try {
    const { latency_ms } = await timed(async () => {
      for (const path of paths) {
        const started = Date.now();
        const response = await fetch(`${base}${path}`, {
          method: "GET",
          cache: "no-store",
          redirect: "follow",
          signal: AbortSignal.timeout(15_000),
          headers: { "User-Agent": "ResQ-Keepalive/1.0" },
        });
        routes[path] = Date.now() - started;
        if (!response.ok && response.status >= 500) {
          throw new Error(`${path} returned ${response.status}`);
        }
        // Drain body so the connection is fully used
        await response.arrayBuffer().catch(() => undefined);
      }
    });

    return { ok: true, configured: true, latency_ms, routes };
  } catch (error) {
    return {
      ok: false,
      configured: true,
      detail: error instanceof Error ? error.message : "frontend warm failed",
      routes,
    };
  }
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
        throw new Error(`${response.status} ${response.statusText}${body ? ` - ${body}` : ""}`);
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
  const [frontend, supabase, backend] = await Promise.all([
    pingFrontend(),
    pingSupabase(),
    pingBackend(),
  ]);

  const configured = [frontend, supabase, backend].filter((check) => check.configured);
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
    checks: { frontend, supabase, backend },
  };
}
