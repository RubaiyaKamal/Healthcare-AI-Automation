import Link from "next/link";

const domains = [
  { href: "/solutions#front-desk", label: "Front Desk & Patient Access" },
  { href: "/solutions#revenue-cycle", label: "Revenue Cycle" },
  { href: "/solutions#clinical", label: "Clinical Workflow" },
  { href: "/solutions#engagement", label: "Patient Engagement" },
  { href: "/solutions#operations", label: "Operations" },
];

const stats = [
  { v: "20", l: "Automations" },
  { v: "1", l: "FHIR Record per Patient" },
  { v: "100%", l: "Audited Actions" },
  { v: "0", l: "Duplicate Records" },
];

export default function Home() {
  return (
    <div className="w-full">
      <section className="mx-auto max-w-6xl px-6 pt-16 pb-10 text-center">
        <p className="inline-block rounded-full border border-brand-line bg-white px-4 py-1 text-xs font-bold uppercase tracking-wider text-brand-brown">
          End-to-End Healthcare Automation · built on FHIR
        </p>
        <h1 className="mx-auto mt-6 max-w-3xl text-4xl font-extrabold leading-tight tracking-tight text-brand-ink sm:text-5xl">
          Capture the patient once. Automate everything that follows.
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg text-brand-muted">
          20 AI automations across the front desk, revenue cycle, clinical
          workflow, and patient engagement — all reading and writing a single
          FHIR patient record. No re-entry, no orphaned records, full audit.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/platform"
            className="rounded-lg bg-brand-yellow px-6 py-3 text-sm font-bold text-brand-ink shadow-sm transition hover:bg-brand-yellowLight"
          >
            Try the live demos →
          </Link>
          <Link
            href="/solutions"
            className="rounded-lg border border-brand-line bg-white px-6 py-3 text-sm font-bold text-brand-brown transition hover:bg-brand-yellowSoft"
          >
            Browse the 20 automations
          </Link>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/Gemini_Generated_Image_5k1ynl5k1ynl5k1y.jpg"
          alt="HealthFlow AI platform overview"
          className="mx-auto w-full max-w-4xl rounded-2xl border border-brand-line object-cover shadow-lg"
        />
      </section>

      <section className="mx-auto max-w-6xl px-6 py-14">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {stats.map((s) => (
            <div
              key={s.l}
              className="rounded-xl border border-brand-line bg-white p-6 text-center shadow-sm"
            >
              <p className="text-3xl font-extrabold text-brand-yellow">{s.v}</p>
              <p className="mt-1 text-xs font-bold uppercase tracking-wider text-brand-brown">
                {s.l}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-16">
        <div className="rounded-2xl border border-brand-line bg-brand-ink p-8">
          <h2 className="text-xl font-bold text-brand-yellow">
            Five domains, one patient journey
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-brand-yellowLight/80">
            Patient info is captured once at intake, then every module reads and
            appends to the same record as the patient moves through your
            hospital or clinic.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            {domains.map((d) => (
              <Link
                key={d.href}
                href={d.href}
                className="rounded-full border border-brand-yellow/40 bg-white/5 px-4 py-2 text-sm font-semibold text-brand-yellow transition hover:bg-brand-yellow hover:text-brand-ink"
              >
                {d.label}
              </Link>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}