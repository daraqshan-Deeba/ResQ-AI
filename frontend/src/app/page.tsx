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
            Report an emergency
          </Link>
        </nav>
      </header>

      <section className="relative overflow-hidden px-6 py-24">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(37,99,235,0.25),transparent_55%)]" />
        <div className="relative mx-auto max-w-4xl text-center">
          <div className="mono-tag mb-4">Hyderabad and nearby areas</div>
          <h1 className="text-4xl font-bold leading-tight md:text-6xl">
            Clear guidance when
            <br />
            <span className="text-gradient">you need help fast</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-slate-300">
            Check weather risk near you, find hospitals and shelters, read local
            reports, and get step by step guidance during an emergency.
          </p>
          <div className="mt-10 flex flex-wrap justify-center gap-4">
            <Link href="/login" className="btn btn-primary">
              Get started
            </Link>
            <Link href="/dashboard/assessment" className="btn btn-outline">
              Ask for help now
            </Link>
          </div>
        </div>
      </section>

      <section id="features" className="mx-auto max-w-6xl px-6 py-16">
        <h2 className="text-3xl font-semibold">What you can do</h2>
        <div className="mt-8 grid gap-6 md:grid-cols-3">
          {[
            ["🚨", "Get help", "Describe what is happening and receive clear next steps."],
            ["🌦️", "Weather risk", "See rainfall and flood risk for your current location."],
            ["🏥", "Hospitals nearby", "Find health facilities close to you with map directions."],
            ["👥", "Local reports", "Read and share updates from people in your area."],
            ["🆘", "SOS alert", "Share your location only after you confirm."],
            ["💬", "Ask a question", "Use Chat for general safety questions that are not urgent."],
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
          <h2 className="text-3xl font-semibold">How it works</h2>
          <p className="mt-4 text-slate-300">
            Sign in, share your location if you choose, describe the situation,
            and review guidance, weather, and nearby help in one place. For a
            life threatening emergency, call 112 or 108 first.
          </p>
        </div>
      </section>
    </main>
  );
}
