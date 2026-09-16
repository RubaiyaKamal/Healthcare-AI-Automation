"use client";

import { useState } from "react";
import Link from "next/link";

type Msg = {
  from: "bot" | "user";
  text: string;
  kind?: string;
};

type BotReply = {
  reply: string;
  kind: string;
  quick_replies: string[];
  wants_demo?: boolean;
};

// ---------------------------------------------------------------------------
// Static fallback answers — used ONLY when the backend (/api/chat/site) is not
// reachable, so the marketing site still works standalone. Copy must match the
// backend's scope rules: pre-sales only, no clinical answers, no unverified
// compliance claims.
// ---------------------------------------------------------------------------
const STATIC_ANSWERS: Record<string, string[]> = {
  "what does healthflow": [
    "HealthFlow AI automates the end-to-end workflows a hospital or clinic runs every day: Front Desk & Patient Access (intake, scheduling, eligibility, prior auth), Revenue Cycle (coding, claims, denials), Clinical Workflow (documentation, triage, labs), Patient Engagement (follow-ups, communication), and Operations (fraud, no-show, staffing, inventory, referrals, records).",
    "7 automations are live as working demos today. Patient data is captured once and every module reads the same FHIR record — no re-entry.",
  ],
  "is it hipaa": [
    "Straight answer: not certified today. The build is a local sandbox with synthetic data, built to be audit-ready, but not production HIPAA yet — see the Security & Compliance page for exactly what we do and the roadmap.",
  ],
  "epic": [
    "Today HealthFlow AI is FHIR-native. Epic, Cerner, and athenahealth adapters are on our roadmap behind a single EHR-adapter interface — see the Security page. Tell us which EHR you're on and we'll confirm interoperability for your environment.",
  ],
  "integrat": [
    "Today HealthFlow AI is FHIR-native — any EHR with a FHIR API can connect. Epic, Cerner, and athenahealth adapters are on the roadmap (Security page).",
  ],
  default: [
    "I'd love to connect you with our team for that — want me to set up a quick call? You can also book a demo from the button below.",
  ],
};

function staticAnswer(q: string): string[] {
  const key = q.toLowerCase();
  for (const k of Object.keys(STATIC_ANSWERS)) {
    if (k === "default") continue;
    if (key.includes(k)) return STATIC_ANSWERS[k];
  }
  return STATIC_ANSWERS.default;
}

type DemoForm = { open: boolean; name: string; email: string; hospital: string };

const QUICK = [
  "What does HealthFlow AI do?",
  "How does pricing work?",
  "Is this HIPAA compliant?",
  "Can I book a demo?",
  "Does this integrate with Epic or Cerner?",
];

