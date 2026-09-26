const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

async function authHeaders(): Promise<Record<string, string>> {
  try {
    const { createClient } = await import("@/lib/supabase/client");
    const { getSupabaseEnv } = await import("@/lib/supabase/env");
    if (!getSupabaseEnv()) return {};
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

export async function apiCall<T>(
  path: string,
  options: RequestInit = {},
): Promise<ApiResult<T>> {
  try {
    const extra = await authHeaders();
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...extra,
        ...(options.headers ?? {}),
      },
    });

    if (!res.ok) {
      let detail = "Something went wrong. Please try again.";
      try {
        const body = (await res.json()) as { detail?: string };
        if (typeof body?.detail === "string" && body.detail.trim()) {
          detail = body.detail;
        }
      } catch {
        /* keep default */
      }
      return { ok: false, error: detail };
    }

    return { ok: true, data: (await res.json()) as T };
  } catch {
    return {
      ok: false,
      error: "Could not connect right now. Please try again in a moment.",
    };
  }
}

export async function apiUpload<T>(
  path: string,
  formData: FormData,
): Promise<ApiResult<T>> {
  try {
    const extra = await authHeaders();
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      body: formData,
      headers: extra,
    });

    if (!res.ok) {
      return {
        ok: false,
        error: "Something went wrong. Please try again.",
      };
    }

    return { ok: true, data: (await res.json()) as T };
  } catch {
    return {
      ok: false,
      error: "Could not connect right now. Please try again in a moment.",
    };
  }
}

export { API_BASE };
