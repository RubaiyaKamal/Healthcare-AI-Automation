const features = [
  {
    t: "Role-based access (RBAC)",
    d: "Every staff role sees only the minimum necessary: front desk gets scheduling and insurance, billers get claims, clinicians get full records for their own patients. This is the HIPAA minimum-necessary principle applied as an access model.",
  },
  {
    t: "Complete audit trail",
    d: "Every read, write, and AI decision writes to audit_log — actor, action, resource, timestamp. Compliance and admin roles can answer \u201cwho touched this record, and when\u201d for any patient.",
  },
  {
    t: "Human-in-the-loop gates",
    d: "No module auto-finalizes clinical or financial actions. AI drafts, rules and humans confirm, then the action touches the permanent record or leaves the building (claim, prior auth, prescription, patient message).",
  },
  {
    t: "Single patient identity",
    d: "Duplicate-check guardrails run before any record is created, so billing, labs, and meds never fragment across two patient files — a data-quality issue that becomes a patient-safety issue in real hospitals.",
  },
];

const roadmap = [
  { item: "Multi-tenant facilities (facility_id scoping of payer_rules, lab ranges, staffing config)" },
  { item: "EHR adapters (Epic, Cerner, athenahealth) behind a single EHRAdapter interface" },
  { item: "True RBAC + SSO (OIDC/SAML) mapped to facility role structures" },
  { item: "Encryption at rest + TLS throughout, secrets via vault, not .env" },
  { item: "Audit export for compliance reporting (HIPAA, SOC 2 readiness)" },
];

export default function SecurityPage() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-3xl font-bold text-brand-ink">Security &amp; Compliance</h1>
      <p className="mt-2 max-w-2xl text-brand-muted">
        What this platform does today to protect patient records, and what it
        takes to reach production-ready HIPAA posture.
      </p>

      <div className="mt-6 rounded-xl border border-brand-line bg-brand-yellowSoft p-4 text-sm text-brand-brownDark">
        <strong>Important:</strong> the current build is a local sandbox with
        synthetic data only. It is not yet HIPAA-ready for production — no real
        PHI should be loaded. This page describes the security architecture and
        the remaining roadmap.
      </div>

      <section className="mt-10 grid gap-4 sm:grid-cols-2">
        {features.map((f) => (
          <div key={f.t} className="rounded-xl border border-brand-line bg-white p-5 shadow-sm">
            <h2 className="text-base font-bold text-brand-ink">{f.t}</h2>
            <p className="mt-2 text-sm leading-relaxed text-brand-muted">{f.d}</p>
          </div>
        ))}
      </section>

      <section className="mt-12 rounded-xl border border-brand-line bg-white p-6 shadow-sm">
        <h2 className="text-xl font-bold text-brand-ink">Humans in the loop, everywhere</h2>
        <p className="mt-3 text-sm leading-relaxed text-brand-muted">
          The same control pattern repeats across all 20 automations:
        </p>
        <div className="mt-5 grid gap-3 sm:grid-cols-4">
          {["1. AI drafts", "2. Rules validate", "3. Human approves", "4. Written / sent"].map((s, i) => (
            <div key={s} className="rounded-lg border border-brand-line bg-brand-cream p-4 text-center text-sm font-bold text-brand-brownDark">
              <span className="block text-2xl text-brand-yellow">{i + 1}</span>
              {s}
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-brand-muted">
          Deterministic parts (critical lab alerts, exact duplicate matches,
          eligibility rules) can confirm automatically; anything AI-generated is
          gated behind staff review.
        </p>
      </section>

      <section className="mt-12">
        <h2 className="text-xl font-bold text-brand-ink">Roadmap to production</h2>
        <ul className="mt-5 space-y-3">
          {roadmap.map((r) => (
            <li key={r.item} className="rounded-xl border border-brand-line bg-white p-4 text-sm text-brand-muted shadow-sm">
              <span className="mr-2 font-bold text-brand-brownDark">□</span>
              {r.item}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}