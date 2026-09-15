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
          <h1 className="text-xl font-bold">Patient Intake Agent</h1>
          <p className="text-sm text-slate-500">
            Duplicate check enforced before registration. Synthetic data only.
          </p>
        </div>
        <a href="/" className="text-sm text-sky-600 hover:underline">
          ← Home
        </a>
      </header>

      <div className="flex flex-1 flex-col gap-2 overflow-y-auto rounded-xl border border-slate-200 bg-white p-4">
        {messages.length === 0 && (
          <div className="mb-2">
            <p className="mb-3 text-sm text-slate-500">
              The front-desk agent will walk you through registration. Try:
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-700 transition hover:bg-slate-100"
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
                ? "self-end bg-sky-600 text-white"
                : "self-start bg-slate-100 text-slate-800"
            }`}
            style={{ whiteSpace: "pre-wrap" }}
          >
            {m.content}
          </div>
        ))}

        {busy && (
          <div className="self-start rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-500">
            <span className="mr-1 inline-block h-2 w-2 animate-pulse rounded-full bg-sky-500" />
            Running agent tools…
          </div>
        )}

        {lastToolCalls.length > 0 && (
          <div className="self-start rounded-lg border border-dashed border-slate-300 px-3 py-2 text-xs text-slate-500">
            <p className="font-medium">Tools called:</p>
            <ul className="mt-1 space-y-1 font-mono">
              {lastToolCalls.map((t, i) => (
                <li key={i}>
                  {t.tool}
                  <span className="text-slate-400">
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
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-sky-500"
          disabled={busy}
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-700 disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </main>
  );
}