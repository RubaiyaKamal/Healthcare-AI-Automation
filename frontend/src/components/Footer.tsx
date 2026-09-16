import Link from "next/link";

const columns = [
  {
    heading: "Platform",
    links: [
      { href: "/platform", label: "Live Demos" },
      { href: "/platform/patient-record", label: "Patient Record Demo" },
      { href: "/intake", label: "AI Intake" },
      { href: "/eligibility", label: "Eligibility Check" },
      { href: "/rcm", label: "Revenue Cycle" },
    ],
  },
  {
    heading: "Solutions",
    links: [
      { href: "/solutions#front-desk", label: "Front Desk & Patient Access" },
      { href: "/solutions#revenue-cycle", label: "Revenue Cycle" },
      { href: "/solutions#clinical", label: "Clinical Workflow" },
      { href: "/solutions#engagement", label: "Patient Engagement" },
      { href: "/solutions#operations", label: "Operations" },
    ],
  },
  {
    heading: "Company",
    links: [
      { href: "/about", label: "About Us" },
      { href: "/security", label: "Security & Compliance" },
      { href: "/patients", label: "Patients" },
      { href: "/contact", label: "Contact" },
      { href: "/login?portal=staff", label: "Staff Login" },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="border-t border-brand-line bg-brand-cream">
      <div className="mx-auto max-w-6xl px-6 py-12">
        <div className="grid gap-10 md:grid-cols-[1.5fr_1fr_1fr_1fr]">
          <div>
            <div className="flex items-center gap-2">
              <span className="grid h-8 w-8 place-items-center rounded-full bg-brand-yellow">
                <span className="text-sm">●</span>
              </span>
              <span className="text-lg font-extrabold tracking-tight text-brand-ink">
                HealthFlow AI
              </span>
            </div>
            <p className="mt-3 max-w-xs text-sm leading-relaxed text-brand-muted">
              One patient record, one FHIR backbone, 20 automations across
              front desk, revenue cycle, clinical workflow, and patient
              engagement.
            </p>
          </div>

          {columns.map((col) => (
            <div key={col.heading}>
              <h4 className="text-xs font-bold uppercase tracking-wider text-brand-brownDark">
                {col.heading}
              </h4>
              <ul className="mt-3 space-y-2">
                {col.links.map((l) => (
                  <li key={l.href}>
                    <Link
                      href={l.href}
                      className="text-sm text-brand-brown transition hover:text-brand-ink"
                    >
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-10 border-t border-brand-line pt-6 text-xs text-brand-muted">
          HealthFlow AI is an end-to-end automation portfolio built on FHIR. All
          demo data is synthetic and sandboxed — no real patient data, not yet
          HIPAA-ready for production.
        </div>
      </div>
    </footer>
  );
}