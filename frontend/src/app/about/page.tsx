import Link from "next/link";
import StatusBadge from "@/components/StatusBadge";

const problem = [
  {
    t: "Denied claims cost real money",
    d: "Between 9–17% of first-pass claims are denied, and most denials are preventable — missing codes, missing prior auth, data entry errors. Every denied claim means rework, cash-flow delay, and payer overhead.",
  },
  {
    t: "Front desks drown in re-typing",
    d: "The same demographics get re-entered at registration, eligibility, scheduling, and billing. Each copy is a chance to corrupt the patient's record.",
  },
  {
    t: "Documentation burnout",
    d: "Clinicians spend more time on notes and billing than at the bedside. When the record is structured at capture, the note pays for itself downstream.",
  },
  {
    t: "No-shows leak revenue",
    d: "Missed appointments cost staff hours and idle rooms. Simple, well-timed reminders change behavior — if the infrastructure bothers to send them.",
  },
];

const principles = [
  {
    t: "Capture once, reuse everywhere",
    d: "Patient info enters at intake and becomes a single FHIR Patient record. The other 19 automations read and append to that record — nobody re-collects it.",
  },
  {
    t: "Deterministic first, AI second",
    d: "Rules classify eligibility, claim responses, and duplicate matches first. The LLM only steps in for genuinely unrecognized edge cases — and every result records how it was resolved.",
  },
  {
    t: "Human in the loop before it counts",
    d: "AI drafts; a deterministic layer and/or a human confirms; then it touches the permanent record or leaves the building. No module auto-finalizes clinical or financial actions.",
  },
  {
    t: "Audit everything",
    d: "Every access and every AI decision is written to audit_log with actor, action, resource, and timestamp. Compliance readiness is a feature, not a retrofit.",
  },
];

const roadmap = [
  { phase: "Phase 1", label: "Foundation + Front Desk", items: ["EHR/FHIR core (#11)", "Intake & Registration (#3)", "Eligibility Verification (#12)"], status: "Live" },
  { phase: "Phase 2", label: "Revenue Cycle", items: ["RCM umbrella (#13)", "Coding (#5)", "Prior Auth (#6)", "Billing & Claims (#2)"], status: "Live" },
  { phase: "Phase 3", label: "Clinical + Engagement", items: ["Documentation (#4)", "Records Extraction (#19)", "Follow-up & Communication (#7, #20)", "Lab Processing (#15)"], status: "In Progress" },
  { phase: "Phase 4", label: "Predictive + Operations", items: ["No-Show Prediction (#10)", "Fraud Detection (#9)", "Triage (#14)", "Referral (#18)"], status: "Roadmap" },
  { phase: "Phase 5", label: "Staffing + Inventory + Meds", items: ["Staff Scheduling (#16)", "Inventory (#17)", "Medication Management (#8)"], status: "Roadmap" },
];

export default function AboutPage() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-3xl font-bold text-brand-ink">About HealthFlow AI</h1>
      <p className="mt-4 max-w-2xl text-brand-muted">
        An end-to-end healthcare automation portfolio: 20 automations across
        front desk, revenue cycle, clinical workflow, patient engagement, and
        operations — all reading and writing one FHIR patient record.
      </p>

      <section className="mt-12">
        <h2 className="text-xl font-bold text-brand-ink">The problem we are solving</h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {problem.map((p) => (
            <div key={p.t} className="rounded-xl border border-brand-line bg-white p-5 shadow-sm">
              <h3 className="text-base font-semibold text-brand-ink">{p.t}</h3>
              <p className="mt-2 text-sm leading-relaxed text-brand-muted">{p.d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-12">
        <h2 className="text-xl font-bold text-brand-ink">Our approach</h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {principles.map((p) => (
            <div key={p.t} className="rounded-xl border border-brand-line bg-brand-yellowSoft p-5 shadow-sm">
              <h3 className="text-base font-bold text-brand-brownDark">{p.t}</h3>
              <p className="mt-2 text-sm leading-relaxed text-brand-brownDark">{p.d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-12">
        <h2 className="text-xl font-bold text-brand-ink">Architecture &amp; standards</h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          {[
            { t: "FHIR / HL7-native", d: "Patient, Coverage, Claim, Appointment, Observation: resources, not rows — FHIR is the source of truth; the cache is state, not truth." },
            { t: "Local / on-prem capable", d: "Runs on Docker with a local HAPI FHIR server and Postgres. Nothing in the sandbox touches outside services or your real PHI." },
            { t: "Audit-ready by design", d: "A HIPAA-style access trail is built in from the first module, not bolted on. RBAC and per-facility config are the roadmap to production." },
          ].map((c) => (
            <div key={c.t} className="rounded-xl border border-brand-line bg-white p-5 shadow-sm">
              <h3 className="text-base font-semibold text-brand-ink">{c.t}</h3>
              <p className="mt-2 text-sm leading-relaxed text-brand-muted">{c.d}</p>
            </div>
          ))}
        </div>
        <div className="mt-4">
          <Link href="/security" className="text-sm font-bold text-brand-brown hover:underline">
            Full Security &amp; Compliance details →
          </Link>
        </div>
      </section>

      <section className="mt-12">
        <h2 className="text-xl font-bold text-brand-ink">Roadmap</h2>
        <p className="mt-2 text-sm text-brand-muted">
          Honest status for every phase. Live means you can open a working demo
          today.
        </p>
        <div className="mt-5 space-y-3">
          {roadmap.map((r) => (
            <div key={r.phase} className="flex flex-wrap items-start gap-4 rounded-xl border border-brand-line bg-white p-4 shadow-sm">
              <div className="w-24 shrink-0">
                <p className="text-sm font-bold text-brand-brownDark">{r.phase}</p>
                <p className="text-xs text-brand-muted">{r.label}</p>
              </div>
              <div className="flex-1">
                <ul className="text-sm text-brand-muted">
                  {r.items.map((i) => (
                    <li key={i} className="list-inside">• {i}</li>
                  ))}
                </ul>
              </div>
              <StatusBadge status={r.status} />
            </div>
          ))}
        </div>
      </section>

      <section className="mt-12 rounded-xl border border-brand-line bg-white p-6 text-sm text-brand-muted shadow-sm">
        This is a portfolio / demo build — not yet connected to a live hospital
        and not HIPAA-ready for production. No real patient data is loaded
        anywhere. Sandbox data is synthetic by design.
      </section>
    </main>
  );
}