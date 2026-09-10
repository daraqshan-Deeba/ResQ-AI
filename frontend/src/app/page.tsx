import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-[var(--border)] bg-[var(--bg)]/80 backdrop-blur">
        <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="text-xl font-semibold">
            📡 ResQ<span className="text-[var(--accent)]">AI</span>
          </Link>
          <div className="hidden items-center gap-6 text-sm text-slate-300 md:flex">
            <a href="#features">Features</a>
            <a href="#how">How it works</a>
            <Link href="/login" className="text-[var(--accent-soft)]">
              Sign in
            </Link>
          </div>
          <Link href="/dashboard/assessment" className="btn btn-primary px-4 py-2 text-sm">
            Report Emergency
          </Link>
        </nav>
      </header>

      <section className="relative overflow-hidden px-6 py-24">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(37,99,235,0.25),transparent_55%)]" />
        <div className="relative mx-auto max-w-4xl text-center">
          <div className="mono-tag mb-4">Live monsoon monitoring · Hyderabad region</div>
          <h1 className="text-4xl font-bold leading-tight md:text-6xl">
            When the water rises,
            <br />
            <span className="text-gradient">ResQ AI</span> tells you where to go.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-slate-300">
            A coordinated emergency response platform with live weather risk,
            AI-guided assessments, nearby resources, community reports, and SOS
            location capture — powered by a Flask backend and Next.js frontend.
          </p>
          <div className="mt-10 flex flex-wrap justify-center gap-4">
            <Link href="/login" className="btn btn-primary">
              Get started →
            </Link>
            <Link href="/dashboard/assessment" className="btn btn-outline">
              Emergency assessment
            </Link>
          </div>
        </div>
      </section>

      <section id="features" className="mx-auto max-w-6xl px-6 py-16">
        <h2 className="text-3xl font-semibold">What it does</h2>
        <div className="mt-8 grid gap-6 md:grid-cols-3">
          {[
            ["🚨", "Emergency Assessment", "Tiered triage, weather risk, and structured action plans via the orchestrator."],
            ["🌦️", "Live Weather Risk", "OpenWeather-driven risk scoring with transparent contributing factors."],
            ["🏥", "Nearby Resources", "Hospitals from Firebase and shelters from Supabase."],
            ["👥", "Community Reports", "Ground-truth incident reports with verification status."],
            ["🆘", "SOS Capture", "Explicit user-confirmed location sharing with durable event logging."],
            ["🤖", "Info Assistant", "General safety Q&A — urgent cases use Emergency Assessment."],
          ].map(([icon, title, body]) => (
            <div key={title} className="glass-card p-6">
              <div className="text-2xl">{icon}</div>
              <h3 className="mt-4 text-lg font-medium">{title}</h3>
              <p className="mt-2 text-sm text-slate-400">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="how" className="border-t border-[var(--border)] px-6 py-16">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-3xl font-semibold">How it connects</h2>
          <p className="mt-4 text-slate-300">
            The Next.js app calls the Flask API at{" "}
            <code className="rounded bg-white/5 px-2 py-1 text-sm">
              {process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"}
            </code>
            . The Emergency Orchestrator on the backend assembles triage,
            weather, action planning, confidence, and optional hospital lookup
            into one unified response.
          </p>
        </div>
      </section>
    </main>
  );
}
