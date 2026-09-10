"use client";

import { useEffect, useState } from "react";
import { apiCall } from "@/lib/api";

type Message = { role: "user" | "assistant"; text: string };

const SESSION_KEY = "resq-chat-session-id";

function getOrCreateSessionId(): string {
  if (typeof window === "undefined") return "server-session";
  const existing = window.localStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const id =
    typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `session-${Date.now()}`;
  window.localStorage.setItem(SESSION_KEY, id);
  return id;
}

const initialMessages: Message[] = [
  {
    role: "assistant",
    text:
      "Hi — I'm the general information assistant. I can answer basic monsoon-safety questions, but I am not the primary emergency system. For urgent situations, open Emergency Assessment or call 112 / 108.",
  },
];

export function ChatWidget({ compact = false }: { compact?: boolean }) {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [sessionId, setSessionId] = useState("");

  useEffect(() => {
    setSessionId(getOrCreateSessionId());
  }, []);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;

    const history = messages.map((m) => ({ role: m.role, text: m.text }));
    const next = [...messages, { role: "user" as const, text }];
    setMessages([...next, { role: "assistant", text: "…" }]);
    setInput("");
    setSending(true);

    const result = await apiCall<{ reply: string; session_id?: string }>("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        history,
        message: text,
        session_id: sessionId || getOrCreateSessionId(),
        actor_id: "resq-web-user",
      }),
    });

    setMessages((prev) => {
      const withoutPlaceholder = prev.slice(0, -1);
      return [
        ...withoutPlaceholder,
        {
          role: "assistant",
          text: result.ok ? result.data.reply : `⚠️ ${result.error}`,
        },
      ];
    });
    setSending(false);
  }

  return (
    <div className={`flex h-full flex-col ${compact ? "" : "min-h-[420px]"}`}>
      <div className="mb-4 flex items-center gap-2">
        <span className="text-xl">🤖</span>
        <div>
          <div className="text-sm font-medium">Info Assistant</div>
          <div className="mono-tag normal-case">Not for urgent emergencies</div>
        </div>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto pr-1">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex gap-2 ${m.role === "user" ? "justify-end" : ""}`}
          >
            {m.role === "assistant" && <span>🤖</span>}
            <div
              className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                m.role === "user"
                  ? "bg-blue-600/30 text-white"
                  : "bg-white/5 text-slate-200"
              }`}
            >
              {m.text}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask a general safety question…"
          className="flex-1 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-white outline-none"
        />
        <button className="btn btn-primary px-4 py-2" onClick={send} disabled={sending}>
          ➤
        </button>
      </div>
    </div>
  );
}
