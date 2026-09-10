import Link from "next/link";
import { RegistrationForm } from "@/components/RegistrationForm";

export default function RegisterPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-12">
      <div className="glass-card w-full max-w-lg p-8">
        <Link href="/" className="text-xl font-semibold">
          📡 ResQ<span className="text-[var(--accent)]">AI</span>
        </Link>
        <h1 className="mt-6 text-2xl font-semibold">Complete your profile</h1>
        <div className="mt-6">
          <RegistrationForm />
        </div>
      </div>
    </main>
  );
}
