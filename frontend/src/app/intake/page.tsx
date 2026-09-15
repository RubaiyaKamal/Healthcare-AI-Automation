"use client";

import { useEffect, useRef, useState } from "react";

type ChatMsg = { role: "user" | "assistant"; content: string };
type ToolCall = { tool: string; args: unknown };

type IntakeOutput = {
  output: string;
  tool_calls: ToolCall[];
  trace_id: string;
};

const SUGGESTIONS = [
  "Register a new patient: Maria Lopez, DOB 1985-04-12, phone 555-0102",
  "New walk-in: James Miller, DOB 1972-11-03",
  "Check the duplicate-first workflow",
];

export default function IntakePage() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastToolCalls, setLastToolCalls] = useState<ToolCall[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, lastToolCalls]);

  async function send(userText: string) {
    if (!userText.trim() || busy) return;
    const next: ChatMsg[] = [...messages, { role: "user", content: userText }];
    setMessages(next);
    setInput("");
    setBusy(true);
    setLastToolCalls([]);

    try {
      const res = await fetch("/api/intake", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: next,
          actor: "frontend-demo",
        }),
      });
      const data: IntakeOutput = await res.json();
      setMessages((m) => [...m, { role: "assistant", content: data.output }]);
      setLastToolCalls(data.tool_calls ?? []);
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `Error calling intake agent: ${e instanceof Error ? e.message : String(e)}`,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col px-4 py-6">
      <header className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-brand-black">Patient Intake Agent</h1>
          <p className="text-sm text-brand-muted">
            Duplicate check enforced before registration. Synthetic data only.
          </p>
        </div>
        <a href="/" className="text-sm font-semibold text-brand-brown hover:underline">
          ← Home
        </a>
      </header>

      <div className="flex flex-1 flex-col gap-2 overflow-y-auto rounded-xl border border-brand-line bg-white p-4">
        {messages.length === 0 && (
          <div className="mb-2">
            <p className="mb-3 text-sm text-brand-muted">
              The front-desk agent will walk you through registration. Try:
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-brand-line bg-brand-yellowSoft px-3 py-1 text-xs text-brand-brownDark transition hover:bg-brand-yellowLight"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
              m.role === "user"
                ? "self-end bg-brand-yellow text-brand-ink"
                : "self-start border border-brand-line bg-white text-brand-brownDark"
            }`}
            style={{ whiteSpace: "pre-wrap" }}
          >
            {m.content}
          </div>
        ))}

        {busy && (
          <div className="self-start rounded-lg border border-brand-line bg-white px-3 py-2 text-sm text-brand-muted">
            <span className="mr-1 inline-block h-2 w-2 animate-pulse rounded-full bg-brand-brown" />
            Running agent tools…
          </div>
        )}

        {lastToolCalls.length > 0 && (
          <div className="self-start rounded-lg border border-dashed border-brand-line px-3 py-2 text-xs text-brand-muted">
            <p className="font-medium">Tools called:</p>
            <ul className="mt-1 space-y-1 font-mono">
              {lastToolCalls.map((t, i) => (
                <li key={i}>
                  {t.tool}
                  <span className="text-brand-brownLight">
                    {" "}
                    {JSON.stringify(t.args).slice(0, 140)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <form
        className="mt-4 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Describe the new patient…"
          className="flex-1 rounded-lg border border-brand-line bg-brand-cream px-3 py-2 text-sm text-brand-ink outline-none focus:border-brand-brown"
          disabled={busy}
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="rounded-lg bg-brand-yellow px-4 py-2 text-sm font-bold text-brand-ink transition hover:bg-brand-yellowLight disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </main>
  );
}