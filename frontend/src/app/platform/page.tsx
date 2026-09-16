import Link from "next/link";
import StatusBadge from "@/components/StatusBadge";

const demos = [
  {
    href: "/intake",
    icon: "✚",
    title: "AI Patient Intake",
    desc: "Register a patient through an agent chat. Watch the tool-call transcript: validate → duplicate check → register. Try: \"Register Maria Lopez, DOB 1985-04-12.\"",
    status: "Live",
  },
  {
    href: "/eligibility",
    icon: "✓",
    title: "Eligibility Check",
    desc: "Pick a patient and verify coverage in seconds. Rules-first classification; every result records resolved_by RULE or LLM plus a full audit trail.",
    status: "Live",
  },
  {
    href: "/rcm",
    icon: "◆",
    title: "Revenue Cycle Agent",
    desc: "One agent runs the full pipeline from a clinical note: coding suggestions, prior-auth rules, claim submission, and the denial queue with metrics.",
    status: "Live",
  },
  {
    href: "/platform/patient-record",
    icon: "◉",
    title: "Patient Record View",
    desc: "The payoff — one coherent record: demographics, eligibility history, claims & denials, coding suggestions, labs, and the audit trail. All 20 modules write here.",
    status: "Demo",
  },
  {
    href: "/portal",
    icon: "💬",
    title: "Patient Portal Chatbot",
    desc: "The scoped patient assistant (#20 + #14): appointments, results status, billing, and a structured triage flow with emergency hard-stop. Conversations are logged to the audit trail.",
    status: "Live",
  },
];

export default function PlatformPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <h1 className="text-3xl font-bold text-brand-ink">Platform — Live Demos</h1>
      <p className="mt-2 max-w-2xl text-brand-muted">
        Working sandbox demos. Every module that is built is here — and nothing
        is claimed that isn&apos;t. The backend runs locally against a HAPI FHIR
        server and Postgres.
      </p>

      <div className="mt-6 rounded-xl border border-brand-line bg-brand-yellowSoft p-4 text-sm text-brand-brownDark">
        <strong>Demo data only.</strong> All patients, coverage, claims, and lab
        results are synthetic and generated locally. Nothing here connects to a
        real hospital or contains real PHI.
      </div>

      <div className="mt-10 space-y-4">
        {demos.map((d) => (
          <Link
            key={d.href}
            href={d.href}
            className="group block rounded-xl border border-brand-line bg-white p-6 shadow-sm transition hover:border-brand-brown hover:shadow-md"
          >
            <div className="flex items-start gap-4">
              <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-brand-yellow text-xl">
                {d.icon}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-bold text-brand-ink">{d.title}</h2>
                  <StatusBadge status={d.status} />
                </div>
                <p className="mt-1.5 text-sm leading-relaxed text-brand-muted">{d.desc}</p>
                <span className="mt-3 inline-block text-sm font-bold text-brand-brown transition group-hover:translate-x-1">
                  Open demo →
                </span>
              </div>
            </div>
          </Link>
        ))}
      </div>

      <section className="mt-14">
        <h2 className="text-xl font-bold text-brand-ink">How a demo run works</h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          {[
            {
              t: "1. Capture once",
              d: "Intake creates a single FHIR Patient — the source of truth every module reads.",
            },
            {
              t: "2. FHIR backbone",
              d: "Eligibility, coding, claims, and audit all read/write the same record. No re-entry.",
            },
            {
              t: "3. Audit everything",
              d: "The Logged trail shows exactly who did what to the record and when.",
            },
          ].map((s) => (
            <div key={s.t} className="rounded-xl border border-brand-line bg-white p-5 shadow-sm">
              <h3 className="text-sm font-bold text-brand-brownDark">{s.t}</h3>
              <p className="mt-2 text-sm leading-relaxed text-brand-muted">{s.d}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}