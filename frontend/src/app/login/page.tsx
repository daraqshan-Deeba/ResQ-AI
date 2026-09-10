import Link from "next/link";
import { GoogleSignInButton } from "@/components/GoogleSignInButton";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const params = await searchParams;

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="glass-card w-full max-w-md p-8">
        <Link href="/" className="text-xl font-semibold">
          📡 ResQ<span className="text-[var(--accent)]">AI</span>
        </Link>
        <h1 className="mt-6 text-2xl font-semibold">Sign in</h1>
        <p className="mt-2 text-sm text-slate-400">
          Use your Google account. New users will review their profile before registering.
        </p>

        {params.error === "auth" && (
          <p className="mt-4 text-sm text-[var(--danger-soft)]">
            Sign-in failed. Check that Google is enabled in Supabase Auth.
          </p>
        )}

        <div className="mt-8">
          <GoogleSignInButton />
        </div>

        <p className="mt-6 text-center text-xs text-slate-500">
          By continuing you agree to use ResQ AI for emergency awareness. Always call 112
          for life-threatening emergencies.
        </p>
      </div>
    </main>
  );
}
