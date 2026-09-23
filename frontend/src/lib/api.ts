const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001";

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

export async function apiCall<T>(
  path: string,
  options: RequestInit = {},
): Promise<ApiResult<T>> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
      ...options,
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

export async function apiUpload<T>(
  path: string,
  formData: FormData,
): Promise<ApiResult<T>> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      body: formData,
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
