import Link from "next/link";

const faqs = [
  {
    q: "Will an AI read my medical records?",
    a: "AI may assist your provider's office with scheduling, reminders, and administrative tasks. Under its design, clinical notes and results are never auto-finalized by AI, and any AI draft requires review by staff. Policies, scope, and opt-outs are defined by each facility and its compliance team.",
  },
  {
    q: "Can I opt out of automated reminders?",
    a: "Yes — automated reminders about appointments, labs, and billing should be configurable per patient through your facility's portal settings. If your facility uses this platform, ask their front desk to adjust your preferences.",
  },
  {
    q: "Is my data shared?",
    a: "Data use is governed by your facility's HIPAA policies and privacy notice. This platform is designed to write to the facility's own FHIR EHR backbone and to keep a full audit trail of every access — it does not create an independent copy of your records for sale.",
  },
  {
    q: "Who can see my information?",
    a: "Role-based access is enforced by design: front-desk staff see scheduling and insurance details but not your clinical notes; billers see claims but not lab results; clinicians see full records for their own patients only.",
  },
];

export default function PatientsPage() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-3xl font-bold text-brand-ink">Patients</h1>
      <p className="mt-2 max-w-2xl text-brand-muted">
        If your hospital or clinic uses HealthFlow AI, here is what you can
        expect — and how to reach your records.
      </p>

      <section className="mt-10 grid gap-4 sm:grid-cols-2">
        {[
          {
            t: "Faster check-in",
            d: "An AI assistant can walk you through registration before you arrive, so you spend less time with paperwork.",
          },
          {
            t: "Smarter reminders",
            d: "Automated reminders for upcoming appointments, lab results, and billing — sent the way you prefer.",
          },
          {
            t: "Fewer surprise bills",
            d: "Insurance eligibility is verified before your visit whenever possible, so coverage is known up front.",
          },
          {
            t: "A human, always",
            d: "AI drafts and assists — it never makes clinical decisions alone. Staff review everything that touches your care.",
          },
        ].map((c) => (
          <div key={c.t} className="rounded-xl border border-brand-line bg-white p-5 shadow-sm">
            <h2 className="text-base font-bold text-brand-ink">{c.t}</h2>
            <p className="mt-2 text-sm leading-relaxed text-brand-muted">{c.d}</p>
          </div>
        ))}
      </section>

      <section className="mt-12 rounded-xl border border-brand-line bg-white p-6 shadow-sm">
        <h2 className="text-xl font-bold text-brand-ink">My Health portal</h2>
        <p className="mt-2 text-sm text-brand-muted">
          Where patients log in to see appointments, lab results, and messages.
        </p>
        <div className="mt-4 inline-flex">
          <Link
            href="/login?portal=patient"
            className="rounded-lg bg-brand-yellow px-5 py-2.5 text-sm font-bold text-brand-ink transition hover:bg-brand-yellowLight"
          >
            Patient Login →
          </Link>
        </div>
        <p className="mt-3 text-xs text-brand-muted">
          Staff (front desk, clinical, billing) use the Staff Login from the navbar.
        </p>
      </section>

      <section className="mt-12">
        <h2 className="text-xl font-bold text-brand-ink">Your privacy</h2>
        <p className="mt-3 text-sm leading-relaxed text-brand-muted">
          The platform is built around a single FHIR patient record and a full
          audit trail: every time a staff member opens your record, the who, the
          what, and the when are logged. Role-based access means people only see
          what their job requires — the minimum-necessary principle under HIPAA.
          This demo site uses synthetic data only; your facility&apos;s deployment
          defines the real production policies.
        </p>
        <div className="mt-4">
          <Link href="/security" className="text-sm font-bold text-brand-brown hover:underline">
            Read about Security &amp; Compliance →
          </Link>
        </div>
      </section>

      <section className="mt-12">
        <h2 className="text-xl font-bold text-brand-ink">Frequently asked questions</h2>
        <div className="mt-5 space-y-3">
          {faqs.map((f) => (
            <details
              key={f.q}
              className="group rounded-xl border border-brand-line bg-white p-4 shadow-sm"
            >
              <summary className="cursor-pointer list-none text-sm font-bold text-brand-ink">
                <span className="mr-2 text-brand-yellow">▸</span>
                {f.q}
              </summary>
              <p className="mt-2 pl-6 text-sm leading-relaxed text-brand-muted">{f.a}</p>
            </details>
          ))}
        </div>
      </section>
    </main>
  );
}