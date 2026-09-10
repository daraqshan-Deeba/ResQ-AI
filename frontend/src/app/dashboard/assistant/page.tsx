import Link from "next/link";
import { ChatWidget } from "@/components/ChatWidget";

export default function AssistantPage() {
  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold">General Information Assistant</h1>
      <p className="mt-2 text-sm text-slate-400">
        This chat is for non-urgent questions only. It does not run the emergency
        orchestrator, triage, or weather risk pipeline.
      </p>
      <div className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
        For urgent or life-threatening situations, use{" "}
        <Link href="/dashboard/assessment" className="font-medium underline">
          Emergency Assessment
        </Link>{" "}
        or call 112 / 108 immediately.
      </div>
      <div className="glass-card mt-6 min-h-[60vh] p-6">
        <ChatWidget />
      </div>
    </div>
  );
}