export default function SiteChatbot() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([
    {
      from: "bot",
      text: "Hi, I'm the HealthFlow AI assistant. I help with questions about the platform and can point you to live demos. I don't give medical advice.",
    },
  ]);
  const [quick, setQuick] = useState<string[]>(QUICK);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [demo, setDemo] = useState<DemoForm>({ open: false, name: "", email: "", hospital: "" });

  async function ask(q: string) {
    if (!q.trim()) return;
    setMsgs((m) => [...m, { from: "user", text: q }]);
    setInput("");
    setTyping(true);
    setQuick([]);

    let reply: BotReply;
    try {
      const res = await fetch("/api/chat/site", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: q }),
      });
      if (!res.ok) throw new Error("backend unavailable");
      reply = (await res.json()) as BotReply;
    } catch {
      // Graceful degradation: local static answers keep the widget working.
      reply = {
        reply: staticAnswer(q).join("\n\n"),
        kind: q.toLowerCase().includes("demo") ? "demo_collect" : "fallback",
        quick_replies: QUICK,
        wants_demo: q.toLowerCase().includes("demo"),
      };
    }

    setMsgs((m) => [...m, { from: "bot", text: reply.reply, kind: reply.kind }]);
    setQuick(reply.quick_replies ?? []);
    setTyping(false);

    if (reply.kind === "demo_collect") {
      setDemo((d) => ({ ...d, open: true }));
    }
  }

  async function submitDemo(e: React.FormEvent) {
    e.preventDefault();
    const { name, email, hospital } = demo;
    if (!name.trim() || !email.trim() || !hospital.trim()) return;

    try {
      const res = await fetch("/api/chat/site/demo-request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, hospital }),
      });
      const data = await res.json();
      if (!data.ok) {
        setMsgs((m) => [...m, { from: "bot", text: "Please check the details and try again." }]);
        return;
      }
      setMsgs((m) => [...m, { from: "bot", text: data.reply }]);
    } catch {
      setMsgs((m) => [
        ...m,
        {
          from: "bot",
          text: "Thanks {name} — I couldn't reach the sales flow just now, but you can also email hello@healthflow.ai.",
        },
      ]);
    }
    setDemo({ open: false, name: "", email: "", hospital: "" });
    setQuick(QUICK);
  }

  return (
    <>
      {open && (
        <div className="fixed bottom-24 right-4 z-[60] flex h-[30rem] w-[22rem] flex-col overflow-hidden rounded-2xl border border-brand-line bg-white shadow-2xl">
          <div className="flex items-center justify-between bg-brand-ink px-4 py-3 text-brand-yellowLight">
            <div>
              <p className="text-sm font-bold">HealthFlow Assistant</p>
              <p className="text-[11px] opacity-70">Platform info only · no medical advice</p>
            </div>
            <button onClick={() => setOpen(false)} className="text-sm" aria-label="Close chat">
              ✕
            </button>
          </div>

          <div className="flex-1 space-y-2 overflow-y-auto bg-brand-cream p-3">
            {msgs.map((m, i) => (
              <div key={i} className={`flex ${m.from === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm ${
                    m.from === "user"
                      ? "bg-brand-yellow text-brand-ink"
                      : "border border-brand-line bg-white text-brand-ink"
                  }`}
                >
                  {m.text}
                </div>
              </div>
            ))}

            {typing && (
              <div className="flex justify-start">
                <div className="rounded-2xl border border-brand-line bg-white px-3 py-2 text-sm text-brand-muted">
                  <span className="mr-1 inline-block h-2 w-2 animate-pulse rounded-full bg-brand-brown" />
                  typing…
                </div>
              </div>
            )}

            {demo.open && (
              <form
                onSubmit={submitDemo}
                className="space-y-2 rounded-2xl border border-brand-yellow bg-brand-yellowSoft p-3 text-sm"
              >
                <p className="font-bold text-brand-brownDark">Book a demo</p>
                <input
                  value={demo.name}
                  onChange={(e) => setDemo((d) => ({ ...d, name: e.target.value }))}
                  placeholder="Your name"
                  className="w-full rounded-lg border border-brand-line bg-white px-3 py-1.5 outline-none focus:border-brand-brown"
                  required
                />
                <input
                  value={demo.email}
                  onChange={(e) => setDemo((d) => ({ ...d, email: e.target.value }))}
                  type="email"
                  placeholder="Work email"
                  className="w-full rounded-lg border border-brand-line bg-white px-3 py-1.5 outline-none focus:border-brand-brown"
                  required
                />
                <input
                  value={demo.hospital}
                  onChange={(e) => setDemo((d) => ({ ...d, hospital: e.target.value }))}
                  placeholder="Hospital / clinic name"
                  className="w-full rounded-lg border border-brand-line bg-white px-3 py-1.5 outline-none focus:border-brand-brown"
                  required
                />
                <button
                  type="submit"
                  className="w-full rounded-lg bg-brand-brownDark px-3 py-2 text-xs font-bold text-brand-yellow transition hover:bg-brand-ink"
                >
                  Send request
                </button>
                <button
                  type="button"
                  onClick={() => setDemo((d) => ({ ...d, open: false }))}
                  className="w-full text-center text-xs text-brand-muted hover:underline"
                >
                  Never mind
                </button>
              </form>
            )}
          </div>

          <div className="border-t border-brand-line bg-white p-2">
            {quick.length > 0 && (
              <div className="flex flex-wrap gap-1.5 px-1 pb-2">
                {quick.map((q) => (
                  <button
                    key={q}
                    onClick={() => ask(q)}
                    className="rounded-full border border-brand-line bg-brand-yellowSoft px-2.5 py-1 text-xs font-semibold text-brand-brownDark transition hover:bg-brand-yellow"
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
                ask(input);
              }}
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a question…"
                className="w-full rounded-lg border border-brand-line bg-brand-cream px-3 py-2 text-sm text-brand-ink outline-none focus:border-brand-brown"
              />
              <button
                type="submit"
                className="rounded-lg bg-brand-ink px-3 text-sm font-bold text-brand-yellow"
              >
                ➤
              </button>
            </form>
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-4 right-4 z-[60] grid h-14 w-14 place-items-center rounded-full bg-brand-brownDark text-base font-extrabold text-brand-yellow shadow-xl transition hover:bg-brand-ink"
        aria-label="Open assistant"
      >
        {open ? "✕" : "AI"}
      </button>

      {!open && (
        <Link
          href="/security"
          className="fixed bottom-20 right-[4.6rem] z-[60] hidden max-w-[16rem] rounded-xl border border-brand-line bg-white px-3 py-2 text-xs text-brand-muted shadow-lg sm:block"
        >
          AI assistant — answers about the platform, not medical advice.
        </Link>
      )}
    </>
  );
}