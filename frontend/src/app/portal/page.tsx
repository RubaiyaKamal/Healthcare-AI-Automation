"use client";

import { useEffect, useRef, useState } from "react";

type Patient = {
  fhir_id: string;
  first_name: string;
  last_name: string;
  dob: string;
};

type PortalMsg = {
  role: "user" | "assistant";
  content: string;
  kind?: string;
  hard_stop?: boolean;
};

type PortalReply = {
  session_id: string;
  reply: string;
  quick_replies: string[];
  kind: string;
  phase: string;
  hard_stop: boolean;
  data?: Record<string, unknown>;
};

const SCOPED = [
  "📅 Appointments",
  "🔬 Results & records",
  "🧾 Billing",
  "🤒 I'm not feeling well",
];

const KINDS = ["intro", "appts", "results", "billing", "triage", "confirm", "info", "hard_stop"];

export default function PortalPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [selected, setSelected] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState<PortalMsg[]>([]);
  const [quick, setQuick] = useState<string[]>(SCOPED);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [stopped, setStopped] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/patients")
      .then((r) => r.json())
      .then((data: Patient[]) => {
        setPatients(data);
        if (data.length > 0) setSelected(data[0].fhir_id);
      })
      .catch(() => setError("Could not load patients. Is the backend running?"));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, quick]);

  function resetChat() {
    setSessionId("");
    setMessages([]);
    setQuick(SCOPED);
    setStopped(false);
  }

  async function send(userText: string) {
    if (!selected || busy || stopped) return;

    const next: PortalMsg[] = [...messages, { role: "user", content: userText }];
    setMessages(next);
    setInput("");
    setBusy(true);

    try {
      const res = await fetch("/api/chat/portal", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          patient_fhir_id: selected,
          message: userText,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const data: PortalReply = await res.json();
      setSessionId(data.session_id);
      setMessages([
        ...next,
        { role: "assistant", content: data.reply, kind: data.kind, hard_stop: data.hard_stop },
      ]);
      setQuick(data.hard_stop ? [] : (data.quick_replies ?? []));
      setStopped(data.hard_stop);
    } catch (e) {
      setMessages([
        ...next,
        { role: "assistant", content: `Error talking to the portal assistant: ${e instanceof Error ? e.message : String(e)}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  const selPatient = patients.find((p) => p.fhir_id === selected);

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <header className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-brand-black">Patient Portal Assistant</h1>
          <p className="text-sm text-brand-muted">
            Scoped to appointments, results, billing, and triage (#20 + #14). It does not diagnose
            or interpret clinical results.
          </p>
        </div>
        <a href="/" className="text-sm font-semibold text-brand-brown hover:underline">
          ← Home
        </a>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-brand-brownLight bg-brand-yellowSoft px-4 py-2 text-sm text-brand-brownDark">
          {error}
        </div>
      )}

      <div className="mb-4 rounded-xl border border-brand-line bg-white p-4 shadow-sm">
        <label className="mb-1 block text-sm font-medium text-brand-brownDark">
          Demo patient (synthetic data only)
        </label>
        <select
          value={selected}
          onChange={(e) => {
            setSelected(e.target.value);
            resetChat();
          }}
          className="w-full rounded-lg border border-brand-line bg-brand-cream px-3 py-2 text-sm text-brand-ink outline-none focus:border-brand-brown"
        >
          {patients.map((p) => (
            <option key={p.fhir_id} value={p.fhir_id}>
              {p.last_name}, {p.first_name} — b. {p.dob}
            </option>
          ))}
        </select>
        <p className="mt-2 text-[11px] text-brand-muted">
          Conversations are logged to the patient record's audit trail — this assistant is not a
          private side-channel.
        </p>
      </div>

      <div className="flex h-[34rem] flex-col overflow-hidden rounded-xl border border-brand-line bg-white shadow-sm">
        <div className="flex-1 space-y-2 overflow-y-auto bg-brand-cream p-4">
          {messages.length === 0 && (
            <div className="rounded-2xl border border-brand-line bg-white px-4 py-3 text-sm text-brand-ink">
              Hi, I&apos;m here to help with appointments, results, and messages. What can I help
              with today?
              <span className="mt-1 block text-xs text-brand-muted">
                Pick a lane below — I&apos;ll guide the rest step by step.
              </span>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm ${
                  m.role === "user"
                    ? "bg-brand-yellow text-brand-ink"
                    : m.hard_stop
                      ? "border-2 border-red-300 bg-red-50 text-red-800 font-medium"
                      : m.kind === "confirm"
                        ? "border border-brand-brownDark bg-brand-yellowSoft text-brand-brownDark"
                        : m.kind === "triage"
                          ? "border border-brand-yellow bg-white text-brand-ink"
                          : "border border-brand-line bg-white text-brand-ink"
                }`}
              >
                {m.content}
              </div>
            </div>
          ))}

          {busy && (
            <div className="flex justify-start">
              <div className="rounded-2xl border border-brand-line bg-white px-3 py-2 text-sm text-brand-muted">
                <span className="mr-1 inline-block h-2 w-2 animate-pulse rounded-full bg-brand-brown" />
                thinking…
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        <div className="border-t border-brand-line bg-white p-3">
          {quick.length > 0 && !busy && (
            <div className="flex flex-wrap gap-1.5 pb-2">
              {quick.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="rounded-full border border-brand-line bg-brand-yellowSoft px-3 py-1.5 text-xs font-semibold text-brand-brownDark transition hover:bg-brand-yellow"
                >
                  {q}
                </button>
              ))}
            </div>
          )}

          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={stopped ? "This conversation has ended." : "Type or use the quick replies…"}
              className="w-full rounded-lg border border-brand-line bg-brand-cream px-3 py-2 text-sm text-brand-ink outline-none focus:border-brand-brown"
              disabled={busy || stopped}
            />
            <button
              type="submit"
              disabled={busy || stopped || !input.trim()}
              className="rounded-lg bg-brand-ink px-4 py-2 text-sm font-bold text-brand-yellow disabled:opacity-40"
            >
              Send
            </button>
            {stopped && (
              <button
                type="button"
                onClick={resetChat}
                className="rounded-lg border border-brand-line bg-brand-yellowSoft px-3 py-2 text-sm font-bold text-brand-brownDark transition hover:bg-brand-yellow"
              >
                Start over
              </button>
            )}
          </form>
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-brand-line bg-white p-4 text-xs text-brand-muted">
        <p>
          <strong className="text-brand-brownDark">About this assistant:</strong> it is
          intentionally limited. It does not diagnose, recommend treatment, or interpret your
          clinical results — those are reviewed and communicated by your care team. If you
          describe symptoms that could be urgent, it will guide you to emergency care
          immediately rather than continuing the conversation. Every conversation is logged and
          available to your provider&apos;s staff, consistent with the audit and privacy standards
          that apply to the rest of your health record.
        </p>
        <p className="mt-2">
          Backed by modules #1 scheduling, #2/#13 billing &amp; claims, #8 medications, #15 lab
          notification, #14 triage, and #20 patient communication.
        </p>
      </div>
    </main>
  );
}