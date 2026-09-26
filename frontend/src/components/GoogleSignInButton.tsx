"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

export function GoogleSignInButton({ label = "Continue with Google" }: { label?: string }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function signIn() {
    setLoading(true);
    setError(null);

    if (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY) {
      setError(
        "Sign in is not available right now. Please try again later.",
      );
      setLoading(false);
      return;
    }

    const supabase = createClient();
    const { error: authError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback`,
        scopes: "openid email profile",
        queryParams: {
          access_type: "offline",
          prompt: "select_account",
        },
      },
    });
    if (authError) {
      setError(authError.message);
      setLoading(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        className="btn btn-primary w-full"
        onClick={signIn}
        disabled={loading}
      >
        {loading ? "Please wait..." : `🔐 ${label}`}
      </button>
      {error && <p className="mt-3 text-sm text-[var(--danger-soft)]">{error}</p>}
    </div>
  );
}
